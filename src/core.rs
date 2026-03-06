//! # Core Logging Components
//!
//! This module contains the fundamental data structures and logic for the LogXide logging system.
//! It provides Rust implementations of Python logging concepts including loggers, log records,
//! and a hierarchical logger management system.

#![allow(dead_code)]

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::thread;

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};
use pyo3::IntoPyObjectExt;
use serde::{Deserialize, Serialize};
use serde_json::Value;

/// Log levels, matching Python's logging levels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum LogLevel {
    NotSet = 0,
    Debug = 10,
    Info = 20,
    Warning = 30,
    Error = 40,
    Critical = 50,
}

impl LogLevel {
    pub fn from_usize(level: usize) -> LogLevel {
        match level {
            10 => LogLevel::Debug,
            20 => LogLevel::Info,
            30 => LogLevel::Warning,
            40 => LogLevel::Error,
            50 => LogLevel::Critical,
            _ => LogLevel::NotSet,
        }
    }
}

/// Convert a serde_json::Value to a Python object.
/// When `as_tuple` is true, top-level arrays become PyTuple (for `msg % args` formatting).
/// When `as_tuple` is false, arrays become PyList (for nested data like extra fields).
fn json_value_to_py_inner(py: Python, value: &Value, as_tuple: bool) -> PyResult<Py<PyAny>> {
    match value {
        Value::Null => Ok(py.None()),
        Value::Bool(b) => b.into_py_any(py),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                i.into_py_any(py)
            } else if let Some(f) = n.as_f64() {
                f.into_py_any(py)
            } else {
                Ok(py.None())
            }
        }
        Value::String(s) => s.clone().into_py_any(py),
        Value::Array(arr) => {
            let items: Vec<Py<PyAny>> = arr
                .iter()
                .map(|v| json_value_to_py_inner(py, v, false)) // nested arrays always PyList
                .collect::<PyResult<Vec<_>>>()?;
            if as_tuple {
                Ok(PyTuple::new(py, &items).expect("Failed to create PyTuple").into_any().unbind())
            } else {
                Ok(pyo3::types::PyList::new(py, &items).expect("Failed to create PyList").into_any().unbind())
            }
        }
        Value::Object(map) => {
            let dict = PyDict::new(py);
            for (k, v) in map {
                let py_val = json_value_to_py_inner(py, v, false)?;
                dict.set_item(k, py_val).expect("Failed to set dict item");
            }
            Ok(dict.into_any().unbind())
        }
    }
}

/// Convert a serde_json::Value to a Python object.
/// Top-level arrays become PyTuple (needed for `msg % args` formatting).
/// Nested arrays become PyList. Objects become PyDict.
pub fn json_value_to_py(py: Python, value: &Value) -> PyResult<Py<PyAny>> {
    json_value_to_py_inner(py, value, true)
}

/// Convert a serde_json::Value to a Python object.
/// ALL arrays become PyList (for extra fields, __dict__, etc.).
pub fn json_value_to_py_as_list(py: Python, value: &Value) -> PyResult<Py<PyAny>> {
    json_value_to_py_inner(py, value, false)
}

/// Complete log record structure for compatibility with Python logging.
#[pyclass(from_py_object)]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogRecord {
    #[pyo3(get, set)]
    pub name: String,
    #[pyo3(get, set)]
    pub levelno: i32,
    #[pyo3(get, set)]
    pub levelname: String,
    #[pyo3(get, set)]
    pub pathname: String,
    #[pyo3(get, set)]
    pub filename: String,
    #[pyo3(get, set)]
    pub module: String,
    #[pyo3(get, set)]
    pub lineno: u32,
    #[pyo3(get, set)]
    pub func_name: String,
    #[pyo3(get, set)]
    pub created: f64,
    #[pyo3(get, set)]
    pub msecs: f64,
    #[pyo3(get, set)]
    pub relative_created: f64,
    #[pyo3(get, set)]
    pub thread: u64,
    #[pyo3(get, set)]
    pub thread_name: String,
    #[pyo3(get, set)]
    pub process_name: String,
    #[pyo3(get, set)]
    pub process: u32,
    #[pyo3(get, set)]
    pub msg: String,
    pub args: Option<String>,
    #[pyo3(get, set)]
    pub exc_info: Option<String>,
    #[pyo3(get, set)]
    pub exc_text: Option<String>,
    #[pyo3(get, set)]
    pub stack_info: Option<String>,
    #[pyo3(get, set)]
    pub task_name: Option<String>,
    #[serde(default)]
    pub extra: Option<HashMap<String, Value>>,
}

