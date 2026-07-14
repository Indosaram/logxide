//! PyLogger - Python-exposed logger implementation

#![allow(non_snake_case)]

use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyList, PyTuple};
use pyo3::IntoPyObjectExt;
use serde_json::Value;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use crate::core::{create_log_record_with_extra, LogLevel, LogRecord, Logger};
use crate::fast_logger::FastLogger;
use crate::globals::{
    add_handler_to_registry, remove_handler_from_registry, PyEntry, RustEntry, GLOBAL_PY_HANDLERS,
    HANDLERS,
};
use crate::handler::{DispatchMode, Handler};

/// Check and resolve a log level from either an integer or a string name.
/// Handles: int passthrough, string lookup (CRITICAL/FATAL/ERROR/WARN/WARNING/INFO/DEBUG/NOTSET).
/// Raises TypeError for unsupported types, ValueError for unknown level names.
pub fn check_level(py: Python, level: &Bound<PyAny>) -> PyResult<u32> {
    // Try int first
    if let Ok(i) = level.extract::<u32>() {
        return Ok(i);
    }
    // Try i64 for negative or large values, then cast
    if let Ok(i) = level.extract::<i64>() {
        return Ok(i as u32);
    }
    // Try string
    if let Ok(s) = level.extract::<String>() {
        let upper = s.to_uppercase();
        return match upper.as_str() {
            "CRITICAL" | "FATAL" => Ok(50),
            "ERROR" => Ok(40),
            "WARN" | "WARNING" => Ok(30),
            "INFO" => Ok(20),
            "DEBUG" => Ok(10),
            "NOTSET" => Ok(0),
            _ => {
                // Try Python-side _nameToLevel lookup for custom levels
                let compat = py.import("logxide.compat_functions")?;
                let name_to_level = compat.getattr("_nameToLevel")?;
                match name_to_level.call_method1("get", (upper.as_str(),)) {
                    Ok(val) if !val.is_none() => val.extract::<u32>(),
                    _ => Err(pyo3::exceptions::PyValueError::new_err(format!(
                        "Unknown level: '{s}'"
                    ))),
                }
            }
        };
    }
    Err(pyo3::exceptions::PyTypeError::new_err(format!(
        "Level not an integer or a valid string: {}",
        level.repr()?
    )))
}

/// Coerce a log `msg` to `String` like `str(msg)`. Exact-`str` fast path reads the
/// UTF-8 buffer directly and skips `PyObject_Str`; the exact-type check is required for
/// byte-identical output because `str` subclasses may override `__str__`.
#[inline]
fn coerce_msg_to_string(msg: &Bound<PyAny>) -> PyResult<String> {
    if msg.is_exact_instance_of::<pyo3::types::PyString>() {
        Ok(msg.cast::<pyo3::types::PyString>()?.to_string())
    } else {
        Ok(msg.str()?.to_string())
    }
}

pub fn py_to_json_value(obj: &Bound<PyAny>) -> Value {
    if obj.is_none() {
        Value::Null
    } else if let Ok(py_bool) = obj.cast::<pyo3::types::PyBool>() {
        Value::Bool(py_bool.extract::<bool>().unwrap_or(false))
    } else if let Ok(py_int) = obj.cast::<pyo3::types::PyInt>() {
        if let Ok(i) = py_int.extract::<i64>() {
            Value::Number(i.into())
        } else if let Ok(f) = py_int.extract::<f64>() {
            serde_json::Number::from_f64(f)
                .map(Value::Number)
                .unwrap_or(Value::Null)
        } else {
            Value::Null
        }
    } else if let Ok(py_float) = obj.cast::<pyo3::types::PyFloat>() {
        serde_json::Number::from_f64(py_float.value())
            .map(Value::Number)
            .unwrap_or(Value::Null)
    } else if let Ok(py_str) = obj.cast::<pyo3::types::PyString>() {
        Value::String(py_str.to_string())
    } else if let Ok(list) = obj.cast::<pyo3::types::PyList>() {
        let arr: Vec<Value> = list.iter().map(|item| py_to_json_value(&item)).collect();
        Value::Array(arr)
    } else if let Ok(tuple) = obj.cast::<pyo3::types::PyTuple>() {
        let arr: Vec<Value> = tuple.iter().map(|item| py_to_json_value(&item)).collect();
        Value::Array(arr)
    } else if let Ok(dict) = obj.cast::<pyo3::types::PyDict>() {
        let mut map = serde_json::Map::new();
        for (k, v) in dict.iter() {
            if let Ok(key) = k.str() {
                map.insert(key.to_string(), py_to_json_value(&v));
            }
        }
        Value::Object(map)
    } else if let Ok(s) = obj.str() {
        Value::String(s.to_string())
    } else {
        Value::Null
    }
}

