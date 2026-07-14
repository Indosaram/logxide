//! Global state and utility functions for LogXide
//!
//! This module contains global registries, thread-local storage,
//! and module-level utility functions.

use arc_swap::ArcSwap;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict};
use std::cell::RefCell;
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};

use once_cell::sync::Lazy;

use crate::core::{get_logger as core_get_logger, get_root_logger, LogLevel};
use crate::fast_logger;
use crate::formatter::PythonFormatter;
use crate::handler::{FileHandler, HTTPHandler, Handler, OverflowStrategy, RotatingFileHandler};
use crate::py_handlers::{
    PyFileHandler, PyHTTPHandler, PyMemoryHandler, PyOTLPHandler, PyRotatingFileHandler,
    PyStreamHandler,
};
use crate::py_logger::PyLogger;

/// Global registry of log handlers (lock-free reads via ArcSwap).
pub static HANDLERS: Lazy<ArcSwap<Vec<Arc<dyn Handler + Send + Sync>>>> =
    Lazy::new(|| ArcSwap::from_pointee(Vec::new()));

/// Root py_dispatch list: text-sink wrappers + foreign Python handlers attached to root.
pub static GLOBAL_PY_HANDLERS: Lazy<Mutex<Vec<PyEntry>>> = Lazy::new(|| Mutex::new(Vec::new()));

/// Root lifecycle list: all rust-backed arcs attached to root (incl. text-sink `_inner`)
/// so module-level flush/teardown can reach them.
pub static GLOBAL_LIFECYCLE: Lazy<Mutex<Vec<Arc<dyn Handler + Send + Sync>>>> =
    Lazy::new(|| Mutex::new(Vec::new()));

/// Number of currently-attached handlers that require caller-frame introspection.
/// Lets removeHandler recompute CALLER_INFO_REQUIRED back to false.
pub static CALLER_INFO_COUNT: AtomicUsize = AtomicUsize::new(0);

/// Identity of a handler entry, used for removeHandler matching.
/// Rust entries: `Arc::as_ptr` as usize. Python entries: `obj.as_ptr` as usize.
pub type HandlerId = usize;

/// A rust-backed handler dispatched via `Arc::emit` (structured HTTP/OTLP or direct pyclass).
pub struct RustEntry {
    pub arc: Arc<dyn Handler + Send + Sync>,
    pub id: HandlerId,
    pub wrapper: Option<Py<PyAny>>,
}

/// A Python handler dispatched via `handle()` (text-sink wrapper or foreign handler).
pub struct PyEntry {
    pub obj: Py<PyAny>,
    pub id: HandlerId,
    pub needs_caller: bool,
}

/// Identity for a rust-backed handler arc.
pub fn arc_id(arc: &Arc<dyn Handler + Send + Sync>) -> HandlerId {
    Arc::as_ptr(arc) as *const () as usize
}

/// Global flag indicating if caller frame introspection is required by any formatter/handler
pub static CALLER_INFO_REQUIRED: AtomicBool = AtomicBool::new(false);

/// Check if a format string contains caller-related placeholders and activate introspection if so
pub fn check_caller_info_needed(format_str: &str) {
    if format_string_needs_caller(format_str) {
        CALLER_INFO_REQUIRED.store(true, Ordering::Relaxed);
    }
}

/// Whether a format string references caller-frame fields.
pub fn format_string_needs_caller(format_str: &str) -> bool {
    format_str.contains("%(pathname)")
        || format_str.contains("%(filename)")
        || format_str.contains("%(module)")
        || format_str.contains("%(lineno)")
        || format_str.contains("%(funcName)")
        || format_str.contains("%(func_name)")
}

/// Expose caller-info activation to Python compatibility layer
#[pyfunction]
pub fn activate_caller_info(format_str: &str) {
    check_caller_info_needed(format_str);
}

