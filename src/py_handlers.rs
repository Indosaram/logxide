//! Python wrapper types for Rust handlers

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::collections::HashMap;
use std::sync::Arc;

use crate::core::LogLevel;
use crate::handler::{
    BufferedHTTPHandler, FileHandler, OverflowStrategy, RotatingFileHandler, StreamHandler,
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

#[pyclass(name = "BufferedHTTPHandler")]
pub struct PyBufferedHTTPHandler {
    pub(crate) inner: Arc<BufferedHTTPHandler>,
}

impl Drop for PyBufferedHTTPHandler {
    fn drop(&mut self) {}
}

#[pymethods]
impl PyBufferedHTTPHandler {
    #[new]
    #[pyo3(signature = (url, headers=None, capacity=10000, batch_size=1000, flush_interval=30))]
    fn new(
        url: String,
        headers: Option<HashMap<String, String>>,
        capacity: usize,
        batch_size: usize,
        flush_interval: u64,
    ) -> PyResult<Self> {
        let h_map = headers.unwrap_or_default();
        let h = BufferedHTTPHandler::new(
            url,
            h_map,
            capacity,
            batch_size,
            flush_interval,
            OverflowStrategy::DropOldest,
        );
        Ok(Self { inner: Arc::new(h) })
    }

    fn setLevel(&self, level: u32) -> PyResult<()> {
        self.inner.set_level(LogLevel::from_usize(level as usize));
        Ok(())
    }
}
