//! Pure Rust implementations for testing without PyO3 dependencies

use std::collections::HashMap;
use std::sync::{Arc, Mutex};

/// Log levels, matching Python's logging levels - Pure Rust version
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

/// Pure Rust LogRecord without PyO3 dependencies
#[derive(Debug, Clone)]
#[allow(dead_code)]
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
}

/// Pure Rust Logger without handlers/filters that depend on traits
pub struct Logger {
    pub name: String,
    pub level: LogLevel,
    pub parent: Option<Arc<Mutex<Logger>>>,
    pub propagate: bool,
}

impl Logger {
    pub fn new(name: &str) -> Self {
        Logger {
            name: name.to_string(),
            level: LogLevel::NotSet,
            parent: None,
            propagate: true,
        }
    }

    pub fn set_level(&mut self, level: LogLevel) {
        self.level = level;
    }

    pub fn get_effective_level(&self) -> LogLevel {
        if self.level != LogLevel::NotSet {
            return self.level;
        }

        if let Some(ref parent) = self.parent {
            return parent.lock().unwrap().get_effective_level();
        }

        LogLevel::Warning
    }

    pub fn is_enabled_for(&self, level: LogLevel) -> bool {
        level >= self.get_effective_level()
    }

    pub fn make_log_record(&self, level: LogLevel, msg: &str) -> LogRecord {
        create_log_record(self.name.clone(), level, msg.to_string())
    }
}

/// Helper function to create a LogRecord - Pure Rust version
pub fn create_log_record(name: String, level: LogLevel, msg: String) -> LogRecord {
    use std::thread;

    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap();
    let created = now.as_secs_f64();
    let msecs = (now.subsec_millis() % 1000) as f64;

    let current_thread = thread::current();
    let thread_id = format!("{:?}", current_thread.id());
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
        thread_name: current_thread.name().unwrap_or("unnamed").to_string(),
        process_name: "".to_string(),
        process: std::process::id(),
        msg,
    }
}

/// Pure Rust LoggerManager
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

    pub fn get_logger(&self, name: &str) -> Arc<Mutex<Logger>> {
        {
            let loggers = self.loggers.lock().unwrap();
            if let Some(logger) = loggers.get(name) {
                return logger.clone();
            }
        }

        let parent_logger = if name != "root" {
            let parent_name = name.rsplit_once('.').map(|x| x.0).unwrap_or("root");
            Some(self.get_logger(parent_name))
        } else {
            None
        };

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

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Arc, Mutex};

    #[test]
    fn test_log_level_ordering() {
        assert!(LogLevel::Debug < LogLevel::Info);
        assert!(LogLevel::Info < LogLevel::Warning);
        assert!(LogLevel::Warning < LogLevel::Error);
        assert!(LogLevel::Error < LogLevel::Critical);
        assert!(LogLevel::Critical > LogLevel::Debug);
    }

    #[test]
    fn test_log_level_from_usize() {
        assert_eq!(LogLevel::from_usize(10), LogLevel::Debug);
        assert_eq!(LogLevel::from_usize(20), LogLevel::Info);
        assert_eq!(LogLevel::from_usize(30), LogLevel::Warning);
        assert_eq!(LogLevel::from_usize(40), LogLevel::Error);
        assert_eq!(LogLevel::from_usize(50), LogLevel::Critical);
        assert_eq!(LogLevel::from_usize(999), LogLevel::NotSet);
    }

    #[test]
    fn test_logger_creation() {
        let logger = Logger::new("test");
        assert_eq!(logger.name, "test");
        assert_eq!(logger.level, LogLevel::NotSet);
        assert!(logger.propagate);
    }

    #[test]
    fn test_logger_set_level() {
        let mut logger = Logger::new("test");
        logger.set_level(LogLevel::Debug);
        assert_eq!(logger.level, LogLevel::Debug);

        logger.set_level(LogLevel::Critical);
        assert_eq!(logger.level, LogLevel::Critical);
    }

    #[test]
    fn test_logger_effective_level() {
        let mut logger = Logger::new("test");

        // Default effective level should be Warning
        assert_eq!(logger.get_effective_level(), LogLevel::Warning);

        // Set explicit level
        logger.set_level(LogLevel::Debug);
        assert_eq!(logger.get_effective_level(), LogLevel::Debug);

        // Test with parent logger
        let parent = Arc::new(Mutex::new(Logger::new("parent")));
        parent.lock().unwrap().set_level(LogLevel::Info);

        let mut child = Logger::new("parent.child");
        child.parent = Some(parent.clone());

        // Child should inherit parent's level
        assert_eq!(child.get_effective_level(), LogLevel::Info);

        // Child's own level should override parent
        child.set_level(LogLevel::Error);
        assert_eq!(child.get_effective_level(), LogLevel::Error);
    }

    #[test]
    fn test_logger_is_enabled_for() {
        let mut logger = Logger::new("test");
        logger.set_level(LogLevel::Warning);

        assert!(!logger.is_enabled_for(LogLevel::Debug));
        assert!(!logger.is_enabled_for(LogLevel::Info));
        assert!(logger.is_enabled_for(LogLevel::Warning));
        assert!(logger.is_enabled_for(LogLevel::Error));
        assert!(logger.is_enabled_for(LogLevel::Critical));
    }

    #[test]
    fn test_create_log_record() {
        let record = create_log_record(
            "test.logger".to_string(),
            LogLevel::Info,
            "Test message".to_string(),
        );

        assert_eq!(record.name, "test.logger");
        assert_eq!(record.levelno, LogLevel::Info as i32);
        assert_eq!(record.levelname, "INFO");
        assert_eq!(record.msg, "Test message");
        assert!(record.created > 0.0);
        assert!(record.process > 0);
    }

    #[test]
    fn test_logger_manager_get_logger() {
        let manager = LoggerManager::new();

        let logger1 = manager.get_logger("test");
        let logger2 = manager.get_logger("test");

        // Should return the same logger instance
        assert!(Arc::ptr_eq(&logger1, &logger2));

        // Different names should return different loggers
        let logger3 = manager.get_logger("different");
        assert!(!Arc::ptr_eq(&logger1, &logger3));
    }

    #[test]
    fn test_logger_hierarchy() {
        let manager = LoggerManager::new();

        let parent = manager.get_logger("myapp");
        let child = manager.get_logger("myapp.database");
        let grandchild = manager.get_logger("myapp.database.connection");

        // Check hierarchy is set up correctly
        assert!(child.lock().unwrap().parent.is_some());
        assert!(grandchild.lock().unwrap().parent.is_some());

        // Child's parent should be the parent logger
        let child_parent = child.lock().unwrap().parent.as_ref().unwrap().clone();
        assert!(Arc::ptr_eq(&parent, &child_parent));
    }

    #[test]
    fn test_logger_make_log_record() {
        let logger = Logger::new("test.logger");
        let record = logger.make_log_record(LogLevel::Warning, "Test warning");

        assert_eq!(record.name, "test.logger");
        assert_eq!(record.levelno, LogLevel::Warning as i32);
        assert_eq!(record.levelname, "WARNING");
        assert_eq!(record.msg, "Test warning");
        assert!(record.created > 0.0);
    }

    #[test]
    fn test_root_logger() {
        let manager = LoggerManager::new();
        let root1 = manager.get_root_logger();
        let root2 = manager.get_root_logger();

        // Should be the same instance
        assert!(Arc::ptr_eq(&root1, &root2));

        // Root logger should have "root" name
        assert_eq!(root1.lock().unwrap().name, "root");
    }
}