/// Decide whether a foreign Python handler forces global caller-frame collection, by
/// inspecting its formatter's format string. Caller-info is forced ONLY when the format
/// string demonstrably references a caller field (%(pathname)s / %(filename)s /
/// %(module)s / %(lineno)s / %(funcName)s). A formatter-less or non-inspectable handler
/// (e.g. urllib3's NullHandler, or a merely-installed unconfigured sentry-sdk) does NOT
/// force it — caller collection is a per-call tax, so the performance-safe default is off.
fn python_handler_needs_caller(handler: &Bound<PyAny>) -> bool {
    let Ok(formatter) = handler.getattr("formatter") else {
        return false;
    };
    if formatter.is_none() {
        return false;
    }
    let fmt = formatter
        .getattr("fmt")
        .ok()
        .filter(|f| !f.is_none())
        .or_else(|| formatter.getattr("_fmt").ok().filter(|f| !f.is_none()));
    match fmt.and_then(|f| f.extract::<String>().ok()) {
        Some(fmt_str) => format_string_needs_caller(&fmt_str),
        None => false,
    }
}

/// GLOBAL LOGGER REGISTRY in Rust to keep PyLogger objects alive
pub static PY_LOGGER_KEEP_ALIVE: Lazy<Mutex<HashMap<String, Py<PyLogger>>>> =
    Lazy::new(|| Mutex::new(HashMap::new()));

thread_local! {
    pub static THREAD_NAME: RefCell<Option<String>> = const { RefCell::new(None) };
}

#[pyfunction(name = "getLogger")]
#[pyo3(signature = (name=None, manager=None))]
pub fn get_logger(
    py: Python,
    name: Option<&str>,
    manager: Option<Py<PyAny>>,
) -> PyResult<PyLogger> {
    let logger_name = name.unwrap_or("root");

    let mut alive = PY_LOGGER_KEEP_ALIVE.lock().unwrap();
    if let Some(p) = alive.get(logger_name) {
        return Ok(p.bind(py).borrow().clone());
    }

    let inner = if name.is_some() {
        core_get_logger(logger_name)
    } else {
        get_root_logger()
    };
    let pylogger = PyLogger::with_params(
        inner,
        fast_logger::get_fast_logger(logger_name),
        manager.map(|m| m.clone_ref(py)),
    );

    let p = Py::new(py, pylogger)?;
    alive.insert(logger_name.to_string(), p.clone_ref(py));

    Ok(p.bind(py).borrow().clone())
}

#[pyfunction]
#[pyo3(signature = (**_kwargs))]
pub fn basicConfig(_py: Python, _kwargs: Option<&Bound<'_, PyDict>>) -> PyResult<()> {
    Ok(())
}

#[pyfunction]
pub fn flush(py: Python) -> PyResult<()> {
    let mut handlers: Vec<Arc<dyn Handler + Send + Sync>> =
        HANDLERS.load().iter().cloned().collect();
    handlers.extend(GLOBAL_LIFECYCLE.lock().unwrap().iter().cloned());
    py.detach(|| {
        for h in handlers.iter() {
            h.flush();
        }
    });
    Ok(())
}

/// Append a handler to the global registry via copy-on-write.
pub fn push_handler(h: Arc<dyn Handler + Send + Sync>) {
    let current = HANDLERS.load();
    let mut new_vec: Vec<Arc<dyn Handler + Send + Sync>> = current.iter().cloned().collect();
    new_vec.push(h);
    HANDLERS.store(Arc::new(new_vec));
}

#[pyfunction]
pub fn set_thread_name(_py: Python, name: String) -> PyResult<()> {
    THREAD_NAME.with(|n| {
        *n.borrow_mut() = Some(name);
    });
    Ok(())
}

#[pyfunction]
#[pyo3(signature = (url, headers=None, capacity=None, batch_size=None, flush_interval=None, level=None))]
pub fn register_http_handler(
    _py: Python,
    url: String,
    headers: Option<HashMap<String, String>>,
    capacity: Option<usize>,
    batch_size: Option<usize>,
    flush_interval: Option<u64>,
    level: Option<u32>,
) -> PyResult<()> {
    let h = Arc::new(HTTPHandler::new(
        url,
        headers.unwrap_or_default(),
        capacity.unwrap_or(10000),
        batch_size.unwrap_or(1000),
        flush_interval.unwrap_or(30),
        OverflowStrategy::DropOldest,
    ));
    h.set_level(LogLevel::from_usize(level.unwrap_or(20) as usize));
    push_handler(h);
    Ok(())
}

