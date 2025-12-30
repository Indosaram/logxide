//! # LogXide
//! # LogXide - Complex Implementation
//!
//! ⚠️ **DEPRECATED: This module is no longer used.**
//!
//! This was an experimental implementation that used PythonHandler.
//! The main implementation in `lib.rs` uses Rust native handlers exclusively
//! for better performance.
//!
//! **Do not use this module.** Use `lib.rs` instead.
//!
//! ---
//!
//! A high-performance logging library for Python, implemented in Rust.
//! LogXide provides a drop-in replacement for Python's standard logging module
//! with asynchronous processing capabilities and enhanced performance.
//!
//! ## Architecture
//!
//! LogXide uses an async architecture with the following components:
//! - **PyLogger**: Python-facing logger class that wraps Rust Logger
//! - **LogMessage**: Message types for async communication
//! - **Global Runtime**: Tokio runtime for async processing
//! - **Message Channel**: High-throughput channel for log records
//! - **Handler Registry**: Global registry of log handlers
//!
//! ## Usage
//!
//! ```python
//! import logxide
//! logxide.install()  # Replace Python's logging module
//!
//! import logging
//! logging.basicConfig(level=logging.INFO)
//! logger = logging.getLogger(__name__)
//! logger.info("High-performance logging!")
//! ```

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyModule};
use std::sync::{Arc, Mutex};

mod config;
pub mod core;
mod filter;
pub mod formatter;
pub mod handler;

// Pure Rust modules for testing without PyO3
#[cfg(test)]
mod concurrency_pure;
#[cfg(test)]
mod core_pure;
#[cfg(test)]
mod formatter_pure;

use core::{
    create_log_record, get_logger as core_get_logger, get_root_logger, LogLevel, LogRecord, Logger,
};
use formatter::{Formatter, PythonFormatter};
use handler::{ConsoleHandler, Handler, PythonHandler};
use pyo3::types::IntoPyDict;

use once_cell::sync::Lazy;
use tokio::runtime::Runtime;
use tokio::sync::mpsc::{self, Receiver, Sender};
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
    Record(LogRecord),
    /// A flush request with a completion signal
    Flush(oneshot::Sender<()>),
}

