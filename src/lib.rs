//! # LogXide
//!
//! A high-performance logging library for Python, implemented in Rust.
//! LogXide provides a drop-in replacement for Python's standard logging module
//! with asynchronous processing capabilities and enhanced performance.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict};
use std::sync::{Arc, Mutex};

mod config;
pub mod core;
mod fast_logger;
mod filter;
pub mod formatter;
pub mod handler;
mod string_cache;

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
        loop {
            match receiver.recv() {
                Ok(message) => {
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
                Err(_) => break, // Channel closed
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
    /// Fast logger for atomic level checking
    fast_logger: Arc<fast_logger::FastLogger>,
}

#[pymethods]
impl PyLogger {
    #[getter]
    fn name(&self) -> PyResult<String> {
        Ok(self.fast_logger.name.to_string())
    }

    #[getter]
    fn level(&self) -> PyResult<u32> {
        Ok(self.fast_logger.get_level() as u32)
    }

    #[getter]
    fn handlers(&self) -> PyResult<Vec<String>> {
        // Return empty list for compatibility - logxide manages handlers globally
        Ok(Vec::new())
    }

    #[getter]
    fn disabled(&self) -> PyResult<bool> {
        // Return false - logger is not disabled
        Ok(false)
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

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn debug(&self, py: Python, msg: &str, args: &Bound<PyAny>, kwargs: Option<&Bound<PyDict>>) {
        let _ = py;
        let _ = args;
        let _ = kwargs; // Ignore kwargs for now

        // Fast atomic level check - no lock needed
        if !self.fast_logger.is_enabled_for(LogLevel::Debug) {
            return;
        }

        // Only create record if level is enabled
        let formatted_msg = msg.to_string();
        let record = create_log_record(
            self.fast_logger.name.to_string(),
            LogLevel::Debug,
            formatted_msg,
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn info(&self, py: Python, msg: &str, args: &Bound<PyAny>, kwargs: Option<&Bound<PyDict>>) {
        let _ = py;
        let _ = args;
        let _ = kwargs;

        if !self.fast_logger.is_enabled_for(LogLevel::Info) {
            return;
        }

        let formatted_msg = msg.to_string();
        let record = create_log_record(
            self.fast_logger.name.to_string(),
            LogLevel::Info,
            formatted_msg,
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn warning(&self, py: Python, msg: &str, args: &Bound<PyAny>, kwargs: Option<&Bound<PyDict>>) {
        let _ = py;
        let _ = args;
        let _ = kwargs;

        if !self.fast_logger.is_enabled_for(LogLevel::Warning) {
            return;
        }

        let formatted_msg = msg.to_string();
        let record = create_log_record(
            self.fast_logger.name.to_string(),
            LogLevel::Warning,
            formatted_msg,
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn error(&self, py: Python, msg: &str, args: &Bound<PyAny>, kwargs: Option<&Bound<PyDict>>) {
        let _ = py;
        let _ = args;
        let _ = kwargs;

        if !self.fast_logger.is_enabled_for(LogLevel::Error) {
            return;
        }

        let formatted_msg = msg.to_string();
        let record = create_log_record(
            self.fast_logger.name.to_string(),
            LogLevel::Error,
            formatted_msg,
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
    }

    #[pyo3(signature = (msg, *args, **kwargs))]
    fn critical(&self, py: Python, msg: &str, args: &Bound<PyAny>, kwargs: Option<&Bound<PyDict>>) {
        let _ = py;
        let _ = args;
        let _ = kwargs;

        if !self.fast_logger.is_enabled_for(LogLevel::Critical) {
            return;
        }

        let formatted_msg = msg.to_string();
        let record = create_log_record(
            self.fast_logger.name.to_string(),
            LogLevel::Critical,
            formatted_msg,
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
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

    #[allow(non_snake_case)]
    fn getChild(&self, suffix: &str) -> PyResult<PyLogger> {
        // Create a child logger
        let logger_name = if self.fast_logger.name.is_empty() {
            suffix.to_string()
        } else {
            format!("{}.{}", self.fast_logger.name, suffix)
        };
        let child_logger = core_get_logger(&logger_name);
        let child_fast_logger = fast_logger::get_fast_logger(&logger_name);
        Ok(PyLogger {
            inner: child_logger,
            fast_logger: child_fast_logger,
        })
    }
}

/// Get a logger by name, mirroring Python's `logging.getLogger()`.
#[pyfunction(name = "getLogger")]
#[pyo3(signature = (name = None))]
fn get_logger(name: Option<&str>) -> PyResult<PyLogger> {
    let logger_name = name.unwrap_or("");
    let logger = match name {
        Some(n) => core_get_logger(n),
        None => get_root_logger(),
    };
    let fast_logger = fast_logger::get_fast_logger(logger_name);
    Ok(PyLogger {
        inner: logger,
        fast_logger,
    })
}

/// Basic configuration for the logging system, mirroring Python's `logging.basicConfig()`.
#[pyfunction(name = "basicConfig")]
#[pyo3(signature = (**kwargs))]
fn basic_config(_py: Python, kwargs: Option<&Bound<PyDict>>) -> PyResult<()> {
    // Set root logger level
    let root_level = if let Some(kw) = kwargs {
        if let Ok(Some(level_val)) = kw.get_item("level") {
            let level: u32 = level_val.extract().unwrap_or(30);
            LogLevel::from_usize(level as usize)
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
            Some(
                datefmt_val
                    .extract::<String>()
                    .unwrap_or_else(|_| "%Y-%m-%d %H:%M:%S".to_string()),
            )
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
    let _ = SENDER.send(LogMessage::Flush(sender));

    // Wait for the flush to complete
    RUNTIME.block_on(async {
        let _ = receiver.await;
    });

    Ok(())
}

/// Register a Python handler globally
#[pyfunction]
fn register_python_handler(_py: Python, handler: &Bound<PyAny>) -> PyResult<()> {
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
    let logging_mod = PyModule::new(py, "logging")?;
    logging_mod.add_class::<PyLogger>()?;
    logging_mod.add_function(wrap_pyfunction!(get_logger, &logging_mod)?)?;
    logging_mod.add_function(wrap_pyfunction!(basic_config, &logging_mod)?)?;
    logging_mod.add_function(wrap_pyfunction!(flush, &logging_mod)?)?;
    logging_mod.add_function(wrap_pyfunction!(register_python_handler, &logging_mod)?)?;
    m.add_submodule(&logging_mod)?;
    // The global SENDER and HANDLERS are initialized on first use
    Ok(())
}
