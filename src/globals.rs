//! Global state and utility functions for LogXide
//!
//! This module contains global registries, thread-local storage,
//! and module-level utility functions.

use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict};
use std::cell::RefCell;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use once_cell::sync::Lazy;

use crate::core::{get_logger as core_get_logger, get_root_logger, LogLevel};
use crate::fast_logger;
use crate::handler::{FileHandler, HTTPHandler, Handler, OverflowStrategy, RotatingFileHandler};
use crate::py_handlers::{
    PyFileHandler, PyHTTPHandler, PyOTLPHandler, PyRotatingFileHandler, PyStreamHandler,
};
use crate::py_logger::PyLogger;

/// Global registry of log handlers.
pub static HANDLERS: Lazy<Mutex<Vec<Arc<dyn Handler + Send + Sync>>>> =
    Lazy::new(|| Mutex::new(Vec::new()));

/// GLOBAL KEEP ALIVE to prevent Python objects from being garbage collected
pub static PYTHON_HANDLERS_KEEP_ALIVE: Lazy<Mutex<Vec<Py<PyAny>>>> =
    Lazy::new(|| Mutex::new(Vec::new()));

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
    let pylogger = PyLogger::new(
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
pub fn flush(_py: Python) -> PyResult<()> {
    let handlers = HANDLERS.lock().unwrap();
    for h in handlers.iter() {
        futures::executor::block_on(h.flush());
    }
    Ok(())
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
    HANDLERS.lock().unwrap().push(h);
    Ok(())
}

#[pyfunction]
pub fn clear_handlers(_py: Python) -> PyResult<()> {
    HANDLERS.lock().unwrap().clear();
    Ok(())
}

#[pyfunction(name = "register_file_handler")]
#[pyo3(signature = (filename, level=None))]
pub fn register_file_handler(_py: Python, filename: String, level: Option<u32>) -> PyResult<()> {
    use pyo3::exceptions::PyValueError;

    let log_level = LogLevel::from_usize(level.unwrap_or(10) as usize);

    let handler = FileHandler::new(filename)
        .map_err(|e| PyValueError::new_err(format!("Failed to create file handler: {}", e)))?;

    handler.set_level(log_level);
    HANDLERS.lock().unwrap().push(Arc::new(handler));
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
    );

    handler.set_level(log_level);
    HANDLERS.lock().unwrap().push(Arc::new(handler));
    Ok(())
}

/// Helper function to add a handler to the appropriate registry
pub fn add_handler_to_registry(
    handler: &Bound<PyAny>,
    logger_name: &str,
    local_handlers: &Mutex<Vec<Arc<dyn Handler + Send + Sync>>>,
) -> PyResult<bool> {
    let handler_arc: Option<Arc<dyn Handler + Send + Sync>> =
        if let Ok(file_handler) = handler.extract::<PyRef<PyFileHandler>>() {
            Some(file_handler.inner.clone())
        } else if let Ok(stream_handler) = handler.extract::<PyRef<PyStreamHandler>>() {
            Some(stream_handler.inner.clone())
        } else if let Ok(rotating_handler) = handler.extract::<PyRef<PyRotatingFileHandler>>() {
            Some(rotating_handler.inner.clone())
        } else if let Ok(http_handler) = handler.extract::<PyRef<PyHTTPHandler>>() {
            Some(http_handler.inner.clone())
        } else if let Ok(otlp_handler) = handler.extract::<PyRef<PyOTLPHandler>>() {
            Some(otlp_handler.inner.clone())
        } else if let Ok(inner) = handler.getattr("_inner") {
            if let Ok(file_handler) = inner.extract::<PyRef<PyFileHandler>>() {
                Some(file_handler.inner.clone())
            } else if let Ok(stream_handler) = inner.extract::<PyRef<PyStreamHandler>>() {
                Some(stream_handler.inner.clone())
            } else if let Ok(rotating_handler) = inner.extract::<PyRef<PyRotatingFileHandler>>() {
                Some(rotating_handler.inner.clone())
            } else if let Ok(http_handler) = inner.extract::<PyRef<PyHTTPHandler>>() {
                Some(http_handler.inner.clone())
            } else if let Ok(otlp_handler) = inner.extract::<PyRef<PyOTLPHandler>>() {
                Some(otlp_handler.inner.clone())
            } else {
                None
            }
        } else {
            None
        };

    if let Some(h) = handler_arc {
        if logger_name == "root" {
            HANDLERS.lock().unwrap().push(h);
        } else {
            local_handlers.lock().unwrap().push(h);
        }
        // CRITICAL: Prevent Python object from being GC'd
        PYTHON_HANDLERS_KEEP_ALIVE
            .lock()
            .unwrap()
            .push(handler.clone().unbind());
        Ok(true)
    } else {
        Ok(false)
    }
}
