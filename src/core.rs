#![allow(dead_code)]

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::thread;

use pyo3::conversion::FromPyObject;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyTuple};

/// Log levels, matching Python's logging levels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
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

/// LogRecord struct, detailed version for compatibility with Python logging.
#[derive(Debug, Clone)]
pub struct LogRecord {
    pub name: String,
    pub levelno: i32,
    pub levelname: String,
    pub pathname: String,
    pub filename: String,
    pub module: String,
    pub lineno: u32,
    pub func_name: String,
    pub created: f64,
    pub msecs: f64,
    pub relative_created: f64,
    pub thread: u64,
    pub thread_name: String,
    pub process_name: String,
    pub process: u32,
    pub msg: String,
    pub args: Option<Py<PyTuple>>,
    pub exc_info: Option<Py<PyAny>>,
    pub exc_text: Option<String>,
    pub stack_info: Option<String>,
    pub task_name: Option<String>,
}

// Implement FromPyObject for LogRecord
impl<'source> FromPyObject<'source> for LogRecord {
    fn extract(obj: &'source PyAny) -> PyResult<Self> {
        Ok(LogRecord {
            name: obj.getattr("name").unwrap().extract().unwrap(),
            levelno: obj.getattr("levelno").unwrap().extract().unwrap(),
            levelname: obj.getattr("levelname").unwrap().extract().unwrap(),
            pathname: obj.getattr("pathname").unwrap().extract().unwrap(),
            filename: obj.getattr("filename").unwrap().extract().unwrap(),
            module: obj.getattr("module").unwrap().extract().unwrap(),
            lineno: obj.getattr("lineno").unwrap().extract().unwrap(),
            func_name: obj.getattr("funcName").unwrap().extract().unwrap(),
            created: obj.getattr("created").unwrap().extract().unwrap(),
            msecs: obj.getattr("msecs").unwrap().extract().unwrap(),
            relative_created: obj.getattr("relativeCreated").unwrap().extract().unwrap(),
            thread: obj.getattr("thread").unwrap().extract().unwrap(),
            thread_name: obj.getattr("threadName").unwrap().extract().unwrap(),
            process_name: obj.getattr("processName").unwrap().extract().unwrap(),
            process: obj.getattr("process").unwrap().extract().unwrap(),
            msg: obj.getattr("msg").unwrap().extract().unwrap(),
            args: obj.getattr("args").ok().and_then(|v| v.extract().ok()),
            exc_info: obj.getattr("exc_info").ok().and_then(|v| v.extract().ok()),
            exc_text: obj.getattr("exc_text").ok().and_then(|v| v.extract().ok()),
            stack_info: obj
                .getattr("stack_info")
                .ok()
                .and_then(|v| v.extract().ok()),
            task_name: obj.getattr("taskName").ok().and_then(|v| v.extract().ok()),
        })
    }
}

/// Logger struct, supports hierarchical loggers.
pub struct Logger {
    pub name: String,
    pub level: LogLevel,
    pub handlers: Vec<Arc<dyn crate::handler::Handler + Send + Sync>>,
    pub filters: Vec<Arc<dyn crate::filter::Filter + Send + Sync>>,
    pub parent: Option<Arc<Mutex<Logger>>>,
    pub propagate: bool,
}

