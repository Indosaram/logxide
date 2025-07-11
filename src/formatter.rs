//! # Log Formatters
//!
//! This module provides formatter implementations for converting log records
//! into formatted string output. Formatters control the presentation of log
//! messages in handlers.
//!
//! ## Formatter Types
//!
//! - **DefaultFormatter**: Simple formatter with basic log information
//! - **PythonFormatter**: Python-compatible formatter supporting format strings
//!
//! ## Python Compatibility
//!
//! The PythonFormatter supports Python logging format strings including:
//! - Field substitution: `%(levelname)s`, `%(message)s`, etc.
//! - Padding and alignment: `%(levelname)-8s`, `%(name)15s`
//! - Date/time formatting with custom date formats
//! - Numeric formatting: `%(msecs)03d`
//!
//! ## Performance
//!
//! Formatters use regex for complex pattern matching and replacement,
//! providing both flexibility and reasonable performance for log formatting.

use chrono::TimeZone;

/// Trait for converting log records to formatted strings.
///
/// Formatters are responsible for converting LogRecord structs into
/// human-readable string representations. They must be thread-safe
/// as they may be used concurrently across multiple threads.
///
/// # Design Principles
///
/// - **Thread Safety**: All formatters must implement Send + Sync
/// - **Performance**: Formatting should be efficient as it's called for every log record
/// - **Flexibility**: Support for different output formats and customization
pub trait Formatter: Send + Sync {
    /// Format a log record into a string.
    ///
    /// # Arguments
    ///
    /// * `record` - The log record to format, as a reference to a LogRecord struct.
    ///
    /// # Returns
    ///
    /// A formatted string representation of the log record.
    fn format(&self, record: &crate::core::LogRecord) -> String;
}

/// Simple default formatter with basic log information.
///
/// Provides a minimal, readable format showing log level, logger name,
/// and message. This formatter is lightweight and suitable for development
/// or simple logging scenarios.
///
/// # Output Format
///
/// `[LEVELNAME] logger_name: message`
///
/// # Examples
///
/// ```text
/// // Output: [INFO] myapp.database: Connected to database
/// // Output: [ERROR] myapp.auth: Failed login attempt
/// ```
pub struct DefaultFormatter;

/// Implementation of Formatter trait for DefaultFormatter.
///
/// Provides simple bracketed format with level, name, and message.
impl Formatter for DefaultFormatter {
    /// Format a log record using the default format.
    ///
    /// # Arguments
    ///
    /// * `record` - The log record to format
    ///
    /// # Returns
    ///
    /// Formatted string in the format: `[LEVELNAME] logger_name: message`
    fn format(&self, record: &crate::core::LogRecord) -> String {
        // Simple format: "[LEVELNAME] logger_name: msg"
        format!("[{}] {}: {}", record.levelname, record.name, record.msg)
    }
}

/// Python-compatible formatter supporting Python logging format strings.
///
/// This formatter provides full compatibility with Python's logging module
/// format strings, including field substitution, padding, alignment, and
/// custom date formatting.
///
/// # Supported Format Specifiers
///
/// - `%(name)s` - Logger name
/// - `%(levelname)s` - Log level name (INFO, ERROR, etc.)
/// - `%(levelno)d` - Log level number (20, 40, etc.)
/// - `%(message)s` - Log message
/// - `%(asctime)s` - Formatted timestamp
/// - `%(thread)d` - Thread ID
/// - `%(threadName)s` - Thread name
/// - `%(process)d` - Process ID
/// - `%(pathname)s`, `%(filename)s`, `%(module)s` - Source information
/// - `%(lineno)d`, `%(funcName)s` - Source location
/// - `%(created)f`, `%(msecs)d` - Timing information
///
/// # Padding and Alignment
///
/// - `%(levelname)-8s` - Left-aligned with 8-character width
/// - `%(name)15s` - Right-aligned with 15-character width
/// - `%(msecs)03d` - Zero-padded 3-digit number
///
/// # Examples
///
/// ```text
/// // Format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
/// // Output: "2023-01-01 12:00:00 - myapp - INFO - Application started"
/// ```
pub struct PythonFormatter {
    /// Python-style format string with %(field)s placeholders
    pub format_string: String,
    /// Optional custom date format (strftime format)
    pub date_format: Option<String>,
}

impl PythonFormatter {
    /// Create a new PythonFormatter with the specified format string.
    ///
    /// Uses default date format ("%Y-%m-%d %H:%M:%S") for %(asctime)s.
    ///
    /// # Arguments
    ///
    /// * `format_string` - Python-style format string with %(field)s placeholders
    ///
    /// # Examples
    ///
    /// ```
    /// use logxide::formatter::PythonFormatter;
    /// let formatter = PythonFormatter::new(
    ///     "%(levelname)s - %(name)s - %(message)s".to_string()
    /// );
    /// ```
    pub fn new(format_string: String) -> Self {
        Self {
            format_string,
            date_format: None,
        }
    }

