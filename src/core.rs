//! # Core Logging Components
//!
//! This module contains the fundamental data structures and logic for the LogXide logging system.
//! It provides Rust implementations of Python logging concepts including loggers, log records,
//! and a hierarchical logger management system.
//!
//! ## Key Components
//!
//! - **LogLevel**: Enumeration of logging levels matching Python's logging module
//! - **LogRecord**: Complete log record structure with all Python logging fields
//! - **Logger**: Individual logger instances supporting hierarchy and filtering
//! - **LoggerManager**: Global registry managing logger hierarchy and creation
//!
//! ## Logger Hierarchy
//!
//! Loggers follow Python's hierarchical naming convention using dots as separators.
//! For example:
//! - "myapp" (parent)
//! - "myapp.database" (child of myapp)
//! - "myapp.database.connection" (child of myapp.database)
//!
//! Child loggers inherit configuration from their parents unless explicitly overridden.

#![allow(dead_code)]

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::thread;

use pyo3::prelude::*;

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
    /// Convert a numeric log level to LogLevel enum.
    ///
    /// Maps Python logging numeric levels to the corresponding LogLevel variant.
    /// Unknown levels default to NotSet.
    ///
    /// # Arguments
    ///
    /// * `level` - Numeric log level (10=Debug, 20=Info, 30=Warning, 40=Error, 50=Critical)
    ///
    /// # Examples
    ///
    /// ```
    /// use logxide::core::LogLevel;
    /// assert_eq!(LogLevel::from_usize(20), LogLevel::Info);
    /// assert_eq!(LogLevel::from_usize(999), LogLevel::NotSet);
    /// ```
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

/// Complete log record structure for compatibility with Python logging.
///
/// This structure contains all fields present in Python's LogRecord class,
/// ensuring full compatibility when interfacing with Python logging handlers
/// and formatters.
///
/// # Field Documentation
///
/// Most fields mirror Python's logging.LogRecord attributes exactly.
#[pyclass]
#[derive(Debug, Clone)]
pub struct LogRecord {
    /// Logger name that generated this record
    #[pyo3(get, set)]
    pub name: String,
    /// Numeric log level (10, 20, 30, 40, 50)
    #[pyo3(get, set)]
    pub levelno: i32,
    /// String representation of log level ("DEBUG", "INFO", etc.)
    #[pyo3(get, set)]
    pub levelname: String,
    /// Full pathname of source file (if available)
    #[pyo3(get, set)]
    pub pathname: String,
    /// Filename portion of pathname
    #[pyo3(get, set)]
    pub filename: String,
    /// Module name (if available)
    #[pyo3(get, set)]
    pub module: String,
    /// Source line number (if available)
    #[pyo3(get, set)]
    pub lineno: u32,
    /// Function name (if available)
    #[pyo3(get, set)]
    pub func_name: String,
    /// Time when LogRecord was created (seconds since epoch)
    #[pyo3(get, set)]
    pub created: f64,
    /// Millisecond portion of creation time
    #[pyo3(get, set)]
    pub msecs: f64,
    /// Time in milliseconds since module load
    #[pyo3(get, set)]
    pub relative_created: f64,
    /// Thread ID number
    #[pyo3(get, set)]
    pub thread: u64,
    /// Thread name
    #[pyo3(get, set)]
    pub thread_name: String,
    /// Process name
    #[pyo3(get, set)]
    pub process_name: String,
    /// Process ID
    #[pyo3(get, set)]
    pub process: u32,
    /// The logged message
    #[pyo3(get, set)]
    pub msg: String,
    /// Arguments passed to the logging call (for % formatting) - simplified to string
    #[pyo3(get, set)]
    pub args: Option<String>,
    /// Exception information (simplified to string)
    #[pyo3(get, set)]
    pub exc_info: Option<String>,
    /// Exception text (if exc_info was processed)
    #[pyo3(get, set)]
    pub exc_text: Option<String>,
    /// Stack information (if requested)
    #[pyo3(get, set)]
    pub stack_info: Option<String>,
    /// Async task name (if in asyncio context)
    #[pyo3(get, set)]
    pub task_name: Option<String>,
}