#[pyclass(skip_from_py_object)]
pub struct PyLogger {
    pub(crate) inner: Arc<Mutex<Logger>>,
    pub(crate) fast_logger: Arc<FastLogger>,
    pub(crate) rust_dispatch: Arc<Mutex<Vec<RustEntry>>>,
    pub(crate) py_dispatch: Arc<Mutex<Vec<PyEntry>>>,
    pub(crate) lifecycle: Arc<Mutex<Vec<Arc<dyn Handler + Send + Sync>>>>,
    pub(crate) filters: Arc<Mutex<Vec<Py<PyAny>>>>,
    pub(crate) propagate: Arc<Mutex<bool>>,
    pub(crate) parent: Arc<Mutex<Option<Py<PyAny>>>>,
    pub(crate) manager: Arc<Mutex<Option<Py<PyAny>>>>,
}

impl PyLogger {
    pub fn new(name: &str) -> Self {
        let fast_logger = Arc::new(FastLogger::new(name));
        PyLogger {
            inner: Arc::new(Mutex::new(Logger::new(name))),
            fast_logger,
            rust_dispatch: Arc::new(Mutex::new(Vec::new())),
            py_dispatch: Arc::new(Mutex::new(Vec::new())),
            lifecycle: Arc::new(Mutex::new(Vec::new())),
            filters: Arc::new(Mutex::new(Vec::new())),
            propagate: Arc::new(Mutex::new(true)),
            parent: Arc::new(Mutex::new(None)),
            manager: Arc::new(Mutex::new(None)),
        }
    }

    pub fn with_params(
        inner: Arc<Mutex<Logger>>,
        fast_logger: Arc<FastLogger>,
        manager: Option<Py<PyAny>>,
    ) -> Self {
        PyLogger {
            inner,
            fast_logger,
            rust_dispatch: Arc::new(Mutex::new(Vec::new())),
            py_dispatch: Arc::new(Mutex::new(Vec::new())),
            lifecycle: Arc::new(Mutex::new(Vec::new())),
            filters: Arc::new(Mutex::new(Vec::new())),
            propagate: Arc::new(Mutex::new(true)),
            parent: Arc::new(Mutex::new(None)),
            manager: Arc::new(Mutex::new(manager)),
        }
    }
}

impl Clone for PyLogger {
    fn clone(&self) -> Self {
        PyLogger {
            inner: self.inner.clone(),
            fast_logger: self.fast_logger.clone(),
            rust_dispatch: self.rust_dispatch.clone(),
            py_dispatch: self.py_dispatch.clone(),
            lifecycle: self.lifecycle.clone(),
            filters: self.filters.clone(),
            propagate: self.propagate.clone(),
            parent: self.parent.clone(),
            manager: self.manager.clone(),
        }
    }
}

impl Drop for PyLogger {
    fn drop(&mut self) {}
}

impl PyLogger {
    fn extract_extra_fields(
        &self,
        kwargs: Option<&Bound<PyDict>>,
    ) -> Option<HashMap<String, Value>> {
        kwargs.and_then(|dict| {
            if let Ok(Some(extra_bound)) = dict.get_item("extra") {
                if let Ok(extra_dict) = extra_bound.cast::<PyDict>() {
                    let mut extra_map = HashMap::new();
                    for (key, value) in extra_dict.iter() {
                        if let Ok(key_str) = key.str() {
                            let json_value = py_to_json_value(&value);
                            extra_map.insert(key_str.to_string(), json_value);
                        }
                    }
                    return Some(extra_map);
                }
            }
            None
        })
    }

    /// Extract exc_info from kwargs and format it as traceback text.
    /// `default_exc_info`: if true, capture current exception when exc_info kwarg is absent.
    /// Handles: exc_info=True, exc_info=False, exc_info=(type, value, tb), exc_info=<exception>.
    fn extract_exc_info_text(
        &self,
        py: Python,
        kwargs: Option<&Bound<PyDict>>,
        default_exc_info: bool,
    ) -> Option<String> {
        let exc_info_val = kwargs.and_then(|dict| dict.get_item("exc_info").ok().flatten());

        match exc_info_val {
            None => {
                if !default_exc_info {
                    return None;
                }
                self.capture_current_exception(py)
            }
            Some(val) => {
                // Check if it's a tuple (type, value, tb)
                if let Ok(tuple) = val.cast::<PyTuple>() {
                    if tuple.len() == 3 {
                        let val_item = tuple.get_item(1).ok();
                        if val_item.map(|v| !v.is_none()).unwrap_or(false) {
                            return self.format_exception_tuple(py, tuple);
                        }
                    }
                    // (None, None, None) or wrong-length tuple
                    return None;
                }

                // Check if it's an exception instance
                if let Ok(base_exc) = py
                    .import("builtins")
                    .and_then(|m| m.getattr("BaseException"))
                {
                    if val.is_instance(&base_exc).unwrap_or(false) {
                        return self.format_exception_instance(py, &val);
                    }
                }

                // Otherwise check truthiness (handles True, False, 0, 1, etc.)
                if val.is_truthy().unwrap_or(false) {
                    self.capture_current_exception(py)
                } else {
                    None
                }
            }
        }
    }

