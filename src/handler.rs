use async_trait::async_trait;
use chrono::TimeZone;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::sync::Arc;
use std::sync::Mutex;

use crate::core::{LogLevel, LogRecord};
use crate::filter::Filter;
use crate::formatter::Formatter;

/// Trait for all log handlers. Now async-aware.
#[async_trait::async_trait]
pub trait Handler: Send + Sync {
    /// Emit a log record asynchronously.
    async fn emit(&self, record: &LogRecord);

    /// Set the formatter for this handler.
    #[allow(dead_code)]
    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>);

    /// Add a filter to this handler.
    #[allow(dead_code)]
    fn add_filter(&mut self, filter: Arc<dyn Filter + Send + Sync>);
}

/// Handler that wraps a Python callable.
/// When a log record is emitted, this handler calls the Python function.
pub struct PythonHandler {
    pub py_callable: PyObject,
    #[allow(dead_code)]
    pub py_id: usize,
    pub formatter: Option<Arc<dyn Formatter + Send + Sync>>,
    pub filters: Vec<Arc<dyn Filter + Send + Sync>>,
}

impl PythonHandler {
    pub fn new(py_callable: PyObject) -> Self {
        let py_id = Python::with_gil(|py| {
            py_callable
                .as_ref(py)
                .getattr("__hash__")
                .and_then(|h| h.call0())
                .and_then(|v| v.extract::<isize>())
                .map(|v| v as usize)
                .unwrap_or(0)
        });
        Self {
            py_callable,
            py_id,
            formatter: None,
            filters: Vec::new(),
        }
    }

    pub fn with_id(py_callable: PyObject, py_id: usize) -> Self {
        Self {
            py_callable,
            py_id,
            formatter: None,
            filters: Vec::new(),
        }
    }

    #[allow(dead_code)]
    pub fn id(&self) -> usize {
        self.py_id
    }
}

#[async_trait]
impl Handler for PythonHandler {
    async fn emit(&self, record: &LogRecord) {
        Python::with_gil(|py| {
            let py_record = PyDict::new(py);
            py_record.set_item("name", &record.name).ok();
            py_record.set_item("levelno", record.levelno).ok();
            py_record.set_item("levelname", &record.levelname).ok();
            py_record.set_item("pathname", &record.pathname).ok();
            py_record.set_item("filename", &record.filename).ok();
            py_record.set_item("module", &record.module).ok();
            py_record.set_item("lineno", record.lineno).ok();
            py_record.set_item("funcName", &record.func_name).ok();
            py_record.set_item("created", record.created).ok();
            py_record.set_item("msecs", record.msecs).ok();
            py_record
                .set_item("relativeCreated", record.relative_created)
                .ok();
            py_record.set_item("thread", record.thread).ok();
            py_record.set_item("threadName", &record.thread_name).ok();
            py_record.set_item("processName", &record.process_name).ok();
            py_record.set_item("process", record.process).ok();
            py_record.set_item("msg", &record.msg).ok();
            // Optionals omitted for brevity

            let _ = self.py_callable.call1(py, (py_record,));
        });
    }

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        self.formatter = Some(formatter);
    }

    fn add_filter(&mut self, filter: Arc<dyn Filter + Send + Sync>) {
        self.filters.push(filter);
    }
}

/// Simple console handler that writes to stdout
pub struct ConsoleHandler {
    pub level: Mutex<LogLevel>,
    pub formatter: Option<Arc<dyn Formatter + Send + Sync>>,
    pub filters: Vec<Arc<dyn Filter + Send + Sync>>,
}

impl ConsoleHandler {
    #[allow(dead_code)]
    pub fn new() -> Self {
        Self {
            level: Mutex::new(LogLevel::Warning),
            formatter: None,
            filters: Vec::new(),
        }
    }

    #[allow(dead_code)]
    pub fn with_level(level: LogLevel) -> Self {
        Self {
            level: Mutex::new(level),
            formatter: None,
            filters: Vec::new(),
        }
    }

    pub fn with_formatter(level: LogLevel, formatter: Arc<dyn Formatter + Send + Sync>) -> Self {
        Self {
            level: Mutex::new(level),
            formatter: Some(formatter),
            filters: Vec::new(),
        }
    }

    #[allow(dead_code)]
    pub fn set_formatter_arc(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        self.formatter = Some(formatter);
    }
}

#[async_trait]
impl Handler for ConsoleHandler {
    async fn emit(&self, record: &LogRecord) {
        // Check if we should log this record based on level
        let level = self.level.lock().unwrap();
        if record.levelno < *level as i32 {
            return;
        }

        // Format the record using the formatter if available
        let output = if let Some(ref formatter) = self.formatter {
            formatter.format(record)
        } else {
            // Default format if no formatter is set
            format!(
                "[{}] [Thread-{} {}] {} {} - {}",
                chrono::Local
                    .timestamp_opt(record.created as i64, (record.msecs * 1_000_000.0) as u32)
                    .single()
                    .unwrap_or_else(chrono::Local::now)
                    .format("%Y-%m-%d %H:%M:%S%.3f"),
                record.thread,
                record.thread_name,
                record.levelname,
                record.name,
                record.msg
            )
        };

        // Use sync println to avoid async ordering issues
        use std::io::{self, Write};
        println!("{}", output);
        io::stdout().flush().unwrap();
    }

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        self.formatter = Some(formatter);
    }

    fn add_filter(&mut self, filter: Arc<dyn Filter + Send + Sync>) {
        self.filters.push(filter);
    }
}