#[pymethods]
impl LogRecord {
    #[new]
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
            name: name.into(),
            levelno,
            levelname: "".into(), // Will be set by Python
            pathname: pathname.into(),
            filename: "".into(), // Will be set by Python
            module: "".into(),   // Will be set by Python
            lineno,
            func_name: func_name.into(),
            created: 0.0,            // Will be set by Python
            msecs: 0.0,              // Will be set by Python
            relative_created: 0.0,   // Will be set by Python
            thread: 0,               // Will be set by Python
            thread_name: "".into(),  // Will be set by Python
            process_name: "".into(), // Will be set by Python
            process: 0,              // Will be set by Python
            msg: msg.into(),
            args,
            exc_info,
            exc_text: None, // Will be set by Python
            stack_info,
            task_name: None, // Will be set by Python
        }
    }
}

///
/// Loggers form a hierarchy based on their names using dot notation.
/// Each logger can have its own level, handlers, and filters, but will
/// inherit from parent loggers when not explicitly configured.
///
/// # Thread Safety
///
/// Logger instances are designed to be used from multiple threads safely
/// when wrapped in `Arc<Mutex<Logger>>`.
pub struct Logger {
    /// Logger name (e.g., "myapp.database.connection")
    pub name: String,
    /// Minimum log level for this logger (NotSet inherits from parent)
    pub level: LogLevel,
    /// List of handlers to process log records
    pub handlers: Vec<Arc<dyn crate::handler::Handler + Send + Sync>>,
    /// List of filters to apply to log records
    pub filters: Vec<Arc<dyn crate::filter::Filter + Send + Sync>>,
    /// Parent logger in the hierarchy (None for root)
    pub parent: Option<Arc<Mutex<Logger>>>,
    /// Whether to propagate records to parent loggers
    pub propagate: bool,
}

/// Create a complete LogRecord with current thread and timing information.
///
/// This function populates all the standard fields of a LogRecord using
/// current system information like thread ID, process ID, and timestamps.
/// It's the primary way to create LogRecord instances in the logging system.
///
/// # Arguments
///
/// * `name` - Logger name that generated this record
/// * `level` - Log level of the message
/// * `msg` - The log message content
///
/// # Returns
///
/// A complete LogRecord ready for processing by handlers
///
/// # Examples
///
/// ```
/// use logxide::core::{create_log_record, LogLevel};
/// let record = create_log_record("myapp".to_string(), LogLevel::Info, "Hello".to_string());
/// assert_eq!(record.name, "myapp");
/// assert_eq!(record.levelno, 20);
/// ```
pub fn create_log_record(name: String, level: LogLevel, msg: String) -> LogRecord {
    use crate::string_cache::{get_common_message, get_level_name, get_logger_name};

    let now = chrono::Local::now();
    let created = now.timestamp() as f64 + now.timestamp_subsec_nanos() as f64 / 1_000_000_000.0;
    let msecs = (now.timestamp_subsec_millis() % 1000) as f64;

    // Get thread info
    let current_thread = thread::current();
    let thread_id = format!("{:?}", current_thread.id());

    // Use custom thread name if available, otherwise use native thread name
    let thread_name = crate::THREAD_NAME
        .with(|custom_name| custom_name.borrow().clone())
        .unwrap_or_else(|| current_thread.name().unwrap_or("unnamed").to_string());

    // Extract numeric thread ID (this is platform-specific)
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
        thread_name: thread_name,
        process_name: "".to_string(),
        process: std::process::id(),
        msg: get_common_message(&msg).to_string(),
        args: None,
        exc_info: None,
        exc_text: None,
        stack_info: None,
        task_name: None,
    }
}