    /// Extract the raw exc_info Python object from kwargs for passing to Python handlers.
    /// Returns the original (type, value, tb) tuple, sys.exc_info() result, or None.
    fn extract_exc_info_raw(
        &self,
        py: Python,
        kwargs: Option<&Bound<PyDict>>,
        default_exc_info: bool,
    ) -> Option<Py<PyAny>> {
        let exc_info_val = kwargs.and_then(|dict| dict.get_item("exc_info").ok().flatten());

        match exc_info_val {
            None => {
                if !default_exc_info {
                    return None;
                }
                // Capture current exception as sys.exc_info() tuple
                py.import("sys")
                    .and_then(|m| m.call_method0("exc_info"))
                    .ok()
                    .and_then(|info| {
                        // Check if there's an actual exception (info[1] is not None)
                        let tuple = info.cast::<PyTuple>().ok()?;
                        let val_item = tuple.get_item(1).ok()?;
                        if val_item.is_none() {
                            None
                        } else {
                            Some(info.unbind())
                        }
                    })
            }
            Some(val) => {
                // Already a tuple — pass through directly
                if let Ok(tuple) = val.cast::<PyTuple>() {
                    if tuple.len() == 3 {
                        let val_item = tuple.get_item(1).ok();
                        if val_item.map(|v| !v.is_none()).unwrap_or(false) {
                            return Some(val.unbind());
                        }
                    }
                    return None;
                }

                // Exception instance — build (type, value, tb) tuple
                if let Ok(base_exc) = py
                    .import("builtins")
                    .and_then(|m| m.getattr("BaseException"))
                {
                    if val.is_instance(&base_exc).unwrap_or(false) {
                        let exc_type = val.get_type();
                        let tb = val.getattr("__traceback__").ok();
                        let tuple = PyTuple::new(
                            py,
                            &[
                                exc_type.into_any(),
                                val.clone(),
                                tb.unwrap_or_else(|| py.None().into_bound(py)),
                            ],
                        )
                        .ok()?;
                        return Some(tuple.unbind().into());
                    }
                }

                // True → capture sys.exc_info()
                if val.is_truthy().unwrap_or(false) {
                    py.import("sys")
                        .and_then(|m| m.call_method0("exc_info"))
                        .ok()
                        .and_then(|info| {
                            let tuple = info.cast::<PyTuple>().ok()?;
                            let val_item = tuple.get_item(1).ok()?;
                            if val_item.is_none() {
                                None
                            } else {
                                Some(info.unbind())
                            }
                        })
                } else {
                    None
                }
            }
        }
    }

    /// Capture the current active exception via traceback.format_exc().
    fn capture_current_exception(&self, py: Python) -> Option<String> {
        py.import("traceback")
            .and_then(|m| m.call_method0("format_exc"))
            .map(|s| s.to_string())
            .ok()
            .filter(|s| s != "NoneType: None\n" && !s.is_empty())
    }

    /// Format a (type, value, tb) tuple into traceback text.
    fn format_exception_tuple(&self, py: Python, tuple: &Bound<PyTuple>) -> Option<String> {
        let tb_mod = py.import("traceback").ok()?;
        let formatted = tb_mod
            .call_method1(
                "format_exception",
                (
                    tuple.get_item(0).ok()?,
                    tuple.get_item(1).ok()?,
                    tuple.get_item(2).ok()?,
                ),
            )
            .ok()?;
        let empty_str = "".into_pyobject(py).ok()?;
        let joined = empty_str.call_method1("join", (&formatted,)).ok()?;
        let result = joined.to_string();
        if result.is_empty() {
            None
        } else {
            Some(result)
        }
    }

    /// Format an exception instance into traceback text.
    fn format_exception_instance(&self, py: Python, exc: &Bound<PyAny>) -> Option<String> {
        let exc_type = exc.get_type();
        let tb = exc.getattr("__traceback__").ok()?;
        let tb_mod = py.import("traceback").ok()?;
        let formatted = tb_mod
            .call_method1("format_exception", (exc_type, exc, tb))
            .ok()?;
        let empty_str = "".into_pyobject(py).ok()?;
        let joined = empty_str.call_method1("join", (&formatted,)).ok()?;
        let result = joined.to_string();
        if result.is_empty() {
            None
        } else {
            Some(result)
        }
    }