#[pyfunction]
pub fn clear_handlers(py: Python) -> PyResult<()> {
    let mut arcs: Vec<Arc<dyn Handler + Send + Sync>> =
        GLOBAL_LIFECYCLE.lock().unwrap().drain(..).collect();
    arcs.extend(HANDLERS.load().iter().cloned());
    py.detach(|| {
        for arc in arcs.iter() {
            arc.shutdown();
        }
    });
    HANDLERS.store(Arc::new(Vec::new()));
    GLOBAL_PY_HANDLERS.lock().unwrap().clear();
    Ok(())
}

#[pyfunction(name = "register_file_handler")]
#[pyo3(signature = (filename, level=None, format=None, datefmt=None))]
pub fn register_file_handler(
    _py: Python,
    filename: String,
    level: Option<u32>,
    format: Option<String>,
    datefmt: Option<String>,
) -> PyResult<()> {
    use pyo3::exceptions::PyValueError;

    let log_level = LogLevel::from_usize(level.unwrap_or(10) as usize);

    let handler = FileHandler::new(filename)
        .map_err(|e| PyValueError::new_err(format!("Failed to create file handler: {e}")))?;

    handler.set_level(log_level);

    // Set formatter if format string is provided
    if let Some(fmt) = format {
        check_caller_info_needed(&fmt);
        let formatter = match datefmt {
            Some(df) => PythonFormatter::with_date_format(fmt, df),
            None => PythonFormatter::new(fmt),
        };
        handler.set_formatter_instance(Arc::new(formatter));
    }

    push_handler(Arc::new(handler));
    Ok(())
}

#[pyfunction(name = "register_rotating_file_handler")]
#[pyo3(signature = (filename, max_bytes=None, backup_count=None, level=None))]
pub fn register_rotating_file_handler(
    _py: Python,
    filename: String,
    max_bytes: Option<u64>,
    backup_count: Option<u32>,
    level: Option<u32>,
) -> PyResult<()> {
    let log_level = LogLevel::from_usize(level.unwrap_or(10) as usize);

    let handler = RotatingFileHandler::new(
        filename,
        max_bytes.unwrap_or(10 * 1024 * 1024),
        backup_count.unwrap_or(5),
    )
    .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

    handler.set_level(log_level);
    push_handler(Arc::new(handler));
    Ok(())
}

#[pyfunction(name = "register_stream_handler")]
#[pyo3(signature = (stream=None, level=None, format=None, datefmt=None))]
pub fn register_stream_handler(
    _py: Python,
    stream: Option<&Bound<PyAny>>,
    level: Option<u32>,
    format: Option<String>,
    datefmt: Option<String>,
) -> PyResult<()> {
    use pyo3::exceptions::PyValueError;

    let log_level = LogLevel::from_usize(level.unwrap_or(10) as usize);

    // Create formatter if format string is provided
    let formatter: Option<Arc<dyn crate::formatter::Formatter + Send + Sync>> = format.map(|fmt| {
        check_caller_info_needed(&fmt);
        let f: Arc<dyn crate::formatter::Formatter + Send + Sync> = match datefmt {
            Some(df) => Arc::new(PythonFormatter::with_date_format(fmt, df)),
            None => Arc::new(PythonFormatter::new(fmt)),
        };
        f
    });

    if let Some(stream_obj) = stream {
        // Try to extract as string first
        if let Ok(stream_str) = stream_obj.extract::<String>() {
            // String path: "stdout" or "stderr"
            let handler = match stream_str.as_str() {
                "stdout" => crate::handler::StreamHandler::stdout(),
                "stderr" => crate::handler::StreamHandler::stderr(),
                _ => {
                    return Err(PyValueError::new_err(
                        "stream string must be 'stdout' or 'stderr'",
                    ))
                }
            };
            handler.set_level(log_level);
            if let Some(ref f) = formatter {
                handler.set_formatter_instance(f.clone());
            }
            push_handler(Arc::new(handler));
        } else {
            // For Python file-like objects, we use stderr as fallback
            // since we don't have PythonStreamHandler anymore
            let handler = crate::handler::StreamHandler::stderr();
            handler.set_level(log_level);
            if let Some(ref f) = formatter {
                handler.set_formatter_instance(f.clone());
            }
            push_handler(Arc::new(handler));
        }
    } else {
        // Default to stderr
        let handler = crate::handler::StreamHandler::stderr();
        handler.set_level(log_level);
        if let Some(ref f) = formatter {
            handler.set_formatter_instance(f.clone());
        }
        push_handler(Arc::new(handler));
    }

    Ok(())
}

