//! # LogXide
//!
//! A high-performance logging library for Python, implemented in Rust.
//! LogXide provides a drop-in replacement for Python's standard logging module
//! with asynchronous processing capabilities and enhanced performance.

#![allow(non_snake_case)]

use pyo3::exceptions::PyValueError;
#[allow(deprecated)]
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyModule};
use std::sync::{Arc, Mutex};

mod config;
pub mod core;
mod fast_logger;
mod filter;
pub mod formatter;
pub mod handler;
mod string_cache;

// Pure Rust implementations (for testing)
#[cfg(test)]
mod concurrency_pure;
#[cfg(test)]
mod core_pure;
#[cfg(test)]
mod formatter_pure;

use std::cell::RefCell;

use core::{
    create_log_record_with_extra, get_logger as core_get_logger, get_root_logger, LogLevel,
    LogRecord, Logger,
};
use handler::{ConsoleHandler, Handler, PythonHandler, RotatingFileHandler};

use crossbeam::channel::{self, Receiver as CrossbeamReceiver, Sender as CrossbeamSender};
use once_cell::sync::Lazy;
use tokio::runtime::Runtime;
use tokio::sync::oneshot;

/// Global Tokio runtime for async logging operations.
///
/// This runtime handles all asynchronous log processing in a dedicated thread pool,
/// ensuring that logging operations don't block the main application threads.
static RUNTIME: Lazy<Runtime> = Lazy::new(|| {
    tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()
        .expect("Failed to create Tokio runtime")
});

/// Message types for communication with the async logging system.
///
/// The logging system uses a message-passing architecture where log records
/// and control messages are sent through a channel to be processed asynchronously.
enum LogMessage {
    /// A log record to be processed by registered handlers
    Record(Box<LogRecord>),
    /// A flush request with a completion signal
    #[allow(dead_code)]
    Flush(oneshot::Sender<()>),
}

/// Global sender for log messages to the async processing system.
///
/// This channel is unbounded using crossbeam for better performance.
/// Messages are processed by a background task spawned in the global RUNTIME.
static SENDER: Lazy<CrossbeamSender<LogMessage>> = Lazy::new(|| {
    let (sender, receiver): (CrossbeamSender<LogMessage>, CrossbeamReceiver<LogMessage>) =
        channel::unbounded();

    // Spawn background task for processing log messages
    RUNTIME.spawn(async move {
        while let Ok(message) = receiver.recv() {
            match message {
                LogMessage::Record(record) => {
                    // Dispatch to all registered handlers synchronously
                    // No per-handler task spawning to reduce overhead
                    let handlers = HANDLERS.lock().unwrap().clone();
                    for handler in handlers.iter() {
                        handler.emit(&record).await;
                    }
                }
                LogMessage::Flush(sender) => {
                    // Send completion signal
                    let _ = sender.send(());
                }
            }
        }
    });
    sender
});

/// Global registry of log handlers.
///
/// All registered handlers receive copies of log records for processing.
/// Handlers are executed concurrently in the async runtime for maximum performance.
static HANDLERS: Lazy<Mutex<Vec<Arc<dyn Handler + Send + Sync>>>> =
    Lazy::new(|| Mutex::new(Vec::new()));

thread_local! {
    static THREAD_NAME: RefCell<Option<String>> = const { RefCell::new(None) };
}

/// Python-exposed Logger class that wraps the Rust Logger implementation.
///
/// This class provides the Python logging API while delegating the actual
/// logging work to the high-performance Rust implementation. It maintains
/// compatibility with Python's logging module interface.
///
/// # Thread Safety
///
/// PyLogger is thread-safe and can be used from multiple Python threads
/// simultaneously. The underlying Rust Logger is protected by a Mutex.
#[pyclass]
pub struct PyLogger {
    /// The underlying Rust logger implementation
    inner: Arc<Mutex<Logger>>,
    /// Fast logger for atomic level checking
    fast_logger: Arc<fast_logger::FastLogger>,
    /// Python handler objects for compatibility
    handlers: Arc<Mutex<Vec<PyObject>>>,
    /// Propagate flag for hierarchy support
    propagate: Arc<Mutex<bool>>,
    /// Parent logger for hierarchy
    parent: Arc<Mutex<Option<PyObject>>>,
    /// Manager reference for compatibility
    manager: Arc<Mutex<Option<PyObject>>>,
}