#[pymethods]
impl LogRecord {
    #[new]
    #[pyo3(signature = (name, levelno, pathname, lineno, msg, args=None, exc_info=None, func_name=String::new(), stack_info=None))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        name: String,
        levelno: i32,
        pathname: String,
        lineno: u32,
        msg: String,
        args: Option<String>,
        exc_info: Option<String>,
        func_name: String,
        stack_info: Option<String>,
    ) -> Self {
        LogRecord {
            name,
            levelno,
            levelname: "".into(),
            pathname,
            filename: "".into(),
            module: "".into(),
            lineno,
            func_name,
            created: 0.0,
            msecs: 0.0,
            relative_created: 0.0,
            thread: 0,
            thread_name: "".into(),
            process_name: "".into(),
            process: 0,
            msg,
            args,
            exc_info,
            exc_text: None,
            stack_info,
            task_name: None,
            extra: None,
        }
    }

    #[getter]
    fn args(&self, py: Python) -> PyResult<Py<PyAny>> {
        match &self.args {
            None => Ok(py.None()),
            Some(json_str) => {
                let value: Value = serde_json::from_str(json_str)
                    .expect("LogRecord.args contains invalid JSON");
                json_value_to_py(py, &value)
            }
        }
    }

    #[setter]
    fn set_args(&mut self, py: Python, value: Py<PyAny>) -> PyResult<()> {
        let bound = value.bind(py);
        if bound.is_none() {
            self.args = None;
        } else {
            let json_val = crate::py_logger::py_to_json_value(bound);
            self.args = Some(serde_json::to_string(&json_val)
                .expect("Failed to serialize args to JSON"));
        }
        Ok(())
    }

    fn getMessage(&self, py: Python) -> PyResult<String> {
        match &self.args {
            None => Ok(self.msg.clone()),
            Some(json_str) => {
                let value: Value = serde_json::from_str(json_str)
                    .expect("LogRecord.args contains invalid JSON");
                let py_args = json_value_to_py(py, &value)?;
                let py_msg = self.msg.as_str().into_pyobject(py)?;
                let formatted = py_msg.call_method1("__mod__", (py_args,))?;
                Ok(formatted.str()?.to_string())
            }
        }
    }

    #[getter]
    fn message(&self, py: Python) -> PyResult<String> {
        self.getMessage(py)
    }

    fn __getattr__(&self, py: Python, name: &str) -> PyResult<Py<PyAny>> {
        if let Some(ref extra) = self.extra {
            if let Some(value) = extra.get(name) {
                return json_value_to_py_as_list(py, value);
            }
        }
        Err(pyo3::exceptions::PyAttributeError::new_err(
            format!("'LogRecord' object has no attribute '{}'", name)
        ))
    }

    #[getter(funcName)]
    fn func_name_alias(&self) -> String {
        self.func_name.clone()
    }

    #[getter(relativeCreated)]
    fn relative_created_alias(&self) -> f64 {
        self.relative_created
    }

    #[getter(threadName)]
    fn thread_name_alias(&self) -> String {
        self.thread_name.clone()
    }

    #[getter(processName)]
    fn process_name_alias(&self) -> String {
        self.process_name.clone()
    }

    fn __setattr__(&mut self, py: Python, name: &str, value: Py<PyAny>) -> PyResult<()> {
        let bound = value.bind(py);
        match name {
            "name" => self.name = bound.extract()?,
            "levelno" => self.levelno = bound.extract()?,
            "levelname" => self.levelname = bound.extract()?,
            "pathname" => self.pathname = bound.extract()?,
            "filename" => self.filename = bound.extract()?,
            "module" => self.module = bound.extract()?,
            "lineno" => self.lineno = bound.extract()?,
            "func_name" | "funcName" => self.func_name = bound.extract()?,
            "created" => self.created = bound.extract()?,
            "msecs" => self.msecs = bound.extract()?,
            "relative_created" | "relativeCreated" => self.relative_created = bound.extract()?,
            "thread" => self.thread = bound.extract()?,
            "thread_name" | "threadName" => self.thread_name = bound.extract()?,
            "process_name" | "processName" => self.process_name = bound.extract()?,
            "process" => self.process = bound.extract()?,
            "msg" => self.msg = bound.extract()?,
            "args" => {
                if bound.is_none() {
                    self.args = None;
                } else {
                    let json_val = crate::py_logger::py_to_json_value(bound);
                    self.args = Some(serde_json::to_string(&json_val)
                        .expect("Failed to serialize args to JSON"));
                }
            }
            "exc_info" => self.exc_info = bound.extract()?,
            "exc_text" => self.exc_text = bound.extract()?,
            "stack_info" => self.stack_info = bound.extract()?,
            "task_name" => self.task_name = bound.extract()?,
            _ => {
                let json_val = crate::py_logger::py_to_json_value(bound);
                let extra = self.extra.get_or_insert_with(HashMap::new);
                extra.insert(name.to_string(), json_val);
            }
        }
        Ok(())
    }

    #[getter(__dict__)]
    fn get_dict(&self, py: Python) -> PyResult<Py<PyAny>> {
        let dict = PyDict::new(py);
        dict.set_item("name", &self.name)?;
        dict.set_item("levelno", self.levelno)?;
        dict.set_item("levelname", &self.levelname)?;
        dict.set_item("pathname", &self.pathname)?;
        dict.set_item("filename", &self.filename)?;
        dict.set_item("module", &self.module)?;
        dict.set_item("lineno", self.lineno)?;
        dict.set_item("func_name", &self.func_name)?;
        dict.set_item("funcName", &self.func_name)?;
        dict.set_item("created", self.created)?;
        dict.set_item("msecs", self.msecs)?;
        dict.set_item("relative_created", self.relative_created)?;
        dict.set_item("relativeCreated", self.relative_created)?;
        dict.set_item("thread", self.thread)?;
        dict.set_item("thread_name", &self.thread_name)?;
        dict.set_item("threadName", &self.thread_name)?;
        dict.set_item("process_name", &self.process_name)?;
        dict.set_item("processName", &self.process_name)?;
        dict.set_item("process", self.process)?;
        dict.set_item("msg", &self.msg)?;
        dict.set_item("message", &self.msg)?;
        match &self.args {
            None => dict.set_item("args", py.None())?,
            Some(json_str) => {
                let value: Value = serde_json::from_str(json_str)
                    .expect("LogRecord.args contains invalid JSON");
                dict.set_item("args", json_value_to_py(py, &value)?)?;
            }
        }
        dict.set_item("exc_info", &self.exc_info)?;
        dict.set_item("exc_text", &self.exc_text)?;
        dict.set_item("stack_info", &self.stack_info)?;
        dict.set_item("task_name", &self.task_name)?;
        if let Some(ref extra) = self.extra {
            for (key, value) in extra {
                dict.set_item(key, json_value_to_py_as_list(py, value)?)?;
            }
        }
        Ok(dict.into_any().unbind())
    }
}