/// Helper function to create a LogRecord with current thread and time info
pub fn create_log_record(name: String, level: LogLevel, msg: String) -> LogRecord {
    let now = chrono::Local::now();
    let created = now.timestamp() as f64 + now.timestamp_subsec_nanos() as f64 / 1_000_000_000.0;
    let msecs = (now.timestamp_subsec_millis() % 1000) as f64;

    // Get thread info
    let current_thread = thread::current();
    let thread_id = format!("{:?}", current_thread.id());

    // First try to get Python thread name, fall back to native thread name
    let thread_name = {
        use crate::THREAD_NAMES;
        let thread_names = THREAD_NAMES.lock().unwrap();
        thread_names
            .get(&current_thread.id())
            .cloned()
            .unwrap_or_else(|| current_thread.name().unwrap_or("unnamed").to_string())
    };

    // Extract numeric thread ID (this is platform-specific)
    let thread_numeric_id = thread_id
        .trim_start_matches("ThreadId(")
        .trim_end_matches(")")
        .parse::<u64>()
        .unwrap_or(0);

    LogRecord {
        name,
        levelno: level as i32,
        levelname: format!("{:?}", level).to_uppercase(),
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
        msg,
        args: None,
        exc_info: None,
        exc_text: None,
        stack_info: None,
        task_name: None,
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

    /// Construct a LogRecord from a message and level.
    pub fn make_log_record(&self, level: LogLevel, msg: &str) -> crate::core::LogRecord {
        crate::core::LogRecord {
            name: self.name.clone(),
            levelno: level as i32,
            levelname: format!("{:?}", level),
            pathname: "".to_string(),
            filename: "".to_string(),
            module: "".to_string(),
            lineno: 0,
            func_name: "".to_string(),
            created: chrono::Utc::now().timestamp_millis() as f64 / 1000.0,
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
        }
    }

    pub fn set_level(&mut self, level: LogLevel) {
        self.level = level;
    }

    pub fn get_effective_level(&self) -> LogLevel {
        // If this logger has a level set, use it
        if self.level != LogLevel::NotSet {
            return self.level;
        }

        // Otherwise, check parent loggers
        if let Some(ref parent) = self.parent {
            return parent.lock().unwrap().get_effective_level();
        }

        // Default to WARNING if no level is set anywhere
        LogLevel::Warning
    }

    pub fn add_handler(&mut self, handler: Arc<dyn crate::handler::Handler + Send + Sync>) {
        self.handlers.push(handler);
    }

    pub fn remove_handler(&mut self, _handler_id: usize) {
        // Handler removal by id is not implemented; consider implementing if needed
    }

    pub fn add_filter(&mut self, filter: Arc<dyn crate::filter::Filter + Send + Sync>) {
        self.filters.push(filter);
    }

    pub fn remove_filter(&mut self, _filter_id: usize) {
        // Filter removal by id is not implemented; consider implementing if needed
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

    /// Handles a log record: applies filters, passes to handlers, propagates if needed.
    pub fn handle(&self, record: LogRecord) {
        // Apply filters
        for filter in &self.filters {
            if !filter.filter(&record) {
                return;
            }
        }
        // Pass to handlers
        for handler in &self.handlers {
            // Use async emit for handler; in async context, you would .await this
            // Here, we just spawn for demonstration (should be handled in async processor)
            let handler = handler.clone();
            let record = record.clone();
            tokio::spawn(async move {
                handler.emit(&record).await;
            });
        }
        // Propagate to parent if enabled
        if self.propagate {
            if let Some(ref parent) = self.parent {
                parent.lock().unwrap().handle(record);
            }
        }
    }
}

/// LoggerManager: manages logger hierarchy and registry.
pub struct LoggerManager {
    pub loggers: Mutex<HashMap<String, Arc<Mutex<Logger>>>>,
    pub root: Arc<Mutex<Logger>>,
}

impl LoggerManager {
    pub fn new() -> Self {
        let root_logger = Arc::new(Mutex::new(Logger::new("root")));
        LoggerManager {
            loggers: Mutex::new(HashMap::new()),
            root: root_logger.clone(),
        }
    }

    /// Get or create a logger by name, supporting hierarchy.
    pub fn get_logger(&self, name: &str) -> Arc<Mutex<Logger>> {
        // First, check if the logger already exists
        {
            let loggers = self.loggers.lock().unwrap();
            if let Some(logger) = loggers.get(name) {
                return logger.clone();
            }
        }

        // If not, create the parent logger first (if needed)
        let parent_logger = if name != "root" {
            let parent_name = name.rsplit_once('.').map(|x| x.0).unwrap_or("root");
            Some(self.get_logger(parent_name))
        } else {
            None
        };

        // Now create the logger and insert it
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

// Global logger manager instance (singleton)
use once_cell::sync::Lazy;
pub static LOGGER_MANAGER: Lazy<LoggerManager> = Lazy::new(LoggerManager::new);

/// Public API: getLogger
pub fn get_logger(name: &str) -> Arc<Mutex<Logger>> {
    LOGGER_MANAGER.get_logger(name)
}

/// Public API: get root logger
pub fn get_root_logger() -> Arc<Mutex<Logger>> {
    LOGGER_MANAGER.get_root_logger()
}
