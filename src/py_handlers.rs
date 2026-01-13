//! Python wrapper types for Rust handlers

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Arc;

use crate::core::LogLevel;
use crate::handler::{
    FileHandler, HTTPHandler, HTTPHandlerConfig, OTLPHandler, OTLPHandlerConfig,
    RotatingFileHandler, StreamHandler,
};

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
        Ok(Self {
            inner: Arc::new(RotatingFileHandler::new(filename, max_bytes, backup_count)),
        })
    }

    fn setLevel(&self, level: u32) -> PyResult<()> {
        self.inner.set_level(LogLevel::from_usize(level as usize));
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
    } else if let Ok(list) = obj.downcast::<PyList>() {
        let arr: Vec<Value> = list.iter().map(|item| py_to_json_value(&item)).collect();
        Value::Array(arr)
    } else if let Ok(dict) = obj.downcast::<PyDict>() {
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
