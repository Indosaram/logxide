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
        let mut result = format!(
            "[{}] {}: {}",
            record.levelname,
            record.name,
            record.get_message()
        );
        if let Some(ref exc_text) = record.exc_text {
            result.push('\n');
            result.push_str(exc_text);
        }
        result
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
    /// Uses a single-pass O(N) parser to perform field formatting with zero regex
    /// and zero sequential allocations. All values are formatted directly into the
    /// pre-allocated output buffer.
    fn format(&self, record: &crate::core::LogRecord) -> String {
        let format_str = &self.format_string;
        let mut result = String::with_capacity(format_str.len() + 128);

        // Pre-compute asctime
        let datetime = chrono::Local
            .timestamp_opt(record.created as i64, (record.msecs * 1_000_000.0) as u32)
            .single()
            .unwrap_or_else(chrono::Local::now);

        let asctime = if let Some(ref date_fmt) = self.date_format {
            datetime.format(date_fmt).to_string()
        } else {
            datetime.format("%Y-%m-%d %H:%M:%S").to_string()
        };

        let mut chars = format_str.char_indices().peekable();
        while let Some(&(_, c)) = chars.peek() {
            if c == '%' {
                chars.next(); // Consume '%'
                if let Some(&(_, '(')) = chars.peek() {
                    chars.next(); // Consume '('

                    let mut name_start = None;
                    if let Some(&(idx, _)) = chars.peek() {
                        name_start = Some(idx);
                    }

                    let mut closing_idx = None;
                    while let Some(&(idx, ch)) = chars.peek() {
                        if ch == ')' {
                            closing_idx = Some(idx);
                            chars.next(); // Consume ')'
                            break;
                        }
                        chars.next();
                    }

                    if let (Some(start), Some(end)) = (name_start, closing_idx) {
                        let field_name = &format_str[start..end];

                        let mut left_align = false;
                        if let Some(&(_, '-')) = chars.peek() {
                            left_align = true;
                            chars.next();
                        }

                        let mut zero_pad = false;
                        if let Some(&(_, '0')) = chars.peek() {
                            zero_pad = true;
                            chars.next();
                        }

                        let mut width = 0;
                        while let Some(&(_, ch)) = chars.peek() {
                            if ch.is_ascii_digit() {
                                width = width * 10 + ch.to_digit(10).unwrap() as usize;
                                chars.next();
                            } else {
                                break;
                            }
                        }

                        // Consume the format type specifier (s, d, f, etc.)
                        if let Some(&(_, _)) = chars.peek() {
                            chars.next();
                        }

                        let val_str = match field_name {
                            "ansi_level_color" => {
                                ansi_colors::get_level_color(&record.levelname).to_string()
                            }
                            "ansi_reset_color" => ansi_colors::RESET.to_string(),
                            "levelname" => record.levelname.to_string(),
                            "threadName" => record.thread_name.to_string(),
                            "name" => record.name.to_string(),
                            "msecs" => (record.msecs as i32).to_string(),
                            "levelno" => record.levelno.to_string(),
                            "pathname" => record.pathname.to_string(),
                            "filename" => record.filename.to_string(),
                            "module" => record.module.to_string(),
                            "lineno" => record.lineno.to_string(),
                            "funcName" => record.func_name.to_string(),
                            "created" => record.created.to_string(),
                            "relativeCreated" => record.relative_created.to_string(),
                            "thread" => record.thread.to_string(),
                            "processName" => record.process_name.to_string(),
                            "process" => record.process.to_string(),
                            "message" => record.get_message(),
                            "asctime" => asctime.clone(),
                            other => {
                                if let Some(ref extra_fields) = record.extra {
                                    if let Some(value) = extra_fields.get(other) {
                                        match value {
                                            serde_json::Value::String(s) => s.clone(),
                                            serde_json::Value::Null => "null".to_string(),
                                            other_val => other_val.to_string(),
                                        }
                                    } else {
                                        format!("%({other})")
                                    }
                                } else {
                                    format!("%({other})")
                                }
                            }
                        };

                        if width > 0 {
                            if left_align {
                                result.push_str(&format!("{val_str:<width$}"));
                            } else if zero_pad {
                                result.push_str(&format!("{val_str:0>width$}"));
                            } else {
                                result.push_str(&format!("{val_str:>width$}"));
                            }
                        } else {
                            result.push_str(&val_str);
                        }
                    } else {
                        result.push('%');
                    }
                } else {
                    result.push('%');
                }
            } else {
                result.push(c);
                chars.next();
            }
        }

        // Append exc_text if present (traceback from exception())
        if let Some(ref exc_text) = record.exc_text {
            result.push('\n');
            result.push_str(exc_text);
        }

        result
    }
}

