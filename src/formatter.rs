use chrono::TimeZone;

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

// Example of a basic formatter implementation
pub struct DefaultFormatter;

impl Formatter for DefaultFormatter {
    fn format(&self, record: &crate::core::LogRecord) -> String {
        // Simple format: "[LEVELNAME] logger_name: msg"
        format!("[{}] {}: {}", record.levelname, record.name, record.msg)
    }
}

/// Python-style formatter that supports format strings like Python's logging module
pub struct PythonFormatter {
    pub format_string: String,
    pub date_format: Option<String>,
}

impl PythonFormatter {
    pub fn new(format_string: String) -> Self {
        Self {
            format_string,
            date_format: None,
        }
    }

    pub fn with_date_format(format_string: String, date_format: String) -> Self {
        Self {
            format_string,
            date_format: Some(date_format),
        }
    }
}

impl Formatter for PythonFormatter {
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
                    record.levelname.clone()
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
                    record.thread_name.clone()
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
                    record.name.clone()
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
