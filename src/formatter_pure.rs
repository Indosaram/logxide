//! Pure Rust formatter implementations for testing without PyO3

use crate::core_pure::LogRecord;

pub trait Formatter {
    fn format(&self, record: &LogRecord) -> String;
}

pub struct DefaultFormatter;

impl Formatter for DefaultFormatter {
    fn format(&self, record: &LogRecord) -> String {
        format!("[{}] {}: {}", record.levelname, record.name, record.msg)
    }
}

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

    #[allow(dead_code)]
    pub fn with_date_format(format_string: String, date_format: String) -> Self {
        Self {
            format_string,
            date_format: Some(date_format),
        }
    }
}

impl Formatter for PythonFormatter {
    fn format(&self, record: &LogRecord) -> String {
        let mut result = self.format_string.clone();

        // Format timestamp using std::time instead of chrono to avoid dependencies
        let datetime = std::time::UNIX_EPOCH + std::time::Duration::from_secs_f64(record.created);
        let asctime = if let Some(ref _date_fmt) = self.date_format {
            // For testing, just use a simple format
            format!("{:?}", datetime)
                .split('.')
                .next()
                .unwrap_or("")
                .to_string()
        } else {
            format!("{:?}", datetime)
                .split('.')
                .next()
                .unwrap_or("")
                .to_string()
        };

        // Handle basic format specifiers (simplified for testing)
        result = result.replace("%(levelname)s", &record.levelname);
        result = result.replace("%(name)s", &record.name);
        result = result.replace("%(message)s", &record.msg);
        result = result.replace("%(levelno)d", &record.levelno.to_string());
        result = result.replace("%(thread)d", &record.thread.to_string());
        result = result.replace("%(process)d", &record.process.to_string());
        result = result.replace("%(asctime)s", &asctime);
        result = result.replace("%(threadName)s", &record.thread_name);

        // Handle simple padding (basic implementation for testing)
        if result.contains("%(levelname)-8s") {
            result = result.replace("%(levelname)-8s", &format!("{:<8}", record.levelname));
        }
        if result.contains("%(name)-15s") {
            result = result.replace("%(name)-15s", &format!("{:<15}", record.name));
        }

        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core_pure::{create_log_record, LogLevel};

    #[test]
    fn test_default_formatter() {
        let formatter = DefaultFormatter;
        let record = create_log_record(
            "test.logger".to_string(),
            LogLevel::Info,
            "Test message".to_string(),
        );

        let formatted = formatter.format(&record);
        assert!(formatted.contains("[INFO]"));
        assert!(formatted.contains("test.logger"));
        assert!(formatted.contains("Test message"));

        // Should match pattern: [LEVELNAME] logger_name: msg
        assert_eq!(formatted, "[INFO] test.logger: Test message");
    }

    #[test]
    fn test_default_formatter_different_levels() {
        let formatter = DefaultFormatter;

        let levels = [
            (LogLevel::Debug, "[DEBUG]"),
            (LogLevel::Info, "[INFO]"),
            (LogLevel::Warning, "[WARNING]"),
            (LogLevel::Error, "[ERROR]"),
            (LogLevel::Critical, "[CRITICAL]"),
        ];

        for (level, expected_prefix) in levels.iter() {
            let record = create_log_record("test".to_string(), *level, "message".to_string());

            let formatted = formatter.format(&record);
            assert!(formatted.starts_with(expected_prefix));
        }
    }

    #[test]
    fn test_python_formatter_basic() {
        let formatter = PythonFormatter::new("%(levelname)s - %(name)s - %(message)s".to_string());
        let record = create_log_record(
            "test.module".to_string(),
            LogLevel::Warning,
            "Warning message".to_string(),
        );

        let formatted = formatter.format(&record);
        assert_eq!(formatted, "WARNING - test.module - Warning message");
    }

    #[test]
    fn test_python_formatter_with_asctime() {
        let formatter = PythonFormatter::new("%(asctime)s - %(message)s".to_string());
        let record = create_log_record("test".to_string(), LogLevel::Info, "Time test".to_string());

        let formatted = formatter.format(&record);

        // Should contain a timestamp and the message
        assert!(formatted.contains(" - Time test"));
        assert!(formatted.len() > "Time test".len());

        // Check that it contains what looks like a timestamp
        let parts: Vec<&str> = formatted.split(" - ").collect();
        assert_eq!(parts.len(), 2);
        assert_eq!(parts[1], "Time test");
    }

    #[test]
    fn test_python_formatter_levelname_padding() {
        let formatter = PythonFormatter::new("%(levelname)-8s - %(message)s".to_string());

        let debug_record =
            create_log_record("test".to_string(), LogLevel::Debug, "msg".to_string());
        let critical_record =
            create_log_record("test".to_string(), LogLevel::Critical, "msg".to_string());

        let debug_formatted = formatter.format(&debug_record);
        let critical_formatted = formatter.format(&critical_record);

        // Both should have consistent formatting with padding
        assert!(debug_formatted.starts_with("DEBUG    - msg"));
        assert!(critical_formatted.starts_with("CRITICAL - msg"));
    }

    #[test]
    fn test_python_formatter_all_basic_fields() {
        let formatter = PythonFormatter::new(
            "%(levelno)d|%(thread)d|%(process)d|%(name)s|%(message)s".to_string(),
        );

        let record = create_log_record(
            "test".to_string(),
            LogLevel::Error,
            "all fields".to_string(),
        );

        let formatted = formatter.format(&record);

        // Should contain pipe-separated values
        let parts: Vec<&str> = formatted.split('|').collect();
        assert_eq!(parts.len(), 5);

        // First part should be levelno (40 for Error)
        assert_eq!(parts[0], "40");

        // Last parts should be name and message
        assert_eq!(parts[3], "test");
        assert_eq!(parts[4], "all fields");

        // Thread and process should be positive integers
        let _thread_id: u64 = parts[1].parse().unwrap();
        let process_id: u32 = parts[2].parse().unwrap();
        assert!(process_id > 0);
    }

    #[test]
    fn test_formatter_with_no_specifiers() {
        let formatter = PythonFormatter::new("Static message".to_string());
        let record = create_log_record("test".to_string(), LogLevel::Info, "ignored".to_string());

        let formatted = formatter.format(&record);
        assert_eq!(formatted, "Static message");
    }

    #[test]
    fn test_log_level_numeric_values() {
        assert_eq!(LogLevel::Debug as i32, 10);
        assert_eq!(LogLevel::Info as i32, 20);
        assert_eq!(LogLevel::Warning as i32, 30);
        assert_eq!(LogLevel::Error as i32, 40);
        assert_eq!(LogLevel::Critical as i32, 50);
        assert_eq!(LogLevel::NotSet as i32, 0);
    }

    #[test]
    fn test_python_formatter_message_replacement() {
        let formatter = PythonFormatter::new("LOG: %(message)s".to_string());
        let record = create_log_record(
            "test".to_string(),
            LogLevel::Info,
            "This is the actual message".to_string(),
        );

        let formatted = formatter.format(&record);
        assert_eq!(formatted, "LOG: This is the actual message");
    }
}
