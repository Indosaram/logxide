//! # Log Handlers
//!
//! This module provides handler implementations for processing log records.
//! Handlers are responsible for outputting log records to their final destinations
//! such as console, files, network services, or Python logging handlers.
//!
//! ## Handler Types
//!
//! - **PythonHandler**: ⚠️ DEPRECATED - No longer used for performance reasons
//! - **ConsoleHandler**: Outputs formatted log records to stdout
//! - **StreamHandler**: Outputs to stdout or stderr (recommended)
//! - **FileHandler**: Outputs to a file
//! - **NullHandler**: Discards all log records
//! - **RotatingFileHandler**: Outputs to a file with automatic rotation
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
#[cfg(feature = "python-handlers")]
use once_cell::sync::OnceCell;
use pyo3::prelude::*;

use std::fs::{File, OpenOptions};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU8, Ordering};
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

    /// Flush any buffered log records.
    ///
    /// This ensures that all buffered log records are written to their
    /// final destination. Should be called before program termination
    /// or when immediate persistence is required.
    async fn flush(&self);

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

/// ⚠️ DEPRECATED: Handler that wraps a Python callable for compatibility with Python logging.
///
/// **This handler is no longer used in LogXide for performance reasons.**
/// Python handlers create significant overhead due to:
/// - Python FFI boundary crossing
/// - GIL acquisition
/// - LogRecord serialization to Python objects
/// - Python method call overhead
///
/// LogXide now uses Rust native handlers exclusively for maximum performance.
/// This struct remains only for backward compatibility and is not registered
/// by the main lib.rs module.
///
/// # Migration
///
/// Use Rust native handlers instead:
/// - `StreamHandler` for console output
/// - `FileHandler` for file output
/// - `RotatingFileHandler` for rotating files
/// - `NullHandler` for discarding logs
///
/// # Thread Safety
///
/// Uses PyO3's GIL management to safely call Python code from Rust threads.
/// Python logging handler support (deprecated - use Rust native handlers instead)
///
/// This is disabled by default. Enable with the `python-handlers` feature flag.
#[cfg(feature = "python-handlers")]
#[deprecated(
    since = "0.1.2",
    note = "Use Rust native handlers (StreamHandler, FileHandler, etc.) for better performance"
)]
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

// Cache for Python logging.LogRecord class to avoid repeated imports
#[cfg(feature = "python-handlers")]
static LOG_RECORD_CLASS: OnceCell<PyObject> = OnceCell::new();

#[cfg(feature = "python-handlers")]
#[allow(deprecated)]
impl PythonHandler {
    /// ⚠️ DEPRECATED: Create a new PythonHandler wrapping a Python callable.
    ///
    /// **Do not use this.** Use Rust native handlers instead.
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
    #[deprecated(
        since = "0.1.2",
        note = "Use Rust native handlers (StreamHandler, FileHandler, etc.) instead"
    )]
    #[allow(dead_code)]
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

    /// ⚠️ DEPRECATED: Create a new PythonHandler with an explicit ID.
    ///
    /// **Do not use this.** Use Rust native handlers instead.
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
    #[deprecated(
        since = "0.1.2",
        note = "Use Rust native handlers (StreamHandler, FileHandler, etc.) instead"
    )]
    #[allow(dead_code)]
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

/// ⚠️ DEPRECATED: Implementation of Handler trait for PythonHandler.
///
/// **This is no longer used in LogXide.** Use Rust native handlers instead.
///
/// Provides Python handler compatibility with GIL management.
#[cfg(feature = "python-handlers")]
#[async_trait]
#[allow(deprecated)]
impl Handler for PythonHandler {
    /// ⚠️ DEPRECATED: Emit a log record by calling the wrapped Python callable.
    ///
    /// **Do not use this.** This method crosses the Python FFI boundary and
    /// acquires the GIL, causing significant performance overhead.
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
            let handler_obj = self.py_callable.bind(py);

            // Get cached LogRecord class or initialize it
            let log_record_class = LOG_RECORD_CLASS.get_or_init(|| {
                Python::with_gil(|py| {
                    let logging_module = py.import("logging").expect("Failed to import logging");
                    let log_record_class = logging_module
                        .getattr("LogRecord")
                        .expect("Failed to get LogRecord class");
                    log_record_class.into()
                })
            });

            let log_record_class = log_record_class.bind(py);

            // Create a proper LogRecord object
            // LogRecord.__init__(name, level, pathname, lineno, msg, args, exc_info, func=None, sinfo=None)
            let py_record = match log_record_class.call1((
                &record.name,     // name
                record.levelno,   // level
                &record.pathname, // pathname
                record.lineno,    // lineno
                &record.msg,      // msg
                py.None(),        // args (empty tuple)
                py.None(),        // exc_info
            )) {
                Ok(rec) => rec,
                Err(_) => return,
            };

