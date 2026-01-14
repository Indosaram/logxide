//! PyLogger - Python-exposed logger implementation

#![allow(non_snake_case)]

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyList, PyTuple};
use pyo3::IntoPyObjectExt;
use serde_json::Value;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use crate::core::{create_log_record_with_extra, LogLevel, LogRecord, Logger};
use crate::fast_logger::FastLogger;
use crate::globals::{add_handler_to_registry, HANDLERS};
use crate::handler::Handler;

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

#[pyclass]
pub struct PyLogger {
    inner: Arc<Mutex<Logger>>,
    fast_logger: Arc<FastLogger>,
    local_handlers: Arc<Mutex<Vec<Arc<dyn Handler + Send + Sync>>>>,
    propagate: Arc<Mutex<bool>>,
    parent: Arc<Mutex<Option<Py<PyAny>>>>,
    manager: Arc<Mutex<Option<Py<PyAny>>>>,
}

impl PyLogger {
    pub fn new(
        inner: Arc<Mutex<Logger>>,
        fast_logger: Arc<FastLogger>,
        manager: Option<Py<PyAny>>,
    ) -> Self {
        PyLogger {
            inner,
            fast_logger,
            local_handlers: Arc::new(Mutex::new(Vec::new())),
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
            local_handlers: self.local_handlers.clone(),
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
                if let Ok(extra_dict) = extra_bound.downcast::<PyDict>() {
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
}

#[pymethods]
impl PyLogger {
    fn emit_record(&self, record: LogRecord) {
        let local_handlers = self.local_handlers.lock().unwrap();

        // 1. Handle Rust handlers
        if local_handlers.is_empty() {
            drop(local_handlers);
            let global_handlers = HANDLERS.lock().unwrap();
            for handler in global_handlers.iter() {
                let _ = futures::executor::block_on(handler.emit(&record));
            }
        } else {
            for handler in local_handlers.iter() {
                let _ = futures::executor::block_on(handler.emit(&record));
            }

            let should_propagate = *self.propagate.lock().unwrap();
            if should_propagate {
                drop(local_handlers);
                let global_handlers = HANDLERS.lock().unwrap();
                for handler in global_handlers.iter() {
                    let _ = futures::executor::block_on(handler.emit(&record));
                }
            }
        }

        // 2. Handle Python handlers (like pytest's caplog)
        // Overhead is just a lock + empty check if no Python handlers are registered.
        Python::with_gil(|py| {
            let py_handlers = crate::globals::PYTHON_HANDLERS_KEEP_ALIVE.lock().unwrap();
            if !py_handlers.is_empty() {
                // Convert Rust record to Python record for compatibility
                if let Ok(py_record) = self.makeRecord(
                    py,
                    record.name.clone(),
                    record.levelno,
                    record.pathname.clone(),
                    record.lineno as i32,
                    record.msg.clone().into_py_any(py).unwrap().into(),
                    record
                        .args
                        .clone()
                        .into_py_any(py)
                        .unwrap_or_else(|_| py.None())
                        .into(),
                    record
                        .exc_info
                        .clone()
                        .into_py_any(py)
                        .unwrap_or_else(|_| py.None())
                        .into(),
                ) {
                    for handler in py_handlers.iter() {
                        let _ = handler.call_method1(py, "handle", (&py_record,));
                    }
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

    fn setLevel(&mut self, level: u32) -> PyResult<()> {
        let level = LogLevel::from_usize(level as usize);
        self.fast_logger.set_level(level);
        self.inner.lock().unwrap().set_level(level);
        Ok(())
    }

    fn getEffectiveLevel(&self) -> PyResult<u32> {
        Ok(self.fast_logger.get_level() as u32)
    }

    fn addHandler(&self, _py: Python, handler: &Bound<PyAny>) -> PyResult<()> {
        let added = add_handler_to_registry(handler, &self.fast_logger.name, &self.local_handlers)?;

        if added {
            Ok(())
        } else {
            Err(PyValueError::new_err(
                "LogXide only supports Rust native handlers.",
            ))
        }
    }

    fn format_message(&self, py: Python, msg: Py<PyAny>, args: &Bound<PyAny>) -> PyResult<String> {
        let msg_str = msg.bind(py);
        if let Ok(args_tuple) = args.downcast::<PyTuple>() {
            if !args_tuple.is_empty() {
                let formatted = msg_str.call_method1("__mod__", (args_tuple,))?;
                return Ok(formatted.str()?.to_string());
            }
        }
        Ok(msg_str.str()?.to_string())
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
        let formatted_msg = self
            .format_message(py, msg.clone_ref(py), args)
            .unwrap_or_default();
        let record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Debug,
            formatted_msg,
            extra_fields,
        );
        self.emit_record(record);
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
        let formatted_msg = self
            .format_message(py, msg.clone_ref(py), args)
            .unwrap_or_default();
        let record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Info,
            formatted_msg,
            extra_fields,
        );
        self.emit_record(record);
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
        let formatted_msg = self
            .format_message(py, msg.clone_ref(py), args)
            .unwrap_or_default();
        let record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Warning,
            formatted_msg,
            extra_fields,
        );
        self.emit_record(record);
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
        let formatted_msg = self
            .format_message(py, msg.clone_ref(py), args)
            .unwrap_or_default();
        let record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Error,
            formatted_msg,
            extra_fields,
        );
        self.emit_record(record);
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
        let formatted_msg = self
            .format_message(py, msg.clone_ref(py), args)
            .unwrap_or_default();
        let record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            LogLevel::Critical,
            formatted_msg,
            extra_fields,
        );
        self.emit_record(record);
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
        let mut formatted_msg = self
            .format_message(py, msg.clone_ref(py), args)
            .unwrap_or_default();
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
        self.emit_record(record);
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
        let formatted_msg = self
            .format_message(py, msg.clone_ref(py), args)
            .unwrap_or_default();
        let record = create_log_record_with_extra(
            self.fast_logger.name.to_string(),
            log_level,
            formatted_msg,
            extra_fields,
        );
        self.emit_record(record);
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
        let record = py.import("logging")?.call_method0("makeLogRecord")?;
        record.setattr("name", name)?;
        record.setattr("levelno", level)?;
        record.setattr("pathname", fn_)?;
        record.setattr("lineno", lno)?;
        record.setattr("msg", msg)?;
        record.setattr("args", args)?;
        record.setattr("exc_info", exc_info)?;
        Ok(record.unbind().into_any())
    }

    fn handle(&self, record: Py<PyAny>) -> PyResult<()> {
        Python::with_gil(|py| {
            let handlers = crate::globals::PYTHON_HANDLERS_KEEP_ALIVE.lock().unwrap();
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