    /// Populate pathname, filename, lineno, func_name on record via Python frame introspection.
    /// Uses a cached Python helper that returns (filename, funcName, lineno) in one call,
    /// roughly halving the number of cross-language attribute lookups vs walking the frame
    /// from Rust.
    fn populate_caller_info(py: Python, record: &mut LogRecord) {
        if !crate::globals::CALLER_INFO_REQUIRED.load(std::sync::atomic::Ordering::Relaxed) {
            return;
        }

        static HELPER: std::sync::OnceLock<Py<PyAny>> = std::sync::OnceLock::new();
        let helper = match HELPER.get() {
            Some(h) => h,
            None => match py
                .import("logxide.compat_functions")
                .and_then(|m| m.getattr("_get_caller_info"))
            {
                Ok(fun) => HELPER.get_or_init(|| fun.unbind()),
                Err(_) => return,
            },
        };

        let Ok(result) = helper.call0(py) else {
            return;
        };
        let Ok((path, func_name, lineno)) = result.extract::<(String, String, u32)>(py) else {
            return;
        };

        let filename = path
            .rsplit_once(std::path::MAIN_SEPARATOR)
            .map(|(_, name)| name.to_string())
            .unwrap_or_else(|| path.clone());
        let module_name = filename
            .rsplit_once('.')
            .map(|(base, _)| base.to_string())
            .unwrap_or_else(|| filename.clone());

        record.pathname = path;
        record.filename = filename;
        record.module = module_name;
        record.func_name = func_name;
        record.lineno = lineno;
    }
}

impl PyLogger {
    fn serialize_args(&self, _py: Python, args: &Bound<PyAny>) -> Option<Arc<Value>> {
        let args_tuple = match args.cast::<PyTuple>() {
            Ok(t) if !t.is_empty() => t,
            _ => return None,
        };
        // If args is a single dict (e.g., `log("%(key)s", {"key": "v"})`) unwrap it
        // so that `msg % args` works correctly (dict, not tuple-of-dict).
        let json_val = if args_tuple.len() == 1 {
            let first = args_tuple.get_item(0).expect("Failed to get first arg");
            if first.cast::<PyDict>().is_ok() {
                py_to_json_value(&first)
            } else {
                py_to_json_value(args_tuple.as_any())
            }
        } else {
            py_to_json_value(args_tuple.as_any())
        };
        Some(Arc::new(json_val))
    }
}

impl PyLogger {
    /// Emit `record` to the Rust-backed handlers: local rust_dispatch arcs first, then the
    /// global HANDLERS when propagation is enabled. Pure Rust — shared by the attached and
    /// detached (GIL-released) paths.
    fn run_rust_dispatch(
        rust_arcs: &[Arc<dyn Handler + Send + Sync>],
        global_handlers: Option<&[Arc<dyn Handler + Send + Sync>]>,
        record: &LogRecord,
    ) {
        for arc in rust_arcs.iter() {
            arc.emit(record);
        }
        if let Some(handlers) = global_handlers {
            for handler in handlers.iter() {
                handler.emit(record);
            }
        }
    }

    /// Snapshot the per-logger rust handler arcs, the propagation decision, and whether
    /// every entry is native (so §4 detached dispatch is allowed). Releases every Mutex
    /// guard before returning so nothing is held across a later `py.detach`.
    fn dispatch_snapshot(&self) -> (Vec<Arc<dyn Handler + Send + Sync>>, bool, bool, bool) {
        let (rust_arcs, all_native): (Vec<Arc<dyn Handler + Send + Sync>>, bool) = {
            let lock = self.rust_dispatch.lock().unwrap();
            let mut arcs = Vec::with_capacity(lock.len());
            let mut all_native = true;
            for e in lock.iter() {
                if e.wrapper.is_some() && e.arc.dispatch_mode() == DispatchMode::Python {
                    all_native = false;
                }
                arcs.push(e.arc.clone());
            }
            (arcs, all_native)
        };
        let py_dispatch_empty = self.py_dispatch.lock().unwrap().is_empty();
        let has_local = !rust_arcs.is_empty() || !py_dispatch_empty;
        let dispatch_global = !has_local || *self.propagate.lock().unwrap();
        (rust_arcs, dispatch_global, py_dispatch_empty, all_native)
    }