impl Logger {
    /// Create a new logger with the given name.
    ///
    /// The logger is initialized with default settings:
    /// - Level: NotSet (inherits from parent)
    /// - No handlers or filters
    /// - Propagation enabled
    /// - No parent (set by LoggerManager when added to hierarchy)
    ///
    /// # Arguments
    ///
    /// * `name` - The logger name
    ///
    /// # Examples
    ///
    /// ```
    /// use logxide::core::Logger;
    /// let logger = Logger::new("myapp.database");
    /// assert_eq!(logger.name, "myapp.database");
    /// ```
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
        use crate::string_cache::{get_common_message, get_level_name, get_logger_name};

        crate::core::LogRecord {
            name: get_logger_name(&self.name).to_string(),
            levelno: level as i32,
            levelname: get_level_name(level).to_string(),
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
            msg: get_common_message(msg).to_string(),
            args: None,
            exc_info: None,
            exc_text: None,
            stack_info: None,
            task_name: None,
        }
    }

    /// Set the minimum log level for this logger.
    ///
    /// Records below this level will be ignored by this logger.
    /// Setting to NotSet causes the logger to inherit from its parent.
    ///
    /// # Arguments
    ///
    /// * `level` - The minimum log level to accept
    pub fn set_level(&mut self, level: LogLevel) {
        self.level = level;
    }

    /// Get the effective log level for this logger.
    ///
    /// If this logger has an explicit level set, returns that level.
    /// Otherwise, traverses up the parent hierarchy to find the first
    /// logger with an explicit level. Defaults to Warning if no level
    /// is found anywhere in the hierarchy.
    ///
    /// # Returns
    ///
    /// The effective log level for filtering decisions
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

    /// Add a handler to this logger.
    ///
    /// The handler will receive all log records that pass through this logger
    /// and meet the level and filter requirements.
    ///
    /// # Arguments
    ///
    /// * `handler` - Handler to add to this logger
    pub fn add_handler(&mut self, handler: Arc<dyn crate::handler::Handler + Send + Sync>) {
        self.handlers.push(handler);
    }

    /// Remove a handler from this logger by ID.
    ///
    /// # Note
    ///
    /// This method is currently a stub. Handler removal by ID is not
    /// implemented and may be added in future versions if needed.
    ///
    /// # Arguments
    ///
    /// * `_handler_id` - ID of handler to remove (currently unused)
    pub fn remove_handler(&mut self, _handler_id: usize) {
        // Handler removal by id is not implemented; consider implementing if needed
    }

    /// Add a filter to this logger.
    ///
    /// Filters are applied to log records before they are passed to handlers.
    /// If any filter rejects a record, it will not be processed further.
    ///
    /// # Arguments
    ///
    /// * `filter` - Filter to add to this logger
    pub fn add_filter(&mut self, filter: Arc<dyn crate::filter::Filter + Send + Sync>) {
        self.filters.push(filter);
    }

    /// Remove a filter from this logger by ID.
    ///
    /// # Note
    ///
    /// This method is currently a stub. Filter removal by ID is not
    /// implemented and may be added in future versions if needed.
    ///
    /// # Arguments
    ///
    /// * `_filter_id` - ID of filter to remove (currently unused)
    pub fn remove_filter(&mut self, _filter_id: usize) {
        // Filter removal by id is not implemented; consider implementing if needed
    }

    /// Check if this logger would process a record at the given level.
    ///
    /// This is used to avoid expensive log message formatting when the
    /// message would be filtered out anyway.
    ///
    /// # Arguments
    ///
    /// * `level` - Log level to check
    ///
    /// # Returns
    ///
    /// true if a record at this level would be processed, false otherwise
    pub fn is_enabled_for(&self, level: LogLevel) -> bool {
        level >= self.get_effective_level()
    }

    /// Log a message at the specified level.
    ///
    /// This is the main logging method. It checks if the level is enabled,
    /// creates a LogRecord, and passes it to the handle method for processing.
    ///
    /// # Arguments
    ///
    /// * `level` - Log level for the message
    /// * `msg` - Message to log
    pub fn log(&self, level: LogLevel, msg: &str) {
        if self.is_enabled_for(level) {
            let record = create_log_record(self.name.clone(), level, msg.to_string());
            self.handle(record);
        }
    }

    /// Log a debug message (level 10).
    pub fn debug(&self, msg: &str) {
        self.log(LogLevel::Debug, msg);
    }

    /// Log an info message (level 20).
    pub fn info(&self, msg: &str) {
        self.log(LogLevel::Info, msg);
    }

    /// Log a warning message (level 30).
    pub fn warning(&self, msg: &str) {
        self.log(LogLevel::Warning, msg);
    }

    /// Log an error message (level 40).
    pub fn error(&self, msg: &str) {
        self.log(LogLevel::Error, msg);
    }

    /// Log a critical message (level 50).
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