            // Set additional fields on the LogRecord object
            let _ = py_record.setattr("created", record.created);
            let _ = py_record.setattr("msecs", record.msecs);
            let _ = py_record.setattr("threadName", &record.thread_name);
            let _ = py_record.setattr("thread", record.thread);
            let _ = py_record.setattr("process", record.process);
            let _ = py_record.setattr("module", &record.module);
            let _ = py_record.setattr("filename", &record.filename);
            let _ = py_record.setattr("funcName", &record.func_name);

            // Add extra fields to the LogRecord object (as strings due to Rust storage)
            if let Some(ref extra_fields) = record.extra {
                for (key, value) in extra_fields {
                    let _ = py_record.setattr(key.as_str(), value.as_str());
                }
            }

            // Call handle() method with proper LogRecord object
            let _ = handler_obj.call_method1("handle", (py_record,));
        });
    }

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        self.formatter = Some(formatter);
    }

    fn add_filter(&mut self, filter: Arc<dyn Filter + Send + Sync>) {
        self.filters.push(filter);
    }

    async fn flush(&self) {
        // PythonHandler doesn't buffer, no-op
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
    /// Minimum log level to output (using AtomicU8 for lock-free access)
    pub level: AtomicU8,
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
            level: AtomicU8::new(LogLevel::Warning as u8),
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
            level: AtomicU8::new(level as u8),
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
            level: AtomicU8::new(level as u8),
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
        // Check if we should log this record based on level (lock-free)
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
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
        println!("{output}");
        io::stdout().flush().unwrap();
    }

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        self.formatter = Some(formatter);
    }

    fn add_filter(&mut self, filter: Arc<dyn Filter + Send + Sync>) {
        self.filters.push(filter);
    }

    async fn flush(&self) {
        // ConsoleHandler uses stdout which auto-flushes on newline
        // But we'll explicitly flush just to be safe
        let _ = std::io::stdout().flush();
    }
}

/// Null handler that does nothing with log records.
///
/// This handler is useful for:
/// - Disabling logging output
/// - Library code that should not produce output by default
/// - Testing scenarios
///
/// # Performance
///
/// NullHandler has minimal overhead as it performs no I/O operations.
pub struct NullHandler;

impl NullHandler {
    /// Create a new NullHandler.
    pub fn new() -> Self {
        Self
    }
}

impl Default for NullHandler {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl Handler for NullHandler {
    /// Emit does nothing for NullHandler.
    async fn emit(&self, _record: &LogRecord) {
        // Intentionally do nothing
    }

    fn set_formatter(&mut self, _formatter: Arc<dyn Formatter + Send + Sync>) {
        // NullHandler ignores formatters
    }

    fn add_filter(&mut self, _filter: Arc<dyn Filter + Send + Sync>) {
        // NullHandler ignores filters
    }

    async fn flush(&self) {
        // NullHandler discards everything, no-op
    }
}

/// Stream handler that writes formatted log records to a stream (stdout or stderr).
///
/// This is a more flexible version of ConsoleHandler that can write to any stream,
/// not just stdout. It's the Rust equivalent of Python's logging.StreamHandler.
///
/// # Output Destination
///
/// The handler can write to:
/// - `stdout` - Standard output stream
/// - `stderr` - Standard error stream (default)
///
/// # Thread Safety
///
/// Uses Mutex to ensure thread-safe access to the output stream.
pub struct StreamHandler {
    /// Target stream (stdout or stderr)
    stream: Mutex<StreamDestination>,
    /// Minimum log level to output (using AtomicU8 for lock-free access)
    level: AtomicU8,
    /// Optional formatter for customizing output format
    formatter: Option<Arc<dyn Formatter + Send + Sync>>,
    /// List of filters applied before output
    filters: Vec<Arc<dyn Filter + Send + Sync>>,
}

/// Represents the destination stream for output.
#[derive(Clone, Copy)]
pub enum StreamDestination {
    Stdout,
    Stderr,
}

impl StreamHandler {
    /// Create a new StreamHandler writing to stderr (default).
    pub fn new() -> Self {
        Self {
            stream: Mutex::new(StreamDestination::Stderr),
            level: AtomicU8::new(LogLevel::Debug as u8),
            formatter: None,
            filters: Vec::new(),
        }
    }

    /// Create a new StreamHandler writing to stdout.
    pub fn stdout() -> Self {
        Self {
            stream: Mutex::new(StreamDestination::Stdout),
            level: AtomicU8::new(LogLevel::Debug as u8),
            formatter: None,
            filters: Vec::new(),
        }
    }

