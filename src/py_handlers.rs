//! Python wrapper types for Rust handlers and formatters

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Arc;

use crate::core::{LogLevel, LogRecord};
use crate::formatter::{ColorFormatter, Formatter, PythonFormatter};
use crate::handler::{
    FileHandler, HTTPHandler, HTTPHandlerConfig, MemoryHandler, OTLPHandler, OTLPHandlerConfig,
    RotatingFileHandler, StreamHandler,
};

// ============================================================================
// Formatter Bindings
// ============================================================================

/// Python binding for PythonFormatter.
/// Standard Python logging-compatible formatter.
#[pyclass(name = "Formatter")]
pub struct PyFormatter {
    pub(crate) inner: Arc<PythonFormatter>,
}

#[pymethods]
impl PyFormatter {
    /// Create a new Formatter with the specified format string.
    ///
    /// Args:
    ///     fmt: Python-style format string with %(field)s placeholders
    ///     datefmt: Optional strftime format for %(asctime)s
    #[new]
    #[pyo3(signature = (fmt="%(message)s".to_string(), datefmt=None))]
    pub fn new(fmt: String, datefmt: Option<String>) -> Self {
        let formatter = if let Some(df) = datefmt {
            PythonFormatter::with_date_format(fmt, df)
        } else {
            PythonFormatter::new(fmt)
        };
        Self {
            inner: Arc::new(formatter),
        }
    }

    /// Format a log record.
    pub fn format(&self, record: &LogRecord) -> String {
        self.inner.format(record)
    }
}

/// Python binding for ColorFormatter.
/// Supports ANSI color codes for terminal output.
///
/// Additional format placeholders:
/// - %(ansi_level_color)s: ANSI color code for the log level
/// - %(ansi_reset_color)s: ANSI reset code
///
/// Example:
///     formatter = ColorFormatter(
///         "%(ansi_level_color)s%(levelname)s%(ansi_reset_color)s - %(message)s"
///     )
#[pyclass(name = "ColorFormatter")]
pub struct PyColorFormatter {
    pub(crate) inner: Arc<ColorFormatter>,
}

#[pymethods]
impl PyColorFormatter {
    /// Create a new ColorFormatter with ANSI color support.
    ///
    /// Args:
    ///     fmt: Format string with %(field)s placeholders.
    ///          Use %(ansi_level_color)s and %(ansi_reset_color)s for colors.
    ///     datefmt: Optional strftime format for %(asctime)s
    #[new]
    #[pyo3(signature = (fmt="%(ansi_level_color)s%(levelname)s%(ansi_reset_color)s - %(message)s".to_string(), datefmt=None))]
    pub fn new(fmt: String, datefmt: Option<String>) -> Self {
        let formatter = if let Some(df) = datefmt {
            ColorFormatter::with_date_format(fmt, df)
        } else {
            ColorFormatter::new(fmt)
        };
        Self {
            inner: Arc::new(formatter),
        }
    }

    /// Format a log record with ANSI colors.
    pub fn format(&self, record: &LogRecord) -> String {
        self.inner.format(record)
    }
}

// ============================================================================
// Handler Bindings
// ============================================================================
#[pyclass(name = "FileHandler")]
pub struct PyFileHandler {
    pub(crate) inner: Arc<FileHandler>,
}

#[pymethods]
impl PyFileHandler {
    #[new]
    fn new(filename: String) -> PyResult<Self> {
        let h = FileHandler::new(filename).map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok(Self { inner: Arc::new(h) })
    }

    fn setLevel(&self, level: u32) -> PyResult<()> {
        self.inner.set_level(LogLevel::from_usize(level as usize));
        Ok(())
    }

    /// Set the flush level. Records at or above this level trigger immediate flush.
    /// Default is ERROR (40).
    #[pyo3(name = "setFlushLevel")]
    fn set_flush_level(&self, level: u32) -> PyResult<()> {
        self.inner.set_flush_level(LogLevel::from_usize(level as usize));
        Ok(())
    }

    /// Get the current flush level.
    #[pyo3(name = "getFlushLevel")]
    fn get_flush_level(&self) -> PyResult<u32> {
        Ok(self.inner.get_flush_level() as u32)
    }

    /// Set an error callback function.
    #[pyo3(name = "setErrorCallback")]
    fn set_error_callback(&self, py: Python, callback: Option<Py<PyAny>>) -> PyResult<()> {
        match callback {
            Some(cb) => {
                let cb = cb.clone_ref(py);
                self.inner.set_error_callback(Some(Arc::new(move |msg: String| {
                    Python::attach(|py| {
                        let _ = cb.call1(py, (msg,));
                    });
                })));
            }
            None => {
                self.inner.set_error_callback(None);
            }
        }
        Ok(())
    }

    fn flush(&self) -> PyResult<()> {
        use crate::handler::Handler;
        futures::executor::block_on(self.inner.flush());
        Ok(())
    }
}

#[pyclass(name = "StreamHandler")]
pub struct PyStreamHandler {
    pub(crate) inner: Arc<StreamHandler>,
}

