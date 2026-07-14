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
use std::cell::RefCell;
use std::fmt::Write;

thread_local! {
    /// Re-used scratch buffer for format() — keeps capacity across calls so
    /// each format call only pays a single bounded `String::clone` instead of
    /// growing a fresh allocation from zero. Cleared on entry, cloned on exit.
    static FMT_SCRATCH: RefCell<String> = const { RefCell::new(String::new()) };

    /// Per-thread cache of the default-format asctime keyed on the truncated epoch
    /// second. The default "%Y-%m-%d %H:%M:%S" has no sub-second field, so its output
    /// is constant within one second — reused here to skip repeated chrono formatting.
    /// Only used for the default format; custom datefmt (which may carry %f) is never cached.
    static ASCTIME_SECOND_CACHE: RefCell<(i64, String)> =
        const { RefCell::new((i64::MIN, String::new())) };
}

pub trait Formatter: Send + Sync {
    fn format(&self, record: &crate::core::LogRecord) -> String;
}

/// Sentinel formatter used as the default in handlers so the formatter slot can be
/// stored in an `ArcSwap<dyn Formatter>` without an `Option` wrapper. Returning the
/// raw record message keeps `handler.emit()` lock-free on the read path while
/// matching the previous "no formatter set" behaviour exactly.
pub struct NoOpFormatter;