    /// Create a new StreamHandler writing to stderr.
    pub fn stderr() -> Self {
        Self {
            stream: Mutex::new(StreamDestination::Stderr),
            level: AtomicU8::new(LogLevel::Debug as u8),
            formatter: None,
            filters: Vec::new(),
        }
    }

    /// Set the minimum log level.
    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
    }
}

impl Default for StreamHandler {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl Handler for StreamHandler {
    async fn emit(&self, record: &LogRecord) {
        // Check if we should log this record based on level (lock-free)
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }

        // Format the record
        let output = if let Some(ref formatter) = self.formatter {
            formatter.format(record)
        } else {
            // Default format matching Python's logging
            format!(
                "{} - {} - {} - {}",
                chrono::Local
                    .timestamp_opt(record.created as i64, (record.msecs * 1_000_000.0) as u32)
                    .single()
                    .unwrap_or_else(chrono::Local::now)
                    .format("%Y-%m-%d %H:%M:%S,%3f"),
                record.name,
                record.levelname,
                record.msg
            )
        };

        // Write to the appropriate stream
        use std::io::{self, Write};
        let stream_dest = *self.stream.lock().unwrap();
        match stream_dest {
            StreamDestination::Stdout => {
                let mut stdout = io::stdout();
                let _ = writeln!(stdout, "{}", output);
                let _ = stdout.flush();
            }
            StreamDestination::Stderr => {
                let mut stderr = io::stderr();
                let _ = writeln!(stderr, "{}", output);
                let _ = stderr.flush();
            }
        }
    }

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        self.formatter = Some(formatter);
    }

    fn add_filter(&mut self, filter: Arc<dyn Filter + Send + Sync>) {
        self.filters.push(filter);
    }

    async fn flush(&self) {
        use std::io::{self, Write};
        let stream_dest = *self.stream.lock().unwrap();
        match stream_dest {
            StreamDestination::Stdout => {
                let _ = io::stdout().flush();
            }
            StreamDestination::Stderr => {
                let _ = io::stderr().flush();
            }
        }
    }
}

/// File handler that writes formatted log records to a file.
///
/// This is a simple file handler that appends log records to a file.
/// For automatic rotation, use RotatingFileHandler instead.
///
/// # File Management
///
/// - Opens the file in append mode by default
/// - Buffers writes for better performance
/// - Flushes after each write to ensure data is persisted
///
/// # Thread Safety
///
/// Uses Mutex to ensure thread-safe access to the file writer.
pub struct FileHandler {
    /// Path to the log file
    #[allow(dead_code)]
    filename: PathBuf,
    /// File writer (protected by Mutex for thread safety)
    writer: Mutex<Option<BufWriter<File>>>,
    /// Minimum log level to output (using AtomicU8 for lock-free access)
    level: AtomicU8,
    /// Optional formatter for customizing output format
    formatter: Option<Arc<dyn Formatter + Send + Sync>>,
    /// List of filters applied before output
    filters: Vec<Arc<dyn Filter + Send + Sync>>,
}

impl FileHandler {
    /// Create a new FileHandler.
    ///
    /// # Arguments
    ///
    /// * `filename` - Path to the log file
    ///
    /// # Returns
    ///
    /// A new FileHandler instance
    pub fn new<P: AsRef<Path>>(filename: P) -> std::io::Result<Self> {
        let filename = filename.as_ref().to_path_buf();
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&filename)?;
        // Use 64KB buffer for better performance (default is 8KB)
        let writer = BufWriter::with_capacity(64 * 1024, file);

        Ok(Self {
            filename: filename.clone(),
            writer: Mutex::new(Some(writer)),
            level: AtomicU8::new(LogLevel::Debug as u8),
            formatter: None,
            filters: Vec::new(),
        })
    }

    /// Set the minimum log level.
    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
    }
}

#[async_trait]
impl Handler for FileHandler {
    async fn emit(&self, record: &LogRecord) {
        // Check if we should log this record based on level (lock-free)
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }

        // Format the record
        let output = if let Some(ref formatter) = self.formatter {
            formatter.format(record)
        } else {
            // Default format matching Python's logging
            format!(
                "{} - {} - {} - {}",
                chrono::Local
                    .timestamp_opt(record.created as i64, (record.msecs * 1_000_000.0) as u32)
                    .single()
                    .unwrap_or_else(chrono::Local::now)
                    .format("%Y-%m-%d %H:%M:%S,%3f"),
                record.name,
                record.levelname,
                record.msg
            )
        };

