//! # Log Handlers
//!
//! This module provides handler implementations for processing log records.
//! Handlers are responsible for outputting log records to their final destinations
//! such as console, files, network services, or Python logging handlers.
//!
//! ## Handler Types
//!
//! - **PythonHandler**: Wraps Python callable objects for compatibility
//! - **ConsoleHandler**: Outputs formatted log records to stdout
//!
//! ## Async Design
//!
//! All handlers implement an async `emit` method to ensure non-blocking
//! log processing in the async runtime. This allows high-throughput logging
//! without blocking application threads.
//!
//! ## Filtering and Formatting
//!
//! Handlers can have their own filters and formatters, providing fine-grained
//! control over which records are processed and how they are presented.

use async_trait::async_trait;
use chrono::TimeZone;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::fs::{File, OpenOptions};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::sync::Mutex;

use crate::core::{LogLevel, LogRecord};
use crate::filter::Filter;
use crate::formatter::Formatter;

/// Trait for all log handlers with async processing capabilities.
///
/// Handlers are responsible for the final processing and output of log records.
/// All handlers must be thread-safe (Send + Sync) and support async emission
/// for high-performance logging in async contexts.
///
/// # Design Philosophy
///
/// Handlers implement async `emit` to avoid blocking the logging system.
/// They can optionally have formatters to control output format and filters
/// to determine which records to process.
#[async_trait::async_trait]
pub trait Handler: Send + Sync {
    /// Emit a log record asynchronously.
    ///
    /// This is the core method where handlers process log records.
    /// Implementations should be non-blocking and efficient.
    ///
    /// # Arguments
    ///
    /// * `record` - The log record to process
    async fn emit(&self, record: &LogRecord);

    /// Set the formatter for this handler.
    ///
    /// Formatters control how log records are converted to strings
    /// for output. If no formatter is set, handlers should provide
    /// a reasonable default format.
    ///
    /// # Arguments
    ///
    /// * `formatter` - The formatter to use for this handler
    #[allow(dead_code)]
    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>);

    /// Add a filter to this handler.
    ///
    /// Filters allow handlers to selectively process records based
    /// on custom criteria beyond just log level.
    ///
    /// # Arguments
    ///
    /// * `filter` - The filter to add to this handler
    #[allow(dead_code)]
    fn add_filter(&mut self, filter: Arc<dyn Filter + Send + Sync>);
}

/// Handler that wraps a Python callable for compatibility with Python logging.
///
/// This handler allows LogXide to interface with existing Python logging
/// infrastructure by accepting Python handler objects and calling them
/// with properly formatted log records.
///
/// # Compatibility
///
/// The handler converts Rust LogRecord structs to Python dict objects
/// that match the format expected by Python logging handlers.
///
/// # Thread Safety
///
/// Uses PyO3's GIL management to safely call Python code from Rust threads.
pub struct PythonHandler {
    /// Python callable object (typically a logging.Handler instance)
    pub py_callable: PyObject,
    /// Unique identifier for this handler instance
    #[allow(dead_code)]
    pub py_id: usize,
    /// Optional formatter for this handler
    pub formatter: Option<Arc<dyn Formatter + Send + Sync>>,
    /// List of filters applied to records before emission
    pub filters: Vec<Arc<dyn Filter + Send + Sync>>,
}