impl Formatter for NoOpFormatter {
    fn format(&self, record: &crate::core::LogRecord) -> String {
        record.get_message()
    }
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

/// A single parsed element of a format string. Built once at formatter construction so
/// `format()` walks the plan instead of re-parsing the format string per record.
enum Token {
    Literal(String),
    Field {
        name: String,
        left_align: bool,
        zero_pad: bool,
        width: usize,
    },
}

/// Parse a Python-style format string into a token plan. This mirrors the exact scanning
/// rules the per-record formatter previously used: `%(name)` fields with optional `-`
/// (left align), `0` (zero pad) and width digits, an unconditionally-consumed trailing
/// conversion char (`s`/`d`/`f`/…), and the fallbacks for a bare `%`, a `%(` with no
/// closing `)`, and `%(name)` with no trailing conversion char.
fn parse_plan(format_str: &str) -> Vec<Token> {
    let mut plan: Vec<Token> = Vec::new();
    let mut literal = String::new();

    let mut chars = format_str.char_indices().peekable();
    while let Some(&(_, c)) = chars.peek() {
        if c == '%' {
            chars.next();
            if let Some(&(_, '(')) = chars.peek() {
                chars.next();

                let mut name_start = None;
                if let Some(&(idx, _)) = chars.peek() {
                    name_start = Some(idx);
                }

                let mut closing_idx = None;
                while let Some(&(idx, ch)) = chars.peek() {
                    if ch == ')' {
                        closing_idx = Some(idx);
                        chars.next();
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

                    // Unconditionally consume the trailing conversion char (s/d/f/…),
                    // matching the previous per-record parser exactly.
                    if let Some(&(_, _)) = chars.peek() {
                        chars.next();
                    }

                    if !literal.is_empty() {
                        plan.push(Token::Literal(std::mem::take(&mut literal)));
                    }
                    plan.push(Token::Field {
                        name: field_name.to_string(),
                        left_align,
                        zero_pad,
                        width,
                    });
                } else {
                    // `%(` with no closing `)`: emit only `%` (the scanned chars are dropped,
                    // exactly as the original parser did).
                    literal.push('%');
                }
            } else {
                literal.push('%');
            }
        } else {
            literal.push(c);
            chars.next();
        }
    }

    if !literal.is_empty() {
        plan.push(Token::Literal(literal));
    }
    plan
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
    /// Format string parsed once into a token plan (see `parse_plan`).
    plan: Vec<Token>,
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
        let plan = parse_plan(&format_string);
        Self {
            format_string,
            date_format: None,
            plan,
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
        let plan = parse_plan(&format_string);
        Self {
            format_string,
            date_format: Some(date_format),
            plan,
        }
    }
}

/// Implementation of Formatter trait for PythonFormatter.
///
/// Provides comprehensive Python logging format string support with regex-based
/// pattern matching for advanced formatting features like padding and alignment.
impl Formatter for PythonFormatter {
    fn format(&self, record: &crate::core::LogRecord) -> String {
        FMT_SCRATCH.with(|cell| {
            // Reentrancy guard: a record's `__str__` may recursively trigger a
            // log call on the same thread while we still hold the scratch
            // buffer. Fall back to a fresh allocation rather than panicking on
            // RefCell::borrow_mut().
            if let Ok(mut result) = cell.try_borrow_mut() {
                result.clear();
                self.format_into(record, &mut result);
                result.clone()
            } else {
                let mut result = String::with_capacity(self.format_string.len() + 128);
                self.format_into(record, &mut result);
                result
            }
        })
    }
}

impl PythonFormatter {
    fn format_into(&self, record: &crate::core::LogRecord, result: &mut String) {
        if result.capacity() < self.format_string.len() + 128 {
            result.reserve(self.format_string.len() + 128 - result.capacity());
        }

        let date_format = self.date_format.as_deref();
        // Per-call cache: dedupes repeated %(asctime)s within one format string. Not shared
        // across calls (a shared cache would reintroduce cross-thread contention on the §4
        // detached path, and a custom datefmt could carry sub-second fields).
        let mut asctime_cache: Option<String> = None;

        for token in &self.plan {
            let (name, left_align, zero_pad, width) = match token {
                Token::Literal(s) => {
                    result.push_str(s);
                    continue;
                }
                Token::Field {
                    name,
                    left_align,
                    zero_pad,
                    width,
                } => (name.as_str(), *left_align, *zero_pad, *width),
            };

            let mut int_buf = itoa::Buffer::new();
            let owned: String;

            let val_str: &str = match name {
                "ansi_level_color" => ansi_colors::get_level_color(&record.levelname),
                "ansi_reset_color" => ansi_colors::RESET,
                "levelname" => &record.levelname,
                "threadName" => &record.thread_name,
                "name" => &record.name,
                "msecs" => int_buf.format(record.msecs as i32),
                "levelno" => int_buf.format(record.levelno),
                "pathname" => &record.pathname,
                "filename" => &record.filename,
                "module" => &record.module,
                "lineno" => int_buf.format(record.lineno),
                "funcName" => &record.func_name,
                "thread" => int_buf.format(record.thread),
                "processName" => &record.process_name,
                "process" => int_buf.format(record.process),
                "message" => {
                    owned = record.get_message();
                    &owned
                }
                "created" => {
                    owned = record.created.to_string();
                    &owned
                }
                "relativeCreated" => {
                    owned = record.relative_created.to_string();
                    &owned
                }
                "asctime" => {
                    let s = asctime_cache.get_or_insert_with(|| {
                        if let Some(date_fmt) = date_format {
                            let datetime = chrono::Local
                                .timestamp_opt(
                                    record.created as i64,
                                    (record.msecs * 1_000_000.0) as u32,
                                )
                                .single()
                                .unwrap_or_else(chrono::Local::now);
                            datetime.format(date_fmt).to_string()
                        } else {
                            let sec = record.created as i64;
                            ASCTIME_SECOND_CACHE.with(|cell| {
                                let mut cached = cell.borrow_mut();
                                if cached.0 != sec {
                                    let datetime = chrono::Local
                                        .timestamp_opt(sec, 0)
                                        .single()
                                        .unwrap_or_else(chrono::Local::now);
                                    cached.1 = datetime.format("%Y-%m-%d %H:%M:%S").to_string();
                                    cached.0 = sec;
                                }
                                cached.1.clone()
                            })
                        }
                    });
                    s.as_str()
                }
                other => {
                    owned = if let Some(ref extra_fields) = record.extra {
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
                    };
                    &owned
                }
            };

            if width == 0 {
                result.push_str(val_str);
            } else if left_align {
                let _ = write!(result, "{val_str:<width$}");
            } else if zero_pad {
                let _ = write!(result, "{val_str:0>width$}");
            } else {
                let _ = write!(result, "{val_str:>width$}");
            }
        }

        if let Some(ref exc_text) = record.exc_text {
            result.push('\n');
            result.push_str(exc_text);
        }
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
    /// Pre-built inner formatter (with its parsed plan) reused across format() calls.
    inner: PythonFormatter,
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
            inner: PythonFormatter::new(format_string.clone()),
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
            inner: PythonFormatter::with_date_format(format_string.clone(), date_format.clone()),
            format_string,
            date_format: Some(date_format),
        }
    }
}

impl Formatter for ColorFormatter {
    /// Format a log record with ANSI color support.
    ///
    /// Delegates to the pre-built inner PythonFormatter, whose token plan handles the
    /// %(ansi_level_color)s / %(ansi_reset_color)s fields alongside the standard ones.
    fn format(&self, record: &crate::core::LogRecord) -> String {
        self.inner.format(record)
    }
}