/// Global sender for log messages to the async processing system.
///
/// This channel has a capacity of 1024 messages and uses try_send to avoid
/// blocking the caller if the channel is full. Messages are processed by
/// a background task spawned in the global RUNTIME.
static SENDER: Lazy<Sender<LogMessage>> = Lazy::new(|| {
    let (sender, mut receiver): (Sender<LogMessage>, Receiver<LogMessage>) = mpsc::channel(1024);
    // Spawn background task for processing log messages
    RUNTIME.spawn(async move {
        while let Some(message) = receiver.recv().await {
            match message {
                LogMessage::Record(record) => {
                    // Dispatch to all registered handlers
                    let handlers = HANDLERS.lock().unwrap().clone();
                    let mut tasks = Vec::new();
                    for handler in handlers {
                        // Each handler is async
                        let record = record.clone();
                        let handler = handler.clone();
                        let task = RUNTIME.spawn(async move {
                            handler.emit(&record).await;
                        });
                        tasks.push(task);
                    }
                    // Wait for all handlers to complete
                    for task in tasks {
                        let _ = task.await;
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
}

#[pymethods]
impl PyLogger {
    #[getter]
    fn name(&self) -> PyResult<String> {
        Ok(self.inner.lock().unwrap().name.clone())
    }

    #[getter]
    fn level(&self) -> PyResult<u32> {
        Ok(self.inner.lock().unwrap().level as u32)
    }

    #[getter]
    fn handlers(&self) -> PyResult<Vec<String>> {
        // Return empty list for compatibility - logxide manages handlers globally
        Ok(Vec::new())
    }

    #[getter]
    fn manager(&self, py: Python) -> PyResult<PyObject> {
        // Return a manager object with disable attribute for SQLAlchemy compatibility
        let logxide_module = py.import("logxide")?;
        let manager_class = logxide_module.getattr("LoggingManager")?;
        let manager_instance = manager_class.call0()?;
        Ok(manager_instance.to_object(py))
    }

    #[getter]
    fn disabled(&self) -> PyResult<bool> {
        // Return false - logger is not disabled
        Ok(false)
    }

    #[allow(non_snake_case)]
    fn setLevel(&mut self, level: u32) -> PyResult<()> {
        let level = LogLevel::from_usize(level as usize);
        self.inner.lock().unwrap().set_level(level);
        Ok(())
    }

    #[allow(non_snake_case)]
    fn getEffectiveLevel(&self) -> PyResult<u32> {
        Ok(self.inner.lock().unwrap().get_effective_level() as u32)
    }

    #[allow(non_snake_case)]
    fn addHandler(&mut self, py: Python, handler: &PyAny) -> PyResult<()> {
        // Wrap the Python callable as a PythonHandler and register globally
        if !handler.is_callable() {
            return Err(PyValueError::new_err("Handler must be callable"));
        }
        // Use Python's id() for handler identity
        let handler_id: usize = py
            .eval("id(obj)", Some([("obj", handler)].into_py_dict(py)), None)
            .unwrap()
            .extract()
            .unwrap();
        let py_handler = PythonHandler::with_id(handler.to_object(py), handler_id);
        HANDLERS.lock().unwrap().push(Arc::new(py_handler));
        Ok(())
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn debug(&self, py: Python, msg: &str, args: &PyAny, kwargs: Option<&PyDict>) {
        let _ = kwargs; // Ignore kwargs for now
        let logger = self.inner.lock().unwrap();
        if !logger.is_enabled_for(LogLevel::Debug) {
            return;
        }

        // Format the message if args are provided
        let formatted_msg = if let Ok(args_tuple) = args.downcast::<pyo3::types::PyTuple>() {
            if !args_tuple.is_empty() {
                // Use Python's % formatting
                match py.eval(
                    &format!("'{}' % {}", msg.replace("'", "\\'"), args_tuple),
                    None,
                    None,
                ) {
                    Ok(formatted) => formatted
                        .extract::<String>()
                        .unwrap_or_else(|_| msg.to_string()),
                    Err(_) => msg.to_string(),
                }
            } else {
                msg.to_string()
            }
        } else {
            msg.to_string()
        };

        let record = create_log_record(logger.name.clone(), LogLevel::Debug, formatted_msg);
        let _ = SENDER.try_send(LogMessage::Record(record));
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn info(&self, py: Python, msg: &str, args: &PyAny, kwargs: Option<&PyDict>) {
        let _ = kwargs;
        let logger = self.inner.lock().unwrap();
        if !logger.is_enabled_for(LogLevel::Info) {
            return;
        }

        let formatted_msg = if let Ok(args_tuple) = args.downcast::<pyo3::types::PyTuple>() {
            if !args_tuple.is_empty() {
                match py.eval(
                    &format!("'{}' % {}", msg.replace("'", "\\'"), args_tuple),
                    None,
                    None,
                ) {
                    Ok(formatted) => formatted
                        .extract::<String>()
                        .unwrap_or_else(|_| msg.to_string()),
                    Err(_) => msg.to_string(),
                }
            } else {
                msg.to_string()
            }
        } else {
            msg.to_string()
        };

        let record = create_log_record(logger.name.clone(), LogLevel::Info, formatted_msg);
        let _ = SENDER.try_send(LogMessage::Record(record));
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn warning(&self, py: Python, msg: &str, args: &PyAny, kwargs: Option<&PyDict>) {
        let _ = kwargs;
        let logger = self.inner.lock().unwrap();
        if !logger.is_enabled_for(LogLevel::Warning) {
            return;
        }

        let formatted_msg = if let Ok(args_tuple) = args.downcast::<pyo3::types::PyTuple>() {
            if !args_tuple.is_empty() {
                match py.eval(
                    &format!("'{}' % {}", msg.replace("'", "\\'"), args_tuple),
                    None,
                    None,
                ) {
                    Ok(formatted) => formatted
                        .extract::<String>()
                        .unwrap_or_else(|_| msg.to_string()),
                    Err(_) => msg.to_string(),
                }
            } else {
                msg.to_string()
            }
        } else {
            msg.to_string()
        };

        let record = create_log_record(logger.name.clone(), LogLevel::Warning, formatted_msg);
        let _ = SENDER.try_send(LogMessage::Record(record));
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn error(&self, py: Python, msg: &str, args: &PyAny, kwargs: Option<&PyDict>) {
        let _ = kwargs;
        let logger = self.inner.lock().unwrap();
        if !logger.is_enabled_for(LogLevel::Error) {
            return;
        }

        let formatted_msg = if let Ok(args_tuple) = args.downcast::<pyo3::types::PyTuple>() {
            if !args_tuple.is_empty() {
                match py.eval(
                    &format!("'{}' % {}", msg.replace("'", "\\'"), args_tuple),
                    None,
                    None,
                ) {
                    Ok(formatted) => formatted
                        .extract::<String>()
                        .unwrap_or_else(|_| msg.to_string()),
                    Err(_) => msg.to_string(),
                }
            } else {
                msg.to_string()
            }
        } else {
            msg.to_string()
        };

        let record = create_log_record(logger.name.clone(), LogLevel::Error, formatted_msg);
        let _ = SENDER.try_send(LogMessage::Record(record));
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn critical(&self, py: Python, msg: &str, args: &PyAny, kwargs: Option<&PyDict>) {
        let _ = kwargs;
        let logger = self.inner.lock().unwrap();
        if !logger.is_enabled_for(LogLevel::Critical) {
            return;
        }

        let formatted_msg = if let Ok(args_tuple) = args.downcast::<pyo3::types::PyTuple>() {
            if !args_tuple.is_empty() {
                match py.eval(
                    &format!("'{}' % {}", msg.replace("'", "\\'"), args_tuple),
                    None,
                    None,
                ) {
                    Ok(formatted) => formatted
                        .extract::<String>()
                        .unwrap_or_else(|_| msg.to_string()),
                    Err(_) => msg.to_string(),
                }
            } else {
                msg.to_string()
            }
        } else {
            msg.to_string()
        };

        let record = create_log_record(logger.name.clone(), LogLevel::Critical, formatted_msg);
        let _ = SENDER.try_send(LogMessage::Record(record));
    }

    // Add compatibility methods that third-party libraries might expect
    #[allow(non_snake_case)]
    fn isEnabledFor(&self, level: u32) -> PyResult<bool> {
        let logger = self.inner.lock().unwrap();
        let level = LogLevel::from_usize(level as usize);
        Ok(logger.is_enabled_for(level))
    }

    #[allow(non_snake_case)]
    fn removeHandler(&self, _handler: &PyAny) -> PyResult<()> {
        // For compatibility - logxide manages handlers globally
        Ok(())
    }

    #[allow(non_snake_case)]
    fn addFilter(&self, _filter: &PyAny) -> PyResult<()> {
        // For compatibility - not implemented yet
        Ok(())
    }

    #[allow(non_snake_case)]
    fn removeFilter(&self, _filter: &PyAny) -> PyResult<()> {
        // For compatibility - not implemented yet
        Ok(())
    }

    fn disable(&self, _level: u32) -> PyResult<()> {
        // For compatibility - disable functionality not implemented
        Ok(())
    }

    #[allow(non_snake_case)]
    fn setFormatter(&self, _formatter: &PyAny) -> PyResult<()> {
        // For compatibility - logxide manages formatters globally
        Ok(())
    }

    #[allow(non_snake_case)]
    fn getChild(&self, suffix: &str) -> PyResult<PyLogger> {
        // Create a child logger
        let logger_name = format!("{}.{}", self.inner.lock().unwrap().name, suffix);
        let child_logger = core_get_logger(&logger_name);
        Ok(PyLogger {
            inner: child_logger,
        })
    }

    fn log(&self, level: u32, msg: &str) {
        let logger = self.inner.lock().unwrap();
        let level = LogLevel::from_usize(level as usize);
        let record = LogRecord {
            name: logger.name.clone(),
            levelno: level as i32,
            levelname: format!("{:?}", level).to_uppercase(),
            pathname: "".to_string(),
            filename: "".to_string(),
            module: "".to_string(),
            lineno: 0,
            func_name: "".to_string(),
            created: 0.0,
            msecs: 0.0,
            relative_created: 0.0,
            thread: 0,
            thread_name: "".to_string(),
            process_name: "".to_string(),
            process: 0,
            msg: msg.to_string(),
            args: None,
            exc_info: None,
            exc_text: None,
            stack_info: None,
            task_name: None,
        };
        let _ = SENDER.try_send(LogMessage::Record(record));
    }

    #[pyo3(signature = (level, msg, args, **kwargs))]
    fn _log(&self, py: Python, level: u32, msg: &str, args: &PyAny, kwargs: Option<&PyDict>) {
        let _ = kwargs;
        let logger = self.inner.lock().unwrap();
        let level_enum = LogLevel::from_usize(level as usize);

        if !logger.is_enabled_for(level_enum) {
            return;
        }

        // Format the message if args are provided
        let formatted_msg = if let Ok(args_tuple) = args.downcast::<pyo3::types::PyTuple>() {
            if !args_tuple.is_empty() {
                match py.eval(
                    &format!("'{}' % {}", msg.replace("'", "\\'"), args_tuple),
                    None,
                    None,
                ) {
                    Ok(formatted) => formatted
                        .extract::<String>()
                        .unwrap_or_else(|_| msg.to_string()),
                    Err(_) => msg.to_string(),
                }
            } else {
                msg.to_string()
            }
        } else {
            msg.to_string()
        };

        let record = create_log_record(logger.name.clone(), level_enum, formatted_msg);
        let _ = SENDER.try_send(LogMessage::Record(record));
    }
}

/// Get a logger by name, mirroring Python's `logging.getLogger()`.
///
/// Creates or retrieves a logger with the specified name. If no name is provided,
/// returns the root logger. Logger names follow a hierarchical structure using
/// dots as separators (e.g., "myapp.database.connection").
///
/// # Arguments
///
/// * `name` - Optional logger name. If None, returns the root logger.
///
/// # Returns
///
/// A PyLogger instance wrapping the Rust logger implementation.
///
/// # Examples
///
/// ```python
/// # Get the root logger
/// root = logging.getLogger()
///
/// # Get a named logger
/// logger = logging.getLogger("myapp.database")
/// ```
#[pyfunction(name = "getLogger")]
fn get_logger(name: Option<&str>) -> PyResult<PyLogger> {
    let logger = match name {
        Some(n) => core_get_logger(n),
        None => get_root_logger(),
    };
    Ok(PyLogger { inner: logger })
}

/// Basic configuration for the logging system, mirroring Python's `logging.basicConfig()`.
///
/// Configures the root logger with the specified level and format. This function
/// clears any existing handlers and adds a new console handler with the given configuration.
///
/// # Arguments
///
/// * `kwargs` - Configuration options including:
///   - `level`: Minimum log level (default: WARNING)
///   - `format`: Log message format string (default: "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
///   - `datefmt`: Date format string (optional)
///
/// # Examples
///
/// ```python
/// logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
/// ```
#[pyfunction(name = "basicConfig")]
fn basic_config(_py: Python, kwargs: Option<&Bound<PyDict>>) -> PyResult<()> {
    // Set root logger level
    let root_level = if let Some(kw) = kwargs {
        if let Ok(level) = kw.get_item("level") {
            if let Some(level_val) = level {
                let level: u32 = level_val.extract().unwrap_or(30);
                LogLevel::from_usize(level as usize)
            } else {
                LogLevel::Warning
            }
        } else {
            LogLevel::Warning
        }
    } else {
        LogLevel::Warning
    };

    let logger = get_root_logger();
    logger.lock().unwrap().set_level(root_level);

    // Clear existing handlers and add new one (allows reconfiguration)
    HANDLERS.lock().unwrap().clear();

    // Check for format parameter
    let format_string = if let Some(kw) = kwargs {
        if let Ok(Some(format_val)) = kw.get_item("format") {
            format_val.extract::<String>().unwrap_or_else(|_| {
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s".to_string()
            })
        } else {
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s".to_string()
        }
    } else {
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s".to_string()
    };

    // Check for date format parameter
    let date_format = if let Some(kw) = kwargs {
        if let Ok(Some(datefmt_val)) = kw.get_item("datefmt") {
            Some(datefmt_val.extract::<String>()
                .unwrap_or_else(|_| "%Y-%m-%d %H:%M:%S".to_string()))
        } else {
            None
        }
    } else {
        None
    };

    // Create formatter
    let formatter: Arc<dyn Formatter + Send + Sync> = if let Some(date_fmt) = date_format {
        Arc::new(PythonFormatter::with_date_format(format_string, date_fmt))
    } else {
        Arc::new(PythonFormatter::new(format_string))
    };

    // Add a console handler with the formatter
    let console_handler = ConsoleHandler::with_formatter(LogLevel::Debug, formatter);
    HANDLERS.lock().unwrap().push(Arc::new(console_handler));

    Ok(())
}

/// Flush all pending log messages
#[pyfunction]
fn flush() -> PyResult<()> {
    let (sender, receiver) = oneshot::channel();
    let _ = SENDER.try_send(LogMessage::Flush(sender));

    // Wait for the flush to complete
    RUNTIME.block_on(async {
        let _ = receiver.await;
    });

    Ok(())
}

/// Register a Python handler globally (for demonstration)
#[pyfunction]
fn register_python_handler(py: Python, handler: &Bound<PyAny>) -> PyResult<()> {
    if !handler.is_callable() {
        return Err(PyValueError::new_err("Handler must be callable"));
    }
    let py_handler = PythonHandler::new(handler.clone().unbind());
    HANDLERS.lock().unwrap().push(Arc::new(py_handler));
    Ok(())
}

/// Python module definition
#[pymodule]
fn logxide(py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    // Create a submodule named "logging"
    let logging_mod = PyModule::new_bound(py, "logging")?;
    logging_mod.add_class::<PyLogger>()?;
    logging_mod.add_function(wrap_pyfunction!(get_logger, &logging_mod)?)?;
    logging_mod.add_function(wrap_pyfunction!(basic_config, &logging_mod)?)?;
    logging_mod.add_function(wrap_pyfunction!(flush, &logging_mod)?)?;
    logging_mod.add_function(wrap_pyfunction!(register_python_handler, &logging_mod)?)?;
    m.add_submodule(&logging_mod)?;
    // The global SENDER and HANDLERS are initialized on first use
    Ok(())
}