#[pymethods]
impl PyStreamHandler {
    #[new]
    #[pyo3(signature = (stream=None))]
    fn new(stream: Option<&str>) -> PyResult<Self> {
        let h = match stream {
            Some("stdout") => StreamHandler::stdout(),
            _ => StreamHandler::stderr(),
        };
        Ok(Self { inner: Arc::new(h) })
    }

    fn setLevel(&self, level: u32) -> PyResult<()> {
        self.inner.set_level(LogLevel::from_usize(level as usize));
        Ok(())
    }

    /// Set an error callback function.
    #[pyo3(name = "setErrorCallback")]
    fn set_error_callback(&self, py: Python, callback: Option<Py<PyAny>>) -> PyResult<()> {
        match callback {
            Some(cb) => {
                let cb = cb.clone_ref(py);
                self.inner.set_error_callback(Some(Arc::new(move |msg: String| {
                    Python::attach(|py| {
                        let _ = cb.call1(py, (msg,));
                    });
                })));
            }
            None => {
                self.inner.set_error_callback(None);
            }
        }
        Ok(())
    }
}

#[pyclass(name = "RotatingFileHandler")]
pub struct PyRotatingFileHandler {
    pub(crate) inner: Arc<RotatingFileHandler>,
}

#[pymethods]
impl PyRotatingFileHandler {
    #[new]
    #[pyo3(signature = (filename, max_bytes=10485760, backup_count=5))]
    fn new(filename: String, max_bytes: u64, backup_count: u32) -> PyResult<Self> {
        let h = RotatingFileHandler::new(filename, max_bytes, backup_count)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok(Self { inner: Arc::new(h) })
    }

    fn setLevel(&self, level: u32) -> PyResult<()> {
        self.inner.set_level(LogLevel::from_usize(level as usize));
        Ok(())
    }

    /// Set the flush level. Records at or above this level trigger immediate flush.
    #[pyo3(name = "setFlushLevel")]
    fn set_flush_level(&self, level: u32) -> PyResult<()> {
        self.inner.set_flush_level(LogLevel::from_usize(level as usize));
        Ok(())
    }

    /// Get the current flush level.
    #[pyo3(name = "getFlushLevel")]
    fn get_flush_level(&self) -> PyResult<u32> {
        Ok(self.inner.get_flush_level() as u32)
    }

    /// Set an error callback function.
    #[pyo3(name = "setErrorCallback")]
    fn set_error_callback(&self, py: Python, callback: Option<Py<PyAny>>) -> PyResult<()> {
        match callback {
            Some(cb) => {
                let cb = cb.clone_ref(py);
                self.inner.set_error_callback(Some(Arc::new(move |msg: String| {
                    Python::attach(|py| {
                        let _ = cb.call1(py, (msg,));
                    });
                })));
            }
            None => {
                self.inner.set_error_callback(None);
            }
        }
        Ok(())
    }

    fn flush(&self) -> PyResult<()> {
        use crate::handler::Handler;
        futures::executor::block_on(self.inner.flush());
        Ok(())
    }
}

#[pyclass(name = "HTTPHandler")]
pub struct PyHTTPHandler {
    pub(crate) inner: Arc<HTTPHandler>,
}

impl Drop for PyHTTPHandler {
    fn drop(&mut self) {}
}

fn py_to_json_value(obj: &Bound<PyAny>) -> Value {
    if obj.is_none() {
        Value::Null
    } else if let Ok(b) = obj.extract::<bool>() {
        Value::Bool(b)
    } else if let Ok(i) = obj.extract::<i64>() {
        Value::Number(i.into())
    } else if let Ok(f) = obj.extract::<f64>() {
        serde_json::Number::from_f64(f)
            .map(Value::Number)
            .unwrap_or(Value::Null)
    } else if let Ok(s) = obj.extract::<String>() {
        Value::String(s)
    } else if let Ok(list) = obj.cast::<PyList>() {
        let arr: Vec<Value> = list.iter().map(|item| py_to_json_value(&item)).collect();
        Value::Array(arr)
    } else if let Ok(dict) = obj.cast::<PyDict>() {
        let mut map = serde_json::Map::new();
        for (k, v) in dict.iter() {
            if let Ok(key) = k.extract::<String>() {
                map.insert(key, py_to_json_value(&v));
            }
        }
        Value::Object(map)
    } else if let Ok(s) = obj.str() {
        Value::String(s.to_string())
    } else {
        Value::Null
    }
}