impl LogRecord {
    pub fn get_message(&self) -> String {
        match &self.args {
            None => self.msg.clone(),
            Some(json_str) => {
                Python::attach(|py| {
                    let value: Value = serde_json::from_str(json_str)
                        .expect("LogRecord.args contains invalid JSON");
                    let py_args = json_value_to_py(py, &value)
                        .expect("Failed to convert args to Python object");
                    let py_msg = self.msg.as_str().into_pyobject(py)
                        .expect("Failed to convert msg to Python string");
                    let formatted = py_msg.call_method1("__mod__", (py_args,))
                        .expect("String formatting (msg % args) failed");
                    formatted.str()
                        .expect("Formatted result is not a string")
                        .to_string()
                })
            }
        }
    }
}

pub struct Logger {
    pub name: String,
    pub level: LogLevel,
    pub handlers: Vec<Arc<dyn crate::handler::Handler + Send + Sync>>,
    pub filters: Vec<Arc<dyn crate::filter::Filter + Send + Sync>>,
    pub parent: Option<Arc<Mutex<Logger>>>,
    pub propagate: bool,
}

pub fn create_log_record(name: String, level: LogLevel, msg: String) -> LogRecord {
    create_log_record_with_extra(name, level, msg, None)
}

pub fn create_log_record_with_extra(
    name: String,
    level: LogLevel,
    msg: String,
    extra: Option<HashMap<String, Value>>,
) -> LogRecord {
    use crate::string_cache::{get_common_message, get_level_name, get_logger_name};

    let now = chrono::Local::now();
    let created = now.timestamp() as f64 + now.timestamp_subsec_nanos() as f64 / 1_000_000_000.0;
    let msecs = (now.timestamp_subsec_millis() % 1000) as f64;

    let current_thread = thread::current();
    let thread_id = format!("{:?}", current_thread.id());
    let thread_name = crate::THREAD_NAME
        .with(|custom_name| custom_name.borrow().clone())
        .unwrap_or_else(|| current_thread.name().unwrap_or("unnamed").to_string());

    let thread_numeric_id = thread_id
        .trim_start_matches("ThreadId(")
        .trim_end_matches(")")
        .parse::<u64>()
        .unwrap_or(0);

    LogRecord {
        name: get_logger_name(&name).to_string(),
        levelno: level as i32,
        levelname: get_level_name(level).to_string(),
        pathname: "".to_string(),
        filename: "".to_string(),
        module: "".to_string(),
        lineno: 0,
        func_name: "".to_string(),
        created,
        msecs,
        relative_created: 0.0,
        thread: thread_numeric_id,
        thread_name,
        process_name: "".to_string(),
        process: std::process::id(),
        msg: get_common_message(&msg).to_string(),
        args: None,
        exc_info: None,
        exc_text: None,
        stack_info: None,
        task_name: None,
        extra,
    }
}