    /// Route a fully-built record. When no Python code needs to run during dispatch
    /// (no filters, no Python-dispatch handlers, every rust entry native), the Rust handler
    /// emit runs with the GIL released so producers scale across threads (§4). Otherwise
    /// fall back to the fully-attached emit_record path (filters may mutate the record;
    /// Python-mode text-sink wrappers + py_dispatch handlers need a py_record).
    ///
    /// Caveat: %-args formatting still calls record.get_message() -> Python __mod__ under
    /// Python::attach (core.rs), so an args-bearing record re-acquires the GIL inside a Rust
    /// formatter's emit and won't fully parallelize until P1-3. No-args / pre-formatted
    /// records scale.
    fn dispatch(&self, py: Python, record: LogRecord, exc_info_py: Option<Py<PyAny>>) {
        let has_filters = !self.filters.lock().unwrap().is_empty();
        let (rust_arcs, dispatch_global, py_dispatch_empty, all_native) = self.dispatch_snapshot();
        let global_py_nonempty = !GLOBAL_PY_HANDLERS.lock().unwrap().is_empty();

        let eligible = !has_filters
            && py_dispatch_empty
            && !(dispatch_global && global_py_nonempty)
            && all_native;

        if !eligible {
            self.emit_record(record, exc_info_py);
            return;
        }

        let global_handlers = if dispatch_global {
            Some(HANDLERS.load_full())
        } else {
            None
        };
        py.detach(move || {
            let _block_scope = crate::handler::BlockWaitGuard::enter();
            PyLogger::run_rust_dispatch(
                &rust_arcs,
                global_handlers.as_deref().map(|v| v.as_slice()),
                &record,
            );
        });
    }
}

#[pymethods]
impl PyLogger {
    fn emit_record(&self, mut record: LogRecord, exc_info_py: Option<Py<PyAny>>) {
        // Filters can modify the record (especially record.msg) and return False to suppress.
        // Only enter the GIL when filters are actually present.
        let has_filters = !self.filters.lock().unwrap().is_empty();
        if has_filters {
            let should_emit = Python::attach(|py| {
                let filters: Vec<Py<PyAny>> = {
                    let lock = self.filters.lock().unwrap();
                    lock.iter().map(|f| f.clone_ref(py)).collect()
                };
                for filter_obj in filters.iter() {
                    let filter_bound = filter_obj.bind(py);

                    let result = if let Ok(filter_method) = filter_bound.getattr("filter") {
                        let py_record = pyo3::types::PyDict::new(py);
                        let _ = py_record.set_item("name", &record.name);
                        let _ = py_record.set_item("levelno", record.levelno);
                        let _ = py_record.set_item("levelname", &record.levelname);
                        let _ = py_record.set_item("msg", &record.msg);
                        let _ = py_record.set_item("pathname", &record.pathname);
                        let _ = py_record.set_item("lineno", record.lineno);
                        let _ = py_record.set_item("func_name", &record.func_name);

                        let call_result = filter_method.call1((&py_record,));

                        if let Ok(Some(new_msg)) = py_record.get_item("msg") {
                            if let Ok(msg_str) = new_msg.extract::<String>() {
                                record.msg = msg_str;
                            }
                        }

                        match call_result {
                            Ok(res) => res.is_truthy().unwrap_or(true),
                            Err(_) => true,
                        }
                    } else if filter_bound.is_callable() {
                        let py_record = pyo3::types::PyDict::new(py);
                        let _ = py_record.set_item("name", &record.name);
                        let _ = py_record.set_item("levelno", record.levelno);
                        let _ = py_record.set_item("levelname", &record.levelname);
                        let _ = py_record.set_item("msg", &record.msg);
                        let _ = py_record.set_item("pathname", &record.pathname);
                        let _ = py_record.set_item("lineno", record.lineno);
                        let _ = py_record.set_item("func_name", &record.func_name);

                        let call_result = filter_bound.call1((&py_record,));

                        if let Ok(Some(new_msg)) = py_record.get_item("msg") {
                            if let Ok(msg_str) = new_msg.extract::<String>() {
                                record.msg = msg_str;
                            }
                        }

                        match call_result {
                            Ok(res) => res.is_truthy().unwrap_or(true),
                            Err(_) => true,
                        }
                    } else {
                        true
                    };

                    if !result {
                        return false;
                    }
                }
                true
            });

            if !should_emit {
                return;
            }
        }

        // Propagation-gated dispatch. Each rust_dispatch entry emits natively unless it is
        // a text-sink wrapper flipped to Python mode (custom Formatter / {,$ style / handler
        // filter), in which case its wrapper.handle() runs once in the Python half below.
        let (native_arcs, python_wrappers, dispatch_global, py_dispatch_empty) = {
            let lock = self.rust_dispatch.lock().unwrap();
            let mut native_arcs: Vec<Arc<dyn Handler + Send + Sync>> =
                Vec::with_capacity(lock.len());
            let mut python_wrappers: Vec<Py<PyAny>> = Vec::new();
            Python::attach(|py| {
                for e in lock.iter() {
                    match &e.wrapper {
                        Some(w) if e.arc.dispatch_mode() == DispatchMode::Python => {
                            python_wrappers.push(w.clone_ref(py));
                        }
                        _ => native_arcs.push(e.arc.clone()),
                    }
                }
            });
            let py_dispatch_empty = self.py_dispatch.lock().unwrap().is_empty();
            let has_local =
                !native_arcs.is_empty() || !python_wrappers.is_empty() || !py_dispatch_empty;
            let dispatch_global = !has_local || *self.propagate.lock().unwrap();
            (
                native_arcs,
                python_wrappers,
                dispatch_global,
                py_dispatch_empty,
            )
        };

        for arc in native_arcs.iter() {
            arc.emit(&record);
        }
        if dispatch_global {
            let global = HANDLERS.load_full();
            for handler in global.iter() {
                handler.emit(&record);
            }
        }

        let global_py_nonempty = !GLOBAL_PY_HANDLERS.lock().unwrap().is_empty();
        let need_py = !python_wrappers.is_empty()
            || !py_dispatch_empty
            || (dispatch_global && global_py_nonempty);
        if !need_py {
            return;
        }

        Python::attach(|py| {
            let local_py_handlers: Vec<Py<PyAny>> = {
                let lock = self.py_dispatch.lock().unwrap();
                lock.iter().map(|e| e.obj.clone_ref(py)).collect()
            };

            let py_record = match self.makeRecord(
                py,
                record.name.clone(),
                record.levelno,
                record.pathname.clone(),
                record.lineno as i32,
                record
                    .get_message()
                    .into_py_any(py)
                    .expect("Failed to convert getMessage to PyAny")
                    .into(),
                py.None().into(),
                exc_info_py.as_ref().map(|e| e.clone_ref(py)),
            ) {
                Ok(r) => r,
                Err(_) => {
                    return;
                }
            };

            if let Some(ref exc_text) = record.exc_text {
                let _ = py_record.bind(py).setattr("exc_text", exc_text.as_str());
            }

            if !record.func_name.is_empty() {
                let _ = py_record
                    .bind(py)
                    .setattr("func_name", record.func_name.as_str());
                let _ = py_record
                    .bind(py)
                    .setattr("funcName", record.func_name.as_str());
            }

            // Python-mode text-sink wrappers (local): one handle() each.
            for wrapper in python_wrappers.iter() {
                let _ = wrapper.bind(py).call_method1("handle", (&py_record,));
            }

            for handler in local_py_handlers.iter() {
                let b_handler = handler.bind(py);
                let _ = b_handler.call_method1("handle", (&py_record,));
            }

            if dispatch_global {
                let global_py_handlers: Vec<Py<PyAny>> = {
                    let lock = GLOBAL_PY_HANDLERS.lock().unwrap();
                    lock.iter().map(|e| e.obj.clone_ref(py)).collect()
                };
                for handler in global_py_handlers.iter() {
                    let b_handler = handler.bind(py);
                    let _ = b_handler.call_method1("handle", (&py_record,));
                }
            }
        });
    }