        // Write to file with immediate flush for reliability
        let mut writer_guard = self.writer.lock().unwrap();
        if let Some(ref mut writer) = *writer_guard {
            let _ = writeln!(writer, "{}", output);
            // Flush immediately to ensure logs are written
            let _ = writer.flush();
        }
    }

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        self.formatter = Some(formatter);
    }

    fn add_filter(&mut self, filter: Arc<dyn Filter + Send + Sync>) {
        self.filters.push(filter);
    }

    async fn flush(&self) {
        let mut writer_guard = self.writer.lock().unwrap();
        if let Some(ref mut writer) = *writer_guard {
            let _ = writer.flush();
        }
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
    /// Minimum log level to output (using AtomicU8 for lock-free access)
    pub level: AtomicU8,
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
            level: AtomicU8::new(LogLevel::Debug as u8),
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
            level: AtomicU8::new(level as u8),
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
            let size = file.metadata()?.len();
            *current_size = size;

            // Use 64KB buffer for better performance (default is 8KB)
            *writer = Some(BufWriter::with_capacity(64 * 1024, file));
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

    /// Set the minimum log level.
    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
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
        // Check if we should log this record based on level (lock-free)
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }

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
                eprintln!("Error rotating log file: {e}");
                return;
            }
        }

        // Ensure we have a writer
        if let Err(e) = self.ensure_writer() {
            eprintln!("Error opening log file: {e}");
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

    async fn flush(&self) {
        let mut writer_guard = self.writer.lock().unwrap();
        if let Some(ref mut writer) = *writer_guard {
            let _ = writer.flush();
        }
    }
}

/// Python stream handler that writes to a Python file-like object.
///
/// This handler allows writing to Python objects that have a `write()` method,
/// such as `io.StringIO`, `io.BytesIO`, or custom stream objects.
/// This is essential for testing with pytest and capturing log output.
///
/// # Thread Safety
///
/// Uses PyObject which is thread-safe across the FFI boundary.
/// The Python GIL is acquired for each write operation.
pub struct PythonStreamHandler {
    /// Python file-like object to write to
    stream: PyObject,
    /// Minimum log level to output (using AtomicU8 for lock-free access)
    level: AtomicU8,
    /// Optional formatter for customizing output format
    formatter: Option<Arc<dyn Formatter + Send + Sync>>,
    /// List of filters applied before output
    filters: Vec<Arc<dyn Filter + Send + Sync>>,
}

impl PythonStreamHandler {
    /// Create a new PythonStreamHandler.
    ///
    /// # Arguments
    ///
    /// * `stream` - Python file-like object with write() method
    ///
    /// # Returns
    ///
    /// A new PythonStreamHandler instance
    pub fn new(stream: PyObject) -> Self {
        Self {
            stream,
            level: AtomicU8::new(LogLevel::Debug as u8),
            formatter: None,
            filters: Vec::new(),
        }
    }

    pub fn set_level(&mut self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
    }
}

#[async_trait]
impl Handler for PythonStreamHandler {
    async fn emit(&self, record: &LogRecord) {
        // Check if we should log this record based on level (lock-free)
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }

        // Format the record
        let output = if let Some(ref formatter) = self.formatter {
            formatter.format(record)
        } else {
            // Default format matching Python's logging
            format!(
                "{} - {} - {} - {}",
                chrono::Local
                    .timestamp_opt(record.created as i64, (record.msecs * 1_000_000.0) as u32)
                    .single()
                    .unwrap_or_else(chrono::Local::now)
                    .format("%Y-%m-%d %H:%M:%S,%3f"),
                record.name,
                record.levelname,
                record.msg
            )
        };

        // Write to Python stream object
        // Use a blocking task to safely acquire GIL in async context
        let output_with_newline = format!("{}\n", output);

        // Clone the PyObject reference for use in the blocking task
        let stream_ref = &self.stream;

        Python::with_gil(|py| {
            let stream_bound = stream_ref.bind(py);
            // Call write() method on the Python object
            if let Ok(write_method) = stream_bound.getattr("write") {
                let _ = write_method.call1((output_with_newline,));
            }
            // Try to flush if the object has a flush() method
            if let Ok(flush_method) = stream_bound.getattr("flush") {
                let _ = flush_method.call0();
            }
        });
    }

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        self.formatter = Some(formatter);
    }

    fn add_filter(&mut self, filter: Arc<dyn Filter + Send + Sync>) {
        self.filters.push(filter);
    }

    async fn flush(&self) {
        Python::with_gil(|py| {
            if let Ok(flush_method) = self.stream.bind(py).getattr("flush") {
                let _ = flush_method.call0();
            }
        });
    }
}