impl PythonHandler {
    /// Create a new PythonHandler wrapping a Python callable.
    ///
    /// The handler will attempt to generate a unique ID by calling
    /// the Python object's __hash__ method.
    ///
    /// # Arguments
    ///
    /// * `py_callable` - Python object that can be called with log records
    ///
    /// # Returns
    ///
    /// A new PythonHandler instance
    pub fn new(py_callable: PyObject) -> Self {
        let py_id = Python::with_gil(|py| {
            py_callable
                .bind(py)
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

    /// Create a new PythonHandler with an explicit ID.
    ///
    /// This constructor allows specifying the handler ID directly,
    /// which is useful when the ID is already known (e.g., from Python's id() function).
    ///
    /// # Arguments
    ///
    /// * `py_callable` - Python object that can be called with log records
    /// * `py_id` - Unique identifier for this handler
    ///
    /// # Returns
    ///
    /// A new PythonHandler instance with the specified ID
    pub fn with_id(py_callable: PyObject, py_id: usize) -> Self {
        Self {
            py_callable,
            py_id,
            formatter: None,
            filters: Vec::new(),
        }
    }

    /// Get the unique ID for this handler.
    ///
    /// The ID can be used to identify and manage handler instances.
    ///
    /// # Returns
    ///
    /// The unique identifier for this handler
    #[allow(dead_code)]
    pub fn id(&self) -> usize {
        self.py_id
    }
}

/// Implementation of Handler trait for PythonHandler.
///
/// Converts Rust LogRecord to Python dict and calls the wrapped Python callable.
#[async_trait]
impl Handler for PythonHandler {
    /// Emit a log record by calling the wrapped Python callable.
    ///
    /// Converts the LogRecord to a Python dictionary with the same field
    /// names and types as Python's logging.LogRecord, then calls the
    /// Python handler with this dictionary.
    ///
    /// # Arguments
    ///
    /// * `record` - The log record to emit
    async fn emit(&self, record: &LogRecord) {
        Python::with_gil(|py| {
            let py_record = PyDict::new(py);
            py_record.set_item("name", record.name.clone()).ok();
            py_record.set_item("levelno", record.levelno).ok();
            py_record
                .set_item("levelname", record.levelname.clone())
                .ok();
            py_record.set_item("pathname", record.pathname.clone()).ok();
            py_record.set_item("filename", record.filename.clone()).ok();
            py_record.set_item("module", record.module.clone()).ok();
            py_record.set_item("lineno", record.lineno).ok();
            py_record
                .set_item("funcName", record.func_name.clone())
                .ok();
            py_record.set_item("created", record.created).ok();
            py_record.set_item("msecs", record.msecs).ok();
            py_record
                .set_item("relativeCreated", record.relative_created)
                .ok();
            py_record.set_item("thread", record.thread).ok();
            py_record
                .set_item("threadName", record.thread_name.clone())
                .ok();
            py_record
                .set_item("processName", record.process_name.clone())
                .ok();
            py_record.set_item("process", record.process).ok();
            py_record.set_item("msg", record.msg.clone()).ok();
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

/// Simple console handler that writes formatted log records to stdout.
///
/// This handler provides basic console output functionality with support
/// for level filtering, custom formatting, and record filtering.
///
/// # Output Format
///
/// Uses a default timestamp-based format when no formatter is specified.
/// With a formatter, uses the formatter's output exactly.
///
/// # Thread Safety
///
/// The handler level is protected by a Mutex to allow safe concurrent access.
pub struct ConsoleHandler {
    /// Minimum log level to output (protected by Mutex for thread safety)
    pub level: Mutex<LogLevel>,
    /// Optional formatter for customizing output format
    pub formatter: Option<Arc<dyn Formatter + Send + Sync>>,
    /// List of filters applied before output
    pub filters: Vec<Arc<dyn Filter + Send + Sync>>,
}

impl Default for ConsoleHandler {
    fn default() -> Self {
        Self::new()
    }
}

impl ConsoleHandler {
    /// Create a new ConsoleHandler with default settings.
    ///
    /// The handler is initialized with:
    /// - Level: Warning (only warnings and above are shown)
    /// - No formatter (uses built-in format)
    /// - No filters
    ///
    /// # Returns
    ///
    /// A new ConsoleHandler instance
    #[allow(dead_code)]
    pub fn new() -> Self {
        Self {
            level: Mutex::new(LogLevel::Warning),
            formatter: None,
            filters: Vec::new(),
        }
    }

    /// Create a new ConsoleHandler with a specific log level.
    ///
    /// # Arguments
    ///
    /// * `level` - Minimum log level to output
    ///
    /// # Returns
    ///
    /// A new ConsoleHandler instance with the specified level
    #[allow(dead_code)]
    pub fn with_level(level: LogLevel) -> Self {
        Self {
            level: Mutex::new(level),
            formatter: None,
            filters: Vec::new(),
        }
    }

    /// Create a new ConsoleHandler with a specific level and formatter.
    ///
    /// This is the most commonly used constructor for ConsoleHandler
    /// as it allows full customization of both filtering and formatting.
    ///
    /// # Arguments
    ///
    /// * `level` - Minimum log level to output
    /// * `formatter` - Formatter to use for output formatting
    ///
    /// # Returns
    ///
    /// A new ConsoleHandler instance with the specified configuration
    pub fn with_formatter(level: LogLevel, formatter: Arc<dyn Formatter + Send + Sync>) -> Self {
        Self {
            level: Mutex::new(level),
            formatter: Some(formatter),
            filters: Vec::new(),
        }
    }

    /// Set the formatter for this handler.
    ///
    /// This method allows changing the formatter after the handler
    /// has been created.
    ///
    /// # Arguments
    ///
    /// * `formatter` - The new formatter to use
    #[allow(dead_code)]
    pub fn set_formatter_arc(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        self.formatter = Some(formatter);
    }
}

/// Implementation of Handler trait for ConsoleHandler.
///
/// Provides console output with level filtering and optional formatting.
#[async_trait]
impl Handler for ConsoleHandler {
    /// Emit a log record to stdout.
    ///
    /// First checks if the record level meets the handler's minimum level.
    /// Then formats the record using the configured formatter or a default format.
    /// Finally outputs the formatted message to stdout with immediate flushing.
    ///
    /// # Arguments
    ///
    /// * `record` - The log record to emit
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

/// Rotating file handler that automatically rotates log files when they exceed a specified size.
///
/// This handler writes log records to a file and automatically rotates the file when it
/// reaches the maximum size. It maintains a specified number of backup files.
///
/// # File Rotation Strategy
///
/// When the current log file exceeds `max_bytes`:
/// 1. Close the current file
/// 2. Rename existing backup files (log.1 -> log.2, log.2 -> log.3, etc.)
/// 3. Rename the current file to log.1
/// 4. Create a new current file
///
/// # Thread Safety
///
/// All file operations are protected by a Mutex to ensure thread-safe writing
/// and rotation in concurrent environments.
pub struct RotatingFileHandler {
    /// Path to the log file
    pub filename: PathBuf,
    /// Maximum file size before rotation (in bytes)
    pub max_bytes: u64,
    /// Number of backup files to keep
    pub backup_count: u32,
    /// Current file writer (protected by Mutex for thread safety)
    pub writer: Mutex<Option<BufWriter<File>>>,
    /// Current file size (protected by Mutex for thread safety)
    pub current_size: Mutex<u64>,
    /// Minimum log level to output
    pub level: Mutex<LogLevel>,
    /// Optional formatter for customizing output format
    pub formatter: Option<Arc<dyn Formatter + Send + Sync>>,
    /// List of filters applied before output
    pub filters: Vec<Arc<dyn Filter + Send + Sync>>,
}

impl RotatingFileHandler {
    /// Create a new RotatingFileHandler.
    ///
    /// # Arguments
    ///
    /// * `filename` - Path to the log file
    /// * `max_bytes` - Maximum file size before rotation (in bytes)
    /// * `backup_count` - Number of backup files to keep
    ///
    /// # Returns
    ///
    /// A new RotatingFileHandler instance
    pub fn new<P: AsRef<Path>>(filename: P, max_bytes: u64, backup_count: u32) -> Self {
        Self {
            filename: filename.as_ref().to_path_buf(),
            max_bytes,
            backup_count,
            writer: Mutex::new(None),
            current_size: Mutex::new(0),
            level: Mutex::new(LogLevel::Warning),
            formatter: None,
            filters: Vec::new(),
        }
    }

    /// Create a new RotatingFileHandler with a specific level and formatter.
    ///
    /// # Arguments
    ///
    /// * `filename` - Path to the log file
    /// * `max_bytes` - Maximum file size before rotation (in bytes)
    /// * `backup_count` - Number of backup files to keep
    /// * `level` - Minimum log level to output
    /// * `formatter` - Formatter to use for output formatting
    ///
    /// # Returns
    ///
    /// A new RotatingFileHandler instance with the specified configuration
    pub fn with_formatter<P: AsRef<Path>>(
        filename: P,
        max_bytes: u64,
        backup_count: u32,
        level: LogLevel,
        formatter: Arc<dyn Formatter + Send + Sync>,
    ) -> Self {
        Self {
            filename: filename.as_ref().to_path_buf(),
            max_bytes,
            backup_count,
            writer: Mutex::new(None),
            current_size: Mutex::new(0),
            level: Mutex::new(level),
            formatter: Some(formatter),
            filters: Vec::new(),
        }
    }

    /// Get or create the file writer.
    ///
    /// This method ensures that a file writer exists and is ready for writing.
    /// If no writer exists, it creates one and initializes the current size.
    fn ensure_writer(&self) -> Result<(), std::io::Error> {
        let mut writer = self.writer.lock().unwrap();
        let mut current_size = self.current_size.lock().unwrap();

        if writer.is_none() {
            let file = OpenOptions::new()
                .create(true)
                .append(true)
                .open(&self.filename)?;

            // Get the current file size
            *current_size = file.metadata()?.len();
            *writer = Some(BufWriter::new(file));
        }

        Ok(())
    }

    /// Rotate the log file.
    ///
    /// This method performs the file rotation by:
    /// 1. Closing the current writer
    /// 2. Rotating existing backup files
    /// 3. Moving the current file to .1
    /// 4. Creating a new current file
    fn do_rollover(&self) -> Result<(), std::io::Error> {
        // Close the current writer
        {
            let mut writer = self.writer.lock().unwrap();
            if let Some(w) = writer.take() {
                drop(w); // This will flush and close the file
            }
        }

        // Rotate backup files (from highest to lowest)
        for i in (1..self.backup_count).rev() {
            let old_name = format!("{}.{}", self.filename.display(), i);
            let new_name = format!("{}.{}", self.filename.display(), i + 1);

            if Path::new(&old_name).exists() {
                let _ = std::fs::rename(&old_name, &new_name);
            }
        }

        // Move the current file to .1
        if self.filename.exists() {
            let backup_name = format!("{}.1", self.filename.display());
            std::fs::rename(&self.filename, backup_name)?;
        }

        // Reset the current size
        {
            let mut current_size = self.current_size.lock().unwrap();
            *current_size = 0;
        }

        // The next write will create a new file
        Ok(())
    }

    /// Check if rotation is needed and perform it if necessary.
    fn should_rollover(&self, record_size: usize) -> bool {
        let current_size = self.current_size.lock().unwrap();
        *current_size + record_size as u64 > self.max_bytes
    }
}

/// Implementation of Handler trait for RotatingFileHandler.
#[async_trait]
impl Handler for RotatingFileHandler {
    /// Emit a log record to the rotating file.
    ///
    /// This method:
    /// 1. Checks the log level
    /// 2. Formats the record
    /// 3. Checks if rotation is needed
    /// 4. Writes the record to the file
    /// 5. Updates the current size
    ///
    /// # Arguments
    ///
    /// * `record` - The log record to emit
    async fn emit(&self, record: &LogRecord) {
        // Check if we should log this record based on level
        let level = self.level.lock().unwrap();
        if record.levelno < *level as i32 {
            return;
        }
        drop(level);

        // Format the record
        let output = if let Some(ref formatter) = self.formatter {
            formatter.format(record)
        } else {
            // Default format if no formatter is set
            format!(
                "[{}] [Thread-{} {}] {} {} - {}\n",
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

        let output_bytes = output.as_bytes();

        // Check if we need to rotate
        if self.should_rollover(output_bytes.len()) {
            if let Err(e) = self.do_rollover() {
                eprintln!("Error rotating log file: {}", e);
                return;
            }
        }

        // Ensure we have a writer
        if let Err(e) = self.ensure_writer() {
            eprintln!("Error opening log file: {}", e);
            return;
        }

        // Write the record
        {
            let mut writer = self.writer.lock().unwrap();
            let mut current_size = self.current_size.lock().unwrap();

            if let Some(ref mut w) = writer.as_mut() {
                if w.write_all(output_bytes).is_ok() {
                    let _ = w.flush();
                    *current_size += output_bytes.len() as u64;
                }
            }
        }
    }

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        self.formatter = Some(formatter);
    }

    fn add_filter(&mut self, filter: Arc<dyn Filter + Send + Sync>) {
        self.filters.push(filter);
    }
}