    #[getter]
    fn name(&self) -> PyResult<String> {
        Ok(self.fast_logger.name.to_string())
    }

    #[getter]
    fn level(&self) -> PyResult<u32> {
        Ok(self.fast_logger.get_level() as u32)
    }

    #[getter]
    fn handlers(&self, py: Python) -> PyResult<Py<PyAny>> {
        Ok(PyList::empty(py).into())
    }

    #[setter]
    fn set_handlers(&self, _handlers: Py<PyAny>) -> PyResult<()> {
        Ok(())
    }

    #[getter]
    fn disabled(&self) -> PyResult<bool> {
        Ok(false)
    }

    #[getter]
    fn propagate(&self) -> PyResult<bool> {
        let propagate = self.propagate.lock().unwrap();
        Ok(*propagate)
    }

    #[setter]
    fn set_propagate(&self, value: bool) -> PyResult<()> {
        let mut propagate = self.propagate.lock().unwrap();
        *propagate = value;
        Ok(())
    }

    #[getter]
    fn parent(&self, py: Python) -> PyResult<Option<Py<PyAny>>> {
        let parent_lock = self.parent.lock().unwrap();
        Ok(parent_lock.as_ref().map(|p| p.clone_ref(py)))
    }

    #[setter]
    fn set_parent(&self, value: Option<Py<PyAny>>) -> PyResult<()> {
        let mut parent = self.parent.lock().unwrap();
        *parent = value;
        Ok(())
    }

    #[getter]
    fn manager(&self, py: Python) -> PyResult<Option<Py<PyAny>>> {
        let manager_lock = self.manager.lock().unwrap();
        Ok(manager_lock.as_ref().map(|m| m.clone_ref(py)))
    }

    #[setter]
    fn set_manager(&self, value: Option<Py<PyAny>>) -> PyResult<()> {
        let mut manager = self.manager.lock().unwrap();
        *manager = value;
        Ok(())
    }

    #[getter]
    fn root(&self, py: Python) -> PyResult<PyLogger> {
        crate::globals::get_logger(py, Some("root"), None)
    }