/// Manages the global logger hierarchy and registry.
///
/// The LoggerManager maintains a registry of all created loggers and
/// ensures proper parent-child relationships in the logger hierarchy.
/// It follows the singleton pattern with a global instance.
///
/// # Thread Safety
///
/// LoggerManager is thread-safe and can be accessed concurrently from
/// multiple threads. The internal registry is protected by a Mutex.
pub struct LoggerManager {
    /// Registry of all created loggers by name
    pub loggers: Mutex<HashMap<String, Arc<Mutex<Logger>>>>,
    /// The root logger (parent of all top-level loggers)
    pub root: Arc<Mutex<Logger>>,
}

impl Default for LoggerManager {
    fn default() -> Self {
        Self::new()
    }
}

impl LoggerManager {
    /// Create a new LoggerManager with a root logger.
    ///
    /// The root logger serves as the ultimate parent for all loggers
    /// in the hierarchy and provides default configuration.
    pub fn new() -> Self {
        let root_logger = Arc::new(Mutex::new(Logger::new("root")));
        LoggerManager {
            loggers: Mutex::new(HashMap::new()),
            root: root_logger.clone(),
        }
    }

    /// Get or create a logger by name, maintaining hierarchy.
    ///
    /// If the logger already exists, returns the existing instance.
    /// Otherwise, creates a new logger and establishes proper parent
    /// relationships based on the name hierarchy.
    ///
    /// # Arguments
    ///
    /// * `name` - Hierarchical logger name (e.g., "myapp.database.connection")
    ///
    /// # Returns
    ///
    /// `Arc<Mutex<Logger>>` for thread-safe access to the logger
    ///
    /// # Examples
    ///
    /// ```
    /// use logxide::core::LoggerManager;
    /// let manager = LoggerManager::new();
    /// let logger = manager.get_logger("myapp.database");
    /// ```
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

    /// Get the root logger.
    ///
    /// The root logger is the ultimate parent in the hierarchy and
    /// provides default behavior for all other loggers.
    ///
    /// # Returns
    ///
    /// `Arc<Mutex<Logger>>` for the root logger
    pub fn get_root_logger(&self) -> Arc<Mutex<Logger>> {
        self.root.clone()
    }
}

// Global logger manager instance (singleton)
use once_cell::sync::Lazy;
pub static LOGGER_MANAGER: Lazy<LoggerManager> = Lazy::new(LoggerManager::new);

/// Get a logger by name from the global logger registry.
///
/// This is the main public API for obtaining logger instances.
/// It uses the global LoggerManager singleton.
///
/// # Arguments
///
/// * `name` - Logger name (hierarchical using dots)
///
/// # Returns
///
/// Thread-safe logger instance
///
/// # Examples
///
/// ```
/// use logxide::core::get_logger;
/// let logger = get_logger("myapp.database");
/// ```
pub fn get_logger(name: &str) -> Arc<Mutex<Logger>> {
    LOGGER_MANAGER.get_logger(name)
}

/// Get the root logger from the global logger registry.
///
/// The root logger is the top-level logger in the hierarchy.
///
/// # Returns
///
/// Thread-safe root logger instance
pub fn get_root_logger() -> Arc<Mutex<Logger>> {
    LOGGER_MANAGER.get_root_logger()
}