impl Clone for PyLogger {
    fn clone(&self) -> Self {
        PyLogger {
            inner: self.inner.clone(),
            fast_logger: self.fast_logger.clone(),
            handlers: self.handlers.clone(),
            propagate: self.propagate.clone(),
            parent: self.parent.clone(),
            manager: self.manager.clone(),
        }
    }
}

#[pymethods]
impl PyLogger {
    /// Extract the 'extra' parameter from kwargs and convert to HashMap<String, String>
    fn extract_extra_fields(
        &self,
        kwargs: Option<&Bound<PyDict>>,
    ) -> Option<std::collections::HashMap<String, String>> {
        kwargs.and_then(|dict| {
            if let Ok(Some(extra_bound)) = dict.get_item("extra") {
                if let Ok(extra_dict) = extra_bound.downcast::<pyo3::types::PyDict>() {
                    let mut extra_map = std::collections::HashMap::new();
                    for (key, value) in extra_dict.iter() {
                        if let (Ok(key_str), Ok(value_str)) = (key.str(), value.str()) {
                            extra_map.insert(key_str.to_string(), value_str.to_string());
                        }
                    }
                    return Some(extra_map);
                }
            }
            None
        })
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
    fn handlers(&self, py: Python) -> PyResult<PyObject> {
        // Return current handlers list as a Python list
        let handlers = self.handlers.lock().unwrap();
        let py_list = pyo3::types::PyList::empty(py);
        for handler in handlers.iter() {
            py_list.append(handler)?;
        }
        Ok(py_list.into())
    }

    #[setter]
    fn set_handlers(&self, handlers: PyObject) -> PyResult<()> {
        // Allow setting handlers for compatibility with libraries like uvicorn
        let mut current_handlers = self.handlers.lock().unwrap();
        current_handlers.clear();

        Python::with_gil(|py| {
            let handlers_ref = handlers.bind(py);

            // Handle both list and single handler cases
            if let Ok(list) = handlers_ref.downcast::<pyo3::types::PyList>() {
                for item in list.iter() {
                    current_handlers.push(item.unbind());
                }
            } else {
                // Single handler case
                current_handlers.push(handlers);
            }
            Ok(())
        })
    }

    #[getter]
    fn disabled(&self) -> PyResult<bool> {
        // Return false - logger is not disabled
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
    fn parent(&self, py: Python) -> PyResult<Option<PyObject>> {
        let parent_lock = self.parent.lock().unwrap();
        Ok(parent_lock.as_ref().map(|p| p.clone_ref(py)))
    }

    #[setter]
    fn set_parent(&self, value: Option<PyObject>) -> PyResult<()> {
        let mut parent = self.parent.lock().unwrap();
        *parent = value;
        Ok(())
    }

    #[getter]
    fn manager(&self, py: Python) -> PyResult<Option<PyObject>> {
        let manager_lock = self.manager.lock().unwrap();
        Ok(manager_lock.as_ref().map(|m| m.clone_ref(py)))
    }

    #[setter]
    fn set_manager(&self, value: Option<PyObject>) -> PyResult<()> {
        let mut manager = self.manager.lock().unwrap();
        *manager = value;
        Ok(())
    }

    #[getter]
    fn root(&self, py: Python) -> PyResult<PyLogger> {
        get_logger(py, Some("root"), None)
    }

    fn filter(&self, record: PyObject) -> PyResult<bool> {
        Python::with_gil(|py| {
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

    #[allow(non_snake_case)]
    fn setLevel(&mut self, level: u32) -> PyResult<()> {
        let level = LogLevel::from_usize(level as usize);
        self.fast_logger.set_level(level);
        // Also update the inner logger for compatibility
        self.inner.lock().unwrap().set_level(level);
        Ok(())
    }

    #[allow(non_snake_case)]
    fn getEffectiveLevel(&self) -> PyResult<u32> {
        Ok(self.fast_logger.get_level() as u32)
    }

    #[allow(non_snake_case)]
    fn addHandler(&mut self, _py: Python, handler: &Bound<PyAny>) -> PyResult<()> {
        // Wrap the Python callable as a PythonHandler and register globally
        if !handler.is_callable() {
            return Err(PyValueError::new_err("Handler must be callable"));
        }
        // Use a simple counter for handler identity
        static HANDLER_COUNTER: std::sync::atomic::AtomicUsize =
            std::sync::atomic::AtomicUsize::new(0);
        let handler_id = HANDLER_COUNTER.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
        let py_handler = PythonHandler::with_id(handler.clone().unbind(), handler_id);
        HANDLERS.lock().unwrap().push(Arc::new(py_handler));
        Ok(())
    }

    /// Format a log message with arguments using Python string formatting
    fn format_message(&self, py: Python, msg: PyObject, args: &Bound<PyAny>) -> PyResult<String> {
        let msg_str = msg.bind(py);

        // Convert args tuple to a vector of PyObject
        if let Ok(args_tuple) = args.downcast::<pyo3::types::PyTuple>() {
            if args_tuple.len() > 0 {
                // Use Python's % operator for formatting
                let formatted = msg_str.call_method1("__mod__", (args_tuple,))?;
                return Ok(formatted.str()?.to_string());
            }
        }

        // No args or not a tuple, just convert message to string
        Ok(msg_str.str()?.to_string())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    #[allow(deprecated)]
    fn debug(
        &self,
        py: Python,
        msg: PyObject,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        // Fast atomic level check - no lock needed
        if !self.fast_logger.is_enabled_for(LogLevel::Debug) {
            return Ok(());
        }

        // Extract extra fields from kwargs
        let extra_fields = self.extract_extra_fields(kwargs);

        // Only create record if level is enabled - format message with args
        let formatted_msg = self
            .format_message(py, msg.clone_ref(py), args)
            .unwrap_or_else(|_| "".to_string());
        let record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Debug,
            formatted_msg,
            extra_fields,
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
        if *self.propagate.lock().unwrap() {
            if let Some(parent_obj) = self.parent.lock().unwrap().as_ref() {
                Python::with_gil(|py| {
                    let parent_logger = parent_obj.extract::<PyLogger>(py)?;
                    parent_logger.debug(py, msg.clone_ref(py), args, kwargs)?;
                    Ok::<(), PyErr>(())
                })?;
            }
        }
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    #[allow(deprecated)]
    fn info(
        &self,
        py: Python,
        msg: PyObject,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Info) {
            return Ok(());
        }

        // Extract extra fields from kwargs
        let extra_fields = self.extract_extra_fields(kwargs);

        let formatted_msg = self
            .format_message(py, msg.clone_ref(py), args)
            .unwrap_or_else(|_| "".to_string());
        let record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Info,
            formatted_msg,
            extra_fields,
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
        if *self.propagate.lock().unwrap() {
            if let Some(parent_obj) = self.parent.lock().unwrap().as_ref() {
                Python::with_gil(|py| {
                    let parent_logger = parent_obj.extract::<PyLogger>(py)?;
                    parent_logger.info(py, msg.clone_ref(py), args, kwargs)?;
                    Ok::<(), PyErr>(())
                })?;
            }
        }
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    #[allow(deprecated)]
    fn warning(
        &self,
        py: Python,
        msg: PyObject,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Warning) {
            return Ok(());
        }

        // Extract extra fields from kwargs
        let extra_fields = self.extract_extra_fields(kwargs);

        let formatted_msg = self
            .format_message(py, msg.clone_ref(py), args)
            .unwrap_or_else(|_| "".to_string());
        let record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Warning,
            formatted_msg,
            extra_fields,
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
        if *self.propagate.lock().unwrap() {
            if let Some(parent_obj) = self.parent.lock().unwrap().as_ref() {
                Python::with_gil(|py| {
                    let parent_logger = parent_obj.extract::<PyLogger>(py)?;
                    parent_logger.warning(py, msg.clone_ref(py), args, kwargs)?;
                    Ok::<(), PyErr>(())
                })?;
            }
        }
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    #[allow(deprecated)]
    fn error(
        &self,
        py: Python,
        msg: PyObject,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Error) {
            return Ok(());
        }

        // Extract extra fields from kwargs
        let extra_fields = self.extract_extra_fields(kwargs);

        let formatted_msg = self
            .format_message(py, msg.clone_ref(py), args)
            .unwrap_or_else(|_| "".to_string());
        let record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Error,
            formatted_msg,
            extra_fields,
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
        if *self.propagate.lock().unwrap() {
            if let Some(parent_obj) = self.parent.lock().unwrap().as_ref() {
                Python::with_gil(|py| {
                    let parent_logger = parent_obj.extract::<PyLogger>(py)?;
                    parent_logger.error(py, msg.clone_ref(py), args, kwargs)?;
                    Ok::<(), PyErr>(())
                })?;
            }
        }
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn critical(
        &self,
        py: Python,
        msg: PyObject,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Critical) {
            return Ok(());
        }

        // Extract extra fields from kwargs
        let extra_fields = self.extract_extra_fields(kwargs);

        let formatted_msg = self
            .format_message(py, msg.clone_ref(py), args)
            .unwrap_or_else(|_| "".to_string());
        let record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Critical,
            formatted_msg,
            extra_fields,
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
        if *self.propagate.lock().unwrap() {
            if let Some(parent_obj) = self.parent.lock().unwrap().as_ref() {
                Python::with_gil(|py| {
                    let parent_logger = parent_obj.extract::<PyLogger>(py)?;
                    parent_logger.critical(py, msg.clone_ref(py), args, kwargs)?;
                    Ok::<(), PyErr>(())
                })?;
            }
        }
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn fatal(
        &self,
        py: Python,
        msg: PyObject,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        self.critical(py, msg.clone_ref(py), args, kwargs)
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn warn(
        &self,
        py: Python,
        msg: PyObject,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        self.warning(py, msg.clone_ref(py), args, kwargs)
    }

    #[getter]
    fn filters(&self) -> PyResult<Vec<PyObject>> {
        Ok(Vec::new())
    }

    #[allow(non_snake_case)]
    fn hasHandlers(&self) -> PyResult<bool> {
        Ok(!self.handlers.lock().unwrap().is_empty())
    }

    #[allow(non_snake_case)]
    fn getChildren(&self) -> PyResult<Vec<PyObject>> {
        Ok(Vec::new())
    }

    #[allow(non_snake_case)]
    #[allow(deprecated)]
    #[allow(clippy::too_many_arguments)]
    fn makeRecord(
        &self,
        py: Python,
        name: String,
        level: i32,
        fn_: String,
        lno: i32,
        msg: PyObject,
        args: PyObject,
        exc_info: Option<PyObject>,
    ) -> PyResult<PyObject> {
        let record = py.import("logging")?.call_method0("makeLogRecord")?;
        record.setattr("name", name)?;
        record.setattr("levelno", level)?;
        record.setattr("pathname", fn_)?;
        record.setattr("lineno", lno)?;
        record.setattr("msg", msg)?;
        record.setattr("args", args)?;
        record.setattr("exc_info", exc_info)?;
        Ok(record.to_object(py))
    }

    fn handle(&self, record: PyObject) -> PyResult<()> {
        Python::with_gil(|py| {
            let handlers = self.handlers.lock().unwrap();
            for handler in handlers.iter() {
                let _ = handler.call_method1(py, "handle", (record.clone_ref(py),));
            }
        });
        Ok(())
    }

    #[allow(non_snake_case)]
    fn findCaller(
        &self,
        _stack_info: Option<bool>,
    ) -> PyResult<(String, u32, String, Option<String>)> {
        Ok(("filename".to_string(), 0, "funcname".to_string(), None))
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn exception(
        &self,
        py: Python,
        msg: PyObject,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        if !self.fast_logger.is_enabled_for(LogLevel::Error) {
            return Ok(());
        }

        // Extract extra fields from kwargs
        let extra_fields = self.extract_extra_fields(kwargs);

        let mut formatted_msg = self
            .format_message(py, msg.clone_ref(py), args)
            .unwrap_or_else(|_| "".to_string());

        let traceback = py
            .import("traceback")
            .and_then(|m| m.call_method0("format_exc"))
            .map(|s| s.to_string())
            .unwrap_or_else(|_| "No traceback available".to_string());

        formatted_msg.push('\n');
        formatted_msg.push_str(&traceback);

        let record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Error,
            formatted_msg,
            extra_fields,
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
        if *self.propagate.lock().unwrap() {
            if let Some(parent_obj) = self.parent.lock().unwrap().as_ref() {
                Python::with_gil(|py| {
                    let parent_logger = parent_obj.extract::<PyLogger>(py)?;
                    parent_logger.exception(py, msg.clone_ref(py), args, kwargs)?;
                    Ok::<(), PyErr>(())
                })?;
            }
        }
        Ok(())
    }

    // Add compatibility methods that third-party libraries might expect
    #[allow(non_snake_case)]
    fn isEnabledFor(&self, level: u32) -> PyResult<bool> {
        let level = LogLevel::from_usize(level as usize);
        Ok(self.fast_logger.is_enabled_for(level))
    }

    #[allow(non_snake_case)]
    fn removeHandler(&self, _handler: &Bound<PyAny>) -> PyResult<()> {
        // For compatibility - logxide manages handlers globally
        Ok(())
    }

    #[allow(non_snake_case)]
    fn addFilter(&self, _filter: &Bound<PyAny>) -> PyResult<()> {
        // For compatibility - not implemented yet
        Ok(())
    }

    #[allow(non_snake_case)]
    fn removeFilter(&self, _filter: &Bound<PyAny>) -> PyResult<()> {
        // For compatibility - not implemented yet
        Ok(())
    }

    fn disable(&self, _level: u32) -> PyResult<()> {
        // For compatibility - disable functionality not implemented
        Ok(())
    }

    #[pyo3(signature = (level, msg, *args, **kwargs))]
    fn log(
        &self,
        py: Python,
        level: u32,
        msg: PyObject,
        args: &Bound<PyAny>,
        kwargs: Option<&Bound<PyDict>>,
    ) -> PyResult<()> {
        let log_level = LogLevel::from_usize(level as usize);

        // Fast atomic level check
        if !self.fast_logger.is_enabled_for(log_level) {
            return Ok(());
        }

        // Extract extra fields from kwargs
        let extra_fields = self.extract_extra_fields(kwargs);

        let formatted_msg = self
            .format_message(py, msg.clone_ref(py), args)
            .unwrap_or_else(|_| "".to_string());
        let record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            log_level,
            formatted_msg,
            extra_fields,
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
        if *self.propagate.lock().unwrap() {
            if let Some(parent_obj) = self.parent.lock().unwrap().as_ref() {
                Python::with_gil(|py| {
                    let parent_logger = parent_obj.extract::<PyLogger>(py)?;
                    parent_logger.log(py, level, msg.clone_ref(py), args, kwargs)?;
                    Ok::<(), PyErr>(())
                })?;
            }
        }
        Ok(())
    }

    #[allow(non_snake_case)]
    #[allow(deprecated)]
    fn getChild(slf: PyRef<Self>, py: Python, suffix: &str) -> PyResult<PyLogger> {
        // Create a child logger
        let logger_name = if slf.fast_logger.name.is_empty() {
            suffix.to_string()
        } else {
            format!("{}.{}", slf.fast_logger.name, suffix)
        };
        let child_logger = core_get_logger(&logger_name);
        let child_fast_logger = fast_logger::get_fast_logger(&logger_name);
        Ok(PyLogger {
            inner: child_logger,
            fast_logger: child_fast_logger,
            handlers: Arc::new(Mutex::new(Vec::new())),
            propagate: Arc::new(Mutex::new(true)), // Default to true like Python logging
            parent: Arc::new(Mutex::new(Some(slf.into_py(py)))),
            manager: Arc::new(Mutex::new(None)),
        })
    }
}

/// Python module definition for logxide.
#[pymodule]
fn logxide(_py: Python, m: &Bound<'_, pyo3::types::PyModule>) -> PyResult<()> {
    // Create the logging submodule that Python wrapper expects
    let logging_module = PyModule::new(m.py(), "logging")?;
    logging_module.add_class::<PyLogger>()?;
    logging_module.add_class::<LogRecord>()?;
    logging_module.add_function(wrap_pyfunction!(get_logger, &logging_module)?)?;
    logging_module.add_function(wrap_pyfunction!(basicConfig, &logging_module)?)?;
    logging_module.add_function(wrap_pyfunction!(flush, &logging_module)?)?;
    logging_module.add_function(wrap_pyfunction!(register_python_handler, &logging_module)?)?;
    logging_module.add_function(wrap_pyfunction!(set_thread_name, &logging_module)?)?;

    // Add the logging submodule to the main module
    m.add_submodule(&logging_module)?;

    // Also add to the main module for direct access
    m.add_class::<PyLogger>()?;
    m.add_class::<LogRecord>()?;
    m.add_function(wrap_pyfunction!(get_logger, m)?)?;
    m.add_function(wrap_pyfunction!(basicConfig, m)?)?;
    m.add_function(wrap_pyfunction!(flush, m)?)?;
    m.add_function(wrap_pyfunction!(register_python_handler, m)?)?;
    m.add_function(wrap_pyfunction!(set_thread_name, m)?)?;

    // Add pure Rust handler registration functions for 100% Rust processing
    m.add_function(wrap_pyfunction!(register_console_handler, m)?)?;
    m.add_function(wrap_pyfunction!(register_file_handler, m)?)?;

    Ok(())
}

/// Get a logger by name, mirroring Python's `logging.getLogger()`.
#[pyfunction(name = "getLogger")]
#[pyo3(signature = (name = None, manager = None))]
fn get_logger(py: Python, name: Option<&str>, manager: Option<PyObject>) -> PyResult<PyLogger> {
    let logger_name = name.unwrap_or("root");
    let logger = match name {
        Some(n) => core_get_logger(n),
        None => get_root_logger(),
    };
    let fast_logger = fast_logger::get_fast_logger(logger_name);

    Ok(PyLogger {
        inner: logger,
        fast_logger,
        handlers: Arc::new(Mutex::new(Vec::new())),
        propagate: Arc::new(Mutex::new(true)), // Default to true like Python logging
        parent: Arc::new(Mutex::new(None)),    // Parent will be set by Python Manager
        manager: Arc::new(Mutex::new(manager.map(|m| m.clone_ref(py)))), // Store the manager
    })
}

/// Basic configuration for the logging system.
#[pyfunction(name = "basicConfig")]
#[pyo3(signature = (**_kwargs))]
#[allow(deprecated)]
#[allow(non_snake_case)]
fn basicConfig(_py: Python, _kwargs: Option<&Bound<'_, PyDict>>) -> PyResult<()> {
    // For now, just return Ok(()) as a placeholder
    // The actual configuration will be handled by the Python wrapper
    Ok(())
}

/// Flush all logging handlers.
#[pyfunction(name = "flush")]
fn flush(_py: Python) -> PyResult<()> {
    // For now, just return Ok(()) as a placeholder
    // The actual flushing will be handled by the Python wrapper
    Ok(())
}

/// Register a Python handler with the logging system.
#[pyfunction(name = "register_python_handler")]
fn register_python_handler(_py: Python, _handler: PyObject) -> PyResult<()> {
    // For now, just return Ok(()) as a placeholder
    // The actual registration will be handled by the Python wrapper
    Ok(())
}

/// Register a pure Rust console handler (no Python boundary).
#[pyfunction(name = "register_console_handler")]
fn register_console_handler(_py: Python, level: Option<u32>) -> PyResult<()> {
    use std::sync::Arc;

    let log_level = LogLevel::from_usize(level.unwrap_or(30) as usize); // Default: WARNING
    let handler = Arc::new(ConsoleHandler::with_level(log_level));

    HANDLERS.lock().unwrap().push(handler);
    Ok(())
}

/// Register a pure Rust file handler (no Python boundary).
#[pyfunction(name = "register_file_handler")]
fn register_file_handler(
    _py: Python,
    filename: String,
    max_bytes: Option<u64>,
    backup_count: Option<u32>,
    level: Option<u32>,
) -> PyResult<()> {
    use std::sync::Arc;

    let log_level = LogLevel::from_usize(level.unwrap_or(30) as usize); // Default: WARNING
    let max_size = max_bytes.unwrap_or(10 * 1024 * 1024); // Default: 10MB
    let backups = backup_count.unwrap_or(5); // Default: 5 backups

    // Create a formatter for the file handler
    let formatter = Arc::new(formatter::PythonFormatter::new(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s".to_string(),
    ));

    let handler = Arc::new(RotatingFileHandler::with_formatter(
        filename, max_size, backups, log_level, formatter,
    ));

    HANDLERS.lock().unwrap().push(handler);
    Ok(())
}

/// Set the thread name for logging.
#[pyfunction(name = "set_thread_name")]
fn set_thread_name(_py: Python, _name: String) -> PyResult<()> {
    // For now, just return Ok(()) as a placeholder
    // The actual thread name setting will be handled by the Python wrapper
    Ok(())
}