    fn filter(&self, record: Py<PyAny>) -> PyResult<bool> {
        Python::attach(|py| {
            let record_bound = record.bind(py);
            let rust_record = record_bound.extract::<LogRecord>()?;
            let inner_logger = self.inner.lock().unwrap();
            for filter in &inner_logger.filters {
                if !filter.filter(&rust_record) {
                    return Ok(false);
                }
            }
            Ok(true)
        })
    }

    fn setLevel(&mut self, py: Python, level: &Bound<PyAny>) -> PyResult<()> {
        let level_int = check_level(py, level)?;
        let level = LogLevel::from_usize(level_int as usize);
        self.fast_logger.set_level(level);
        self.inner.lock().unwrap().set_level(level);
        crate::fast_logger::propagate_all_effective_levels();
        Ok(())
    }

    fn getEffectiveLevel(&self) -> PyResult<u32> {
        Ok(self.fast_logger.get_effective_level())
    }

    fn addHandler(&self, _py: Python, handler: &Bound<PyAny>) -> PyResult<()> {
        add_handler_to_registry(
            handler,
            &self.fast_logger.name,
            &self.rust_dispatch,
            &self.py_dispatch,
            &self.lifecycle,
        )?;

        Ok(())
    }

    fn removeHandler(&self, _py: Python, handler: &Bound<PyAny>) -> PyResult<()> {
        remove_handler_from_registry(
            handler,
            &self.fast_logger.name,
            &self.rust_dispatch,
            &self.py_dispatch,
            &self.lifecycle,
        )
    }

    /// Add a filter to this logger.
    /// The filter can be:
    /// - An object with a `filter(record)` method that returns True/False
    /// - A callable that takes a record dict and returns True/False
    ///
    /// The record dict has keys: name, levelno, levelname, msg, pathname, lineno, func_name
    /// Filters can modify record['msg'] to transform the log message.
    fn addFilter(&self, py: Python, filter_obj: Py<PyAny>) -> PyResult<()> {
        let mut filters = self.filters.lock().unwrap();
        filters.push(filter_obj.clone_ref(py));
        Ok(())
    }