#[pymethods]
impl PyHTTPHandler {
    #[new]
    #[pyo3(signature = (
        url,
        headers=None,
        capacity=10000,
        batch_size=1000,
        flush_interval=30,
        global_context=None,
        transform_callback=None,
        context_provider=None,
        error_callback=None
    ))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        py: Python,
        url: String,
        headers: Option<HashMap<String, String>>,
        capacity: usize,
        batch_size: usize,
        flush_interval: u64,
        global_context: Option<&Bound<PyDict>>,
        transform_callback: Option<Py<PyAny>>,
        context_provider: Option<Py<PyAny>>,
        error_callback: Option<Py<PyAny>>,
    ) -> PyResult<Self> {
        let h_map = headers.unwrap_or_default();

        let global_ctx: HashMap<String, Value> = global_context
            .map(|dict| {
                let mut map = HashMap::new();
                for (k, v) in dict.iter() {
                    if let Ok(key) = k.extract::<String>() {
                        map.insert(key, py_to_json_value(&v));
                    }
                }
                map
            })
            .unwrap_or_default();

        let config = HTTPHandlerConfig {
            url,
            headers: h_map,
            global_context: global_ctx,
            transform_callback: transform_callback.map(|cb| cb.clone_ref(py)),
            context_provider: context_provider.map(|cb| cb.clone_ref(py)),
            error_callback: error_callback.map(|cb| cb.clone_ref(py)),
        };

        let h = HTTPHandler::with_config(config, capacity, batch_size, flush_interval);
        Ok(Self { inner: Arc::new(h) })
    }

    fn setLevel(&self, level: u32) -> PyResult<()> {
        self.inner.set_level(LogLevel::from_usize(level as usize));
        Ok(())
    }

    fn flush(&self) -> PyResult<()> {
        self.inner.flush();
        Ok(())
    }

    fn shutdown(&self) -> PyResult<()> {
        self.inner.shutdown();
        Ok(())
    }

    /// Set the flush level. Records at or above this level trigger immediate flush.
    /// Default is ERROR (40). Use logging.CRITICAL (50) to flush only on critical.
    /// Use logging.DEBUG (10) to flush on every record.
    #[pyo3(name = "setFlushLevel")]
    fn set_flush_level(&self, level: u32) -> PyResult<()> {
        self.inner.set_flush_level(LogLevel::from_usize(level as usize));
        Ok(())
    }

    /// Get the current flush level.
    #[pyo3(name = "getFlushLevel")]
    fn get_flush_level(&self) -> PyResult<u32> {
        Ok(self.inner.get_flush_level() as u32)
    }
}

#[pyclass(name = "OTLPHandler")]
pub struct PyOTLPHandler {
    pub(crate) inner: Arc<OTLPHandler>,
}

impl Drop for PyOTLPHandler {
    fn drop(&mut self) {}
}

#[pymethods]
impl PyOTLPHandler {
    #[new]
    #[pyo3(signature = (
        url,
        headers=None,
        service_name="unknown_service".to_string(),
        capacity=10000,
        batch_size=1000,
        flush_interval=30,
        error_callback=None
    ))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        py: Python,
        url: String,
        headers: Option<HashMap<String, String>>,
        service_name: String,
        capacity: usize,
        batch_size: usize,
        flush_interval: u64,
        error_callback: Option<Py<PyAny>>,
    ) -> PyResult<Self> {
        let h_map = headers.unwrap_or_default();

        let config = OTLPHandlerConfig {
            url,
            headers: h_map,
            service_name,
            error_callback: error_callback.map(|cb| cb.clone_ref(py)),
        };

        let h = OTLPHandler::with_config(config, capacity, batch_size, flush_interval);
        Ok(Self { inner: Arc::new(h) })
    }

    fn setLevel(&self, level: u32) -> PyResult<()> {
        self.inner.set_level(LogLevel::from_usize(level as usize));
        Ok(())
    }

    fn flush(&self) -> PyResult<()> {
        self.inner.flush();
        Ok(())
    }

    fn shutdown(&self) -> PyResult<()> {
        self.inner.shutdown();
        Ok(())
    }
}

#[pyclass(name = "MemoryHandler")]
pub struct PyMemoryHandler {
    pub(crate) inner: Arc<MemoryHandler>,
}

impl Drop for PyMemoryHandler {
    fn drop(&mut self) {}
}

#[pymethods]
impl PyMemoryHandler {
    #[new]
    pub fn new() -> Self {
        Self {
            inner: Arc::new(MemoryHandler::new()),
        }
    }

    /// Returns all captured log records.
    #[pyo3(name = "getRecords")]
    pub fn get_records(&self) -> Vec<LogRecord> {
        self.inner.get_records()
    }

    /// Alias for getRecords() - Python naming convention.
    #[getter]
    pub fn records(&self) -> Vec<LogRecord> {
        self.inner.get_records()
    }

    /// Returns all captured messages as a single newline-separated string.
    /// Compatible with pytest caplog.text
    #[getter]
    pub fn text(&self) -> String {
        self.inner.get_text()
    }

    /// Returns record tuples in pytest caplog format: (logger_name, level_num, message).
    /// Compatible with pytest caplog.record_tuples
    #[getter]
    pub fn record_tuples(&self) -> Vec<(String, i32, String)> {
        self.inner.get_record_tuples()
    }

    /// Clear all captured records.
    pub fn clear(&self) {
        self.inner.clear();
    }

    #[pyo3(name = "setLevel")]
    pub fn set_level(&self, level: u32) -> PyResult<()> {
        self.inner.set_level(LogLevel::from_usize(level as usize));
        Ok(())
    }

    pub fn flush(&self) -> PyResult<()> {
        Ok(())
    }

    pub fn shutdown(&self) -> PyResult<()> {
        Ok(())
    }
}