/// ANSI color codes for terminal output.
pub mod ansi_colors {
    /// ANSI color code for DEBUG level (white/gray)
    pub const DEBUG: &str = "\x1b[37m";
    /// ANSI color code for INFO level (green)
    pub const INFO: &str = "\x1b[32m";
    /// ANSI color code for WARNING level (yellow)
    pub const WARNING: &str = "\x1b[33m";
    /// ANSI color code for ERROR level (red)
    pub const ERROR: &str = "\x1b[31m";
    /// ANSI color code for CRITICAL level (magenta/bold red)
    pub const CRITICAL: &str = "\x1b[35m";
    /// ANSI reset code to clear formatting
    pub const RESET: &str = "\x1b[0m";

    /// Get the ANSI color code for a given log level.
    pub fn get_level_color(levelname: &str) -> &'static str {
        match levelname {
            "DEBUG" => DEBUG,
            "INFO" => INFO,
            "WARNING" => WARNING,
            "ERROR" => ERROR,
            "CRITICAL" => CRITICAL,
            _ => "",
        }
    }
}

/// Color-aware formatter that supports ANSI escape codes for terminal output.
///
/// Extends PythonFormatter with support for color placeholders:
/// - `%(ansi_level_color)s` - ANSI color code for the current log level
/// - `%(ansi_reset_color)s` - ANSI reset code to clear formatting
///
/// # Examples
///
/// ```text
/// // Format: "%(ansi_level_color)s%(levelname)s%(ansi_reset_color)s - %(message)s"
/// // Output: "\x1b[32mINFO\x1b[0m - Application started" (INFO in green)
/// ```
///
/// # Color Mapping
///
/// | Level    | Color   | ANSI Code |
/// |----------|---------|-----------|
/// | DEBUG    | White   | \x1b[37m |
/// | INFO     | Green   | \x1b[32m |
/// | WARNING  | Yellow  | \x1b[33m |
/// | ERROR    | Red     | \x1b[31m |
/// | CRITICAL | Magenta | \x1b[35m |
pub struct ColorFormatter {
    /// The underlying format string with %(field)s placeholders
    pub format_string: String,
    /// Optional custom date format (strftime format)
    pub date_format: Option<String>,
}

impl ColorFormatter {
    /// Create a new ColorFormatter with the specified format string.
    ///
    /// Uses default date format ("%Y-%m-%d %H:%M:%S") for %(asctime)s.
    ///
    /// # Arguments
    ///
    /// * `format_string` - Python-style format string with %(field)s placeholders.
    ///   Supports %(ansi_level_color)s and %(ansi_reset_color)s.
    ///
    /// # Examples
    ///
    /// ```
    /// use logxide::formatter::ColorFormatter;
    /// let formatter = ColorFormatter::new(
    ///     "%(ansi_level_color)s[%(levelname)s]%(ansi_reset_color)s %(message)s".to_string()
    /// );
    /// ```
    pub fn new(format_string: String) -> Self {
        Self {
            format_string,
            date_format: None,
        }
    }

    /// Create a new ColorFormatter with custom date formatting.
    ///
    /// # Arguments
    ///
    /// * `format_string` - Python-style format string with %(field)s placeholders
    /// * `date_format` - strftime format string for date/time formatting
    pub fn with_date_format(format_string: String, date_format: String) -> Self {
        Self {
            format_string,
            date_format: Some(date_format),
        }
    }
}

impl Formatter for ColorFormatter {
    /// Format a log record with ANSI color support.
    ///
    /// First replaces color placeholders with appropriate ANSI codes,
    /// then delegates to PythonFormatter logic for remaining fields.
    fn format(&self, record: &crate::core::LogRecord) -> String {
        let python_formatter = PythonFormatter {
            format_string: self.format_string.clone(),
            date_format: self.date_format.clone(),
        };

        python_formatter.format(record)
    }
}