/// Extract the Rust `Arc<dyn Handler>` from a handler pyclass (HTTP/OTLP/Memory/File/
/// Stream/Rotating). Used on both the object itself (DIRECT pyclass) and its `_inner`
/// (public wrapper). All text-sink kinds route through rust_dispatch; the per-record
/// Native/Python decision lives on the arc's dispatch_mode flag.
fn extract_rust_arc(obj: &Bound<PyAny>) -> Option<Arc<dyn Handler + Send + Sync>> {
    if let Ok(h) = obj.extract::<PyRef<PyHTTPHandler>>() {
        Some(h.inner.clone())
    } else if let Ok(h) = obj.extract::<PyRef<PyOTLPHandler>>() {
        Some(h.inner.clone())
    } else if let Ok(h) = obj.extract::<PyRef<PyMemoryHandler>>() {
        Some(h.inner.clone())
    } else if let Ok(h) = obj.extract::<PyRef<PyFileHandler>>() {
        Some(h.inner.clone())
    } else if let Ok(h) = obj.extract::<PyRef<PyStreamHandler>>() {
        Some(h.inner.clone())
    } else if let Ok(h) = obj.extract::<PyRef<PyRotatingFileHandler>>() {
        Some(h.inner.clone())
    } else {
        None
    }
}

fn decrement_caller_info() {
    if CALLER_INFO_COUNT.load(Ordering::Relaxed) > 0 {
        let remaining = CALLER_INFO_COUNT
            .fetch_sub(1, Ordering::Relaxed)
            .saturating_sub(1);
        if remaining == 0 {
            CALLER_INFO_REQUIRED.store(false, Ordering::Relaxed);
        }
    }
}

fn register_rust_entry(
    is_root: bool,
    arc: Arc<dyn Handler + Send + Sync>,
    wrapper: Option<Py<PyAny>>,
    rust_dispatch: &Mutex<Vec<RustEntry>>,
    lifecycle: &Mutex<Vec<Arc<dyn Handler + Send + Sync>>>,
) {
    let id = arc_id(&arc);
    if is_root {
        // Root handlers live in the global HANDLERS list (Arc only). Text-sink wrappers
        // attached to root therefore dispatch natively (no per-entry wrapper is kept).
        push_handler(arc.clone());
        GLOBAL_LIFECYCLE.lock().unwrap().push(arc);
    } else {
        rust_dispatch.lock().unwrap().push(RustEntry {
            arc: arc.clone(),
            id,
            wrapper,
        });
        lifecycle.lock().unwrap().push(arc);
    }
}