    /// Create a new PythonFormatter with custom date formatting.
    ///
    /// Allows specification of a custom strftime format for %(asctime)s placeholders.
    ///
    /// # Arguments
    ///
    /// * `format_string` - Python-style format string with %(field)s placeholders
    /// * `date_format` - strftime format string for date/time formatting
    ///
    /// # Examples
    ///
    /// ```
    /// use logxide::formatter::PythonFormatter;
    /// let formatter = PythonFormatter::with_date_format(
    ///     "%(asctime)s %(message)s".to_string(),
    ///     "%H:%M:%S".to_string()  // Time only
    /// );
    /// ```
    pub fn with_date_format(format_string: String, date_format: String) -> Self {
        Self {
            format_string,
            date_format: Some(date_format),
        }
    }
}

/// Implementation of Formatter trait for PythonFormatter.
///
/// Provides comprehensive Python logging format string support with regex-based
/// pattern matching for advanced formatting features like padding and alignment.
impl Formatter for PythonFormatter {
    /// Format a log record using Python-style format strings.
    ///
    /// Processes the format string to replace all %(field)s placeholders with
    /// corresponding values from the log record. Supports advanced features like
    /// padding, alignment, and custom date formatting.
    ///
    /// # Arguments
    ///
    /// * `record` - The log record to format
    ///
    /// # Returns
    ///
    /// Formatted string with all placeholders replaced
    ///
    /// # Performance
    ///
    /// Uses compiled regex patterns for efficient field replacement with
    /// padding support. Basic field replacements use simple string replacement.
    fn format(&self, record: &crate::core::LogRecord) -> String {
        let mut result = self.format_string.clone();

        // Format timestamp
        let datetime = chrono::Local
            .timestamp_opt(record.created as i64, (record.msecs * 1_000_000.0) as u32)
            .single()
            .unwrap_or_else(chrono::Local::now);

        let asctime = if let Some(ref date_fmt) = self.date_format {
            datetime.format(date_fmt).to_string()
        } else {
            datetime.format("%Y-%m-%d %H:%M:%S").to_string()
        };

        // Replace Python logging format specifiers with regex for padding support
        use regex::Regex;

        // Handle %(levelname)s with optional padding like %(levelname)-8s
        let levelname_re = Regex::new(r"%\(levelname\)(-?)(\d*)s").unwrap();
        result = levelname_re
            .replace_all(&result, |caps: &regex::Captures| {
                let left_align = caps.get(1).map_or("", |m| m.as_str()) == "-";
                let width: usize = caps.get(2).map_or("", |m| m.as_str()).parse().unwrap_or(0);

                if width > 0 {
                    if left_align {
                        format!("{:<width$}", record.levelname, width = width)
                    } else {
                        format!("{:>width$}", record.levelname, width = width)
                    }
                } else {
                    record.levelname.to_string()
                }
            })
            .to_string();

        // Handle %(threadName)s with optional padding like %(threadName)-10s
        let threadname_re = Regex::new(r"%\(threadName\)(-?)(\d*)s").unwrap();
        result = threadname_re
            .replace_all(&result, |caps: &regex::Captures| {
                let left_align = caps.get(1).map_or("", |m| m.as_str()) == "-";
                let width: usize = caps.get(2).map_or("", |m| m.as_str()).parse().unwrap_or(0);

                if width > 0 {
                    if left_align {
                        format!("{:<width$}", record.thread_name, width = width)
                    } else {
                        format!("{:>width$}", record.thread_name, width = width)
                    }
                } else {
                    record.thread_name.to_string()
                }
            })
            .to_string();

        // Handle %(name)s with optional padding like %(name)-15s
        let name_re = Regex::new(r"%\(name\)(-?)(\d*)s").unwrap();
        result = name_re
            .replace_all(&result, |caps: &regex::Captures| {
                let left_align = caps.get(1).map_or("", |m| m.as_str()) == "-";
                let width: usize = caps.get(2).map_or("", |m| m.as_str()).parse().unwrap_or(0);

                if width > 0 {
                    if left_align {
                        format!("{:<width$}", record.name, width = width)
                    } else {
                        format!("{:>width$}", record.name, width = width)
                    }
                } else {
                    record.name.to_string()
                }
            })
            .to_string();

        // Handle %(msecs)03d format with padding
        let msecs_re = Regex::new(r"%\(msecs\)0?(\d*)d").unwrap();
        result = msecs_re
            .replace_all(&result, |caps: &regex::Captures| {
                let width: usize = caps.get(1).map_or("", |m| m.as_str()).parse().unwrap_or(0);
                let msecs_val = record.msecs as i32;

                if width > 0 {
                    format!("{:0width$}", msecs_val, width = width)
                } else {
                    msecs_val.to_string()
                }
            })
            .to_string();

        // Handle other format specifiers (basic replacements)
        // Note: %(name)s, %(levelname)s, %(threadName)s handled above with padding support
        result = result.replace("%(levelno)d", &record.levelno.to_string());
        result = result.replace("%(pathname)s", &record.pathname);
        result = result.replace("%(filename)s", &record.filename);
        result = result.replace("%(module)s", &record.module);
        result = result.replace("%(lineno)d", &record.lineno.to_string());
        result = result.replace("%(funcName)s", &record.func_name);
        result = result.replace("%(created)f", &record.created.to_string());
        result = result.replace("%(relativeCreated)f", &record.relative_created.to_string());
        result = result.replace("%(thread)d", &record.thread.to_string());
        result = result.replace("%(processName)s", &record.process_name);
        result = result.replace("%(process)d", &record.process.to_string());
        result = result.replace("%(message)s", &record.msg);
        result = result.replace("%(asctime)s", &asctime);

        result
    }
}