    /// Remove a filter from this logger.
    fn removeFilter(&self, py: Python, filter_obj: &Bound<PyAny>) -> PyResult<()> {
        let mut filters = self.filters.lock().unwrap();
        filters.retain(|f| !f.bind(py).is(filter_obj));
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn debug(
        &self,
        py: Python,
        msg: Py<PyAny>,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Debug) {
            return Ok(());
        }
        let extra_fields = self.extract_extra_fields(kwargs);
        let msg_str = coerce_msg_to_string(msg.bind(py))?;
        let serialized_args = self.serialize_args(py, args);
        let mut record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Debug,
            msg_str,
            extra_fields,
        );
        PyLogger::populate_caller_info(py, &mut record);
        record.args = serialized_args;
        record.exc_text = self.extract_exc_info_text(py, kwargs, false);
        let exc_info_py = self.extract_exc_info_raw(py, kwargs, false);
        self.dispatch(py, record, exc_info_py);
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn info(
        &self,
        py: Python,
        msg: Py<PyAny>,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Info) {
            return Ok(());
        }
        let extra_fields = self.extract_extra_fields(kwargs);
        let msg_str = coerce_msg_to_string(msg.bind(py))?;
        let serialized_args = self.serialize_args(py, args);
        let mut record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Info,
            msg_str,
            extra_fields,
        );
        PyLogger::populate_caller_info(py, &mut record);
        record.args = serialized_args;
        record.exc_text = self.extract_exc_info_text(py, kwargs, false);
        let exc_info_py = self.extract_exc_info_raw(py, kwargs, false);
        self.dispatch(py, record, exc_info_py);
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn warning(
        &self,
        py: Python,
        msg: Py<PyAny>,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Warning) {
            return Ok(());
        }
        let extra_fields = self.extract_extra_fields(kwargs);
        let msg_str = coerce_msg_to_string(msg.bind(py))?;
        let serialized_args = self.serialize_args(py, args);
        let mut record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Warning,
            msg_str,
            extra_fields,
        );
        PyLogger::populate_caller_info(py, &mut record);
        record.args = serialized_args;
        record.exc_text = self.extract_exc_info_text(py, kwargs, false);
        let exc_info_py = self.extract_exc_info_raw(py, kwargs, false);
        self.dispatch(py, record, exc_info_py);
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn error(
        &self,
        py: Python,
        msg: Py<PyAny>,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Error) {
            return Ok(());
        }
        let extra_fields = self.extract_extra_fields(kwargs);
        let msg_str = coerce_msg_to_string(msg.bind(py))?;
        let serialized_args = self.serialize_args(py, args);
        let mut record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Error,
            msg_str,
            extra_fields,
        );
        PyLogger::populate_caller_info(py, &mut record);
        record.args = serialized_args;
        record.exc_text = self.extract_exc_info_text(py, kwargs, false);
        let exc_info_py = self.extract_exc_info_raw(py, kwargs, false);
        self.dispatch(py, record, exc_info_py);
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn critical(
        &self,
        py: Python,
        msg: Py<PyAny>,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Critical) {
            return Ok(());
        }
        let extra_fields = self.extract_extra_fields(kwargs);
        let msg_str = coerce_msg_to_string(msg.bind(py))?;
        let serialized_args = self.serialize_args(py, args);
        let mut record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Critical,
            msg_str,
            extra_fields,
        );
        PyLogger::populate_caller_info(py, &mut record);
        record.args = serialized_args;
        record.exc_text = self.extract_exc_info_text(py, kwargs, false);
        let exc_info_py = self.extract_exc_info_raw(py, kwargs, false);
        self.dispatch(py, record, exc_info_py);
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn exception(
        &self,
        py: Python,
        msg: Py<PyAny>,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Error) {
            return Ok(());
        }
        let extra_fields = self.extract_extra_fields(kwargs);
        let msg_str = coerce_msg_to_string(msg.bind(py))?;
        let serialized_args = self.serialize_args(py, args);
        let mut record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Error,
            msg_str,
            extra_fields,
        );
        PyLogger::populate_caller_info(py, &mut record);
        record.args = serialized_args;
        record.exc_text = self.extract_exc_info_text(py, kwargs, true);
        let exc_info_py = self.extract_exc_info_raw(py, kwargs, true);
        self.dispatch(py, record, exc_info_py);
        Ok(())
    }

    #[pyo3(signature = (level, msg, *args, **kwargs))]
    fn log(
        &self,
        py: Python,
        level: u32,
        msg: Py<PyAny>,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        let log_level = LogLevel::from_usize(level as usize);
        if !self.fast_logger.is_enabled_for(log_level) {
            return Ok(());
        }
        let extra_fields = self.extract_extra_fields(kwargs);
        let msg_str = coerce_msg_to_string(msg.bind(py))?;
        let serialized_args = self.serialize_args(py, args);
        let mut record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            log_level,
            msg_str,
            extra_fields,
        );
        PyLogger::populate_caller_info(py, &mut record);
        record.args = serialized_args;
        record.exc_text = self.extract_exc_info_text(py, kwargs, false);
        let exc_info_py = self.extract_exc_info_raw(py, kwargs, false);
        self.dispatch(py, record, exc_info_py);
        Ok(())
    }

    #[pyo3(signature = (name, level, fn_, lno, msg, args, exc_info=None))]
    fn makeRecord(
        &self,
        py: Python,
        name: String,
        level: i32,
        fn_: String,
        lno: i32,
        msg: Py<PyAny>,
        args: Py<PyAny>,
        exc_info: Option<Py<PyAny>>,
    ) -> PyResult<Py<PyAny>> {
        let logging = py.import("logging")?;
        let log_record_cls = logging.getattr("LogRecord")?;

        // Standard LogRecord constructor:
        // name, level, pathname, lineno, msg, args, exc_info, func=None, sinfo=None
        let args_tuple = (
            name,
            level,
            fn_,
            lno,
            msg,
            args,
            exc_info,
            py.None(), // func
            py.None(), // sinfo
        );

        let record = log_record_cls.call1(args_tuple)?;
        Ok(record.unbind())
    }

    fn handle(&self, record: Py<PyAny>) -> PyResult<()> {
        Python::attach(|py| {
            let handlers: Vec<Py<PyAny>> = {
                let lock = GLOBAL_PY_HANDLERS.lock().unwrap();
                lock.iter().map(|e| e.obj.clone_ref(py)).collect()
            };
            for handler in handlers.iter() {
                let _ = handler.call_method1(py, "handle", (record.clone_ref(py),));
            }
        });
        Ok(())
    }

    fn callHandlers(&self, record: Py<PyAny>) -> PyResult<()> {
        self.handle(record)
    }

    #[pyo3(signature = (suffix))]
    fn getChild(slf: PyRef<Self>, py: Python, suffix: &str) -> PyResult<PyLogger> {
        let logger_name = if slf.fast_logger.name.is_empty() {
            suffix.to_string()
        } else {
            format!("{}.{}", slf.fast_logger.name, suffix)
        };
        crate::globals::get_logger(py, Some(&logger_name), None)
    }

    #[pyo3(signature = (level))]
    fn isEnabledFor(&self, level: u32) -> PyResult<bool> {
        Ok(self
            .fast_logger
            .is_enabled_for(LogLevel::from_usize(level as usize)))
    }
}