/// Route a handler into the correct dispatch list by backend kind (PHASE 6).
/// A DIRECT rust pyclass (RustFileHandler etc.) -> rust_dispatch{wrapper:None}. A public
/// wrapper whose `_inner` is a rust pyclass (File/Stream/Rotating/Memory/HTTP/OTLP) ->
/// rust_dispatch{wrapper:Some(handler)} so emit_record can read the arc's dispatch_mode and
/// fall back to `wrapper.handle()` in Python mode. FOREIGN Python handlers -> py_dispatch.
/// `name == "root"` targets the global lists; otherwise the per-logger lists.
pub fn add_handler_to_registry(
    handler: &Bound<PyAny>,
    logger_name: &str,
    rust_dispatch: &Mutex<Vec<RustEntry>>,
    py_dispatch: &Mutex<Vec<PyEntry>>,
    lifecycle: &Mutex<Vec<Arc<dyn Handler + Send + Sync>>>,
) -> PyResult<bool> {
    let is_root = logger_name == "root";
    let inner = handler.getattr("_inner").ok();

    // DIRECT rust pyclass: the object itself is a handler.
    if let Some(arc) = extract_rust_arc(handler) {
        register_rust_entry(is_root, arc, None, rust_dispatch, lifecycle);
        return Ok(true);
    }

    // Public wrapper: its `_inner` is a rust pyclass.
    if let Some(arc) = inner.as_ref().and_then(extract_rust_arc) {
        register_rust_entry(
            is_root,
            arc,
            Some(handler.clone().unbind()),
            rust_dispatch,
            lifecycle,
        );
        return Ok(true);
    }

    // FOREIGN python handler.
    let needs_caller = python_handler_needs_caller(handler);
    if needs_caller {
        CALLER_INFO_COUNT.fetch_add(1, Ordering::Relaxed);
        CALLER_INFO_REQUIRED.store(true, Ordering::Relaxed);
    }
    let entry = PyEntry {
        obj: handler.clone().unbind(),
        id: handler.as_ptr() as usize,
        needs_caller,
    };
    if is_root {
        GLOBAL_PY_HANDLERS.lock().unwrap().push(entry);
    } else {
        py_dispatch.lock().unwrap().push(entry);
    }
    Ok(true)
}

/// Remove a handler by identity. Rust entries match by `_inner` Arc pointer OR by stored
/// wrapper identity. Structured/async entries have their worker shut down. Foreign Python
/// handler removal recomputes CALLER_INFO_REQUIRED.
pub fn remove_handler_from_registry(
    handler: &Bound<PyAny>,
    logger_name: &str,
    rust_dispatch: &Mutex<Vec<RustEntry>>,
    py_dispatch: &Mutex<Vec<PyEntry>>,
    lifecycle: &Mutex<Vec<Arc<dyn Handler + Send + Sync>>>,
) -> PyResult<()> {
    let is_root = logger_name == "root";
    let py_id = handler.as_ptr() as usize;
    let inner = handler.getattr("_inner").ok();
    let arc = extract_rust_arc(handler).or_else(|| inner.as_ref().and_then(extract_rust_arc));
    let arc_identity = arc.as_ref().map(arc_id);

    if is_root {
        if let Some(aid) = arc_identity {
            let current = HANDLERS.load();
            let mut kept: Vec<Arc<dyn Handler + Send + Sync>> = Vec::new();
            for h in current.iter() {
                if arc_id(h) == aid {
                    h.shutdown();
                } else {
                    kept.push(h.clone());
                }
            }
            HANDLERS.store(Arc::new(kept));
            GLOBAL_LIFECYCLE
                .lock()
                .unwrap()
                .retain(|h| arc_id(h) != aid);
        }
        GLOBAL_PY_HANDLERS.lock().unwrap().retain(|e| {
            if e.id == py_id {
                if e.needs_caller {
                    decrement_caller_info();
                }
                false
            } else {
                true
            }
        });
    } else {
        let mut removed_ids: Vec<HandlerId> = Vec::new();
        rust_dispatch.lock().unwrap().retain(|e| {
            let hit = arc_identity == Some(e.id)
                || e.wrapper
                    .as_ref()
                    .is_some_and(|w| w.as_ptr() as usize == py_id);
            if hit {
                e.arc.shutdown();
                removed_ids.push(e.id);
                false
            } else {
                true
            }
        });
        if !removed_ids.is_empty() {
            lifecycle
                .lock()
                .unwrap()
                .retain(|h| !removed_ids.contains(&arc_id(h)));
        }
        py_dispatch.lock().unwrap().retain(|e| {
            if e.id == py_id {
                if e.needs_caller {
                    decrement_caller_info();
                }
                false
            } else {
                true
            }
        });
    }
    Ok(())
}