impl Logger {
    pub fn new(name: &str) -> Self {
        Logger {
            name: name.to_string(),
            level: LogLevel::NotSet,
            handlers: Vec::new(),
            filters: Vec::new(),
            parent: None,
            propagate: true,
        }
    }

    pub fn set_level(&mut self, level: LogLevel) {
        self.level = level;
    }

    pub fn get_effective_level(&self) -> LogLevel {
        if self.level != LogLevel::NotSet {
            return self.level;
        }
        if let Some(ref parent) = self.parent {
            return parent.lock().unwrap().get_effective_level();
        }
        LogLevel::Warning
    }

    pub fn add_handler(&mut self, handler: Arc<dyn crate::handler::Handler + Send + Sync>) {
        self.handlers.push(handler);
    }

    pub fn is_enabled_for(&self, level: LogLevel) -> bool {
        level >= self.get_effective_level()
    }

    pub fn log(&self, level: LogLevel, msg: &str) {
        if self.is_enabled_for(level) {
            let record = create_log_record(self.name.clone(), level, msg.to_string());
            self.handle(record);
        }
    }

    pub fn debug(&self, msg: &str) {
        self.log(LogLevel::Debug, msg);
    }
    pub fn info(&self, msg: &str) {
        self.log(LogLevel::Info, msg);
    }
    pub fn warning(&self, msg: &str) {
        self.log(LogLevel::Warning, msg);
    }
    pub fn error(&self, msg: &str) {
        self.log(LogLevel::Error, msg);
    }
    pub fn critical(&self, msg: &str) {
        self.log(LogLevel::Critical, msg);
    }

    pub fn handle(&self, record: LogRecord) {
        for filter in &self.filters {
            if !filter.filter(&record) {
                return;
            }
        }
        for handler in &self.handlers {
            let handler = handler.clone();
            let record = record.clone();
            futures::executor::block_on(handler.emit(&record));
        }
        if self.propagate {
            if let Some(ref parent) = self.parent {
                parent.lock().unwrap().handle(record);
            }
        }
    }
}

pub struct LoggerManager {
    pub loggers: Mutex<HashMap<String, Arc<Mutex<Logger>>>>,
    pub root: Arc<Mutex<Logger>>,
}

impl Default for LoggerManager {
    fn default() -> Self {
        Self::new()
    }
}

impl LoggerManager {
    pub fn new() -> Self {
        let root_logger = Arc::new(Mutex::new(Logger::new("root")));
        LoggerManager {
            loggers: Mutex::new(HashMap::new()),
            root: root_logger.clone(),
        }
    }

    pub fn get_logger(&self, name: &str) -> Arc<Mutex<Logger>> {
        {
            let loggers = self.loggers.lock().unwrap();
            if let Some(logger) = loggers.get(name) {
                return logger.clone();
            }
        }
        let parent_logger = if name != "root" {
            let parent_name = name.rsplit_once('.').map(|x| x.0).unwrap_or("root");
            Some(self.get_logger(parent_name))
        } else {
            None
        };
        let logger = Arc::new(Mutex::new(Logger::new(name)));
        if let Some(parent) = parent_logger {
            logger.lock().unwrap().parent = Some(parent);
        }
        let mut loggers = self.loggers.lock().unwrap();
        loggers.insert(name.to_string(), logger.clone());
        logger
    }

    pub fn get_root_logger(&self) -> Arc<Mutex<Logger>> {
        self.root.clone()
    }
}

use once_cell::sync::Lazy;
pub static LOGGER_MANAGER: Lazy<LoggerManager> = Lazy::new(LoggerManager::new);

pub fn get_logger(name: &str) -> Arc<Mutex<Logger>> {
    LOGGER_MANAGER.get_logger(name)
}

pub fn get_root_logger() -> Arc<Mutex<Logger>> {
    LOGGER_MANAGER.get_root_logger()
}
