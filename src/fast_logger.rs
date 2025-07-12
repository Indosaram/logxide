//! Fast logger implementation using atomic operations
//!
//! This module provides a lock-free logger implementation optimized for
//! high-performance scenarios where traditional mutex-based loggers
//! become a bottleneck.

use crate::core::LogLevel;
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::Arc;

/// Fast logger using atomic operations for lock-free level checking
#[derive(Debug)]
pub struct FastLogger {
    pub name: Arc<str>,
    level: AtomicU32,
    effective_level: AtomicU32,
    disabled: AtomicBool,
    propagate: AtomicBool,
}

impl FastLogger {
    pub fn new(name: &str) -> Self {
        Self {
            name: Arc::from(name),
            level: AtomicU32::new(LogLevel::NotSet as u32),
            effective_level: AtomicU32::new(LogLevel::Warning as u32), // Default
            disabled: AtomicBool::new(false),
            propagate: AtomicBool::new(true),
        }
    }

    #[inline(always)]
    pub fn is_enabled_for(&self, level: LogLevel) -> bool {
        !self.disabled.load(Ordering::Relaxed)
            && level as u32 >= self.effective_level.load(Ordering::Relaxed)
    }

    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u32, Ordering::Relaxed);
        self.update_effective_level();
    }

    pub fn get_level(&self) -> LogLevel {
        LogLevel::from_usize(self.level.load(Ordering::Relaxed) as usize)
    }

    pub fn set_disabled(&self, disabled: bool) {
        self.disabled.store(disabled, Ordering::Relaxed);
    }

    pub fn is_disabled(&self) -> bool {
        self.disabled.load(Ordering::Relaxed)
    }

    fn update_effective_level(&self) {
        let level = self.level.load(Ordering::Relaxed);
        let effective = if level == LogLevel::NotSet as u32 {
            LogLevel::Warning as u32 // Default effective level
        } else {
            level
        };
        self.effective_level.store(effective, Ordering::Relaxed);
    }
}

/// Fast logger manager using DashMap for concurrent access
use dashmap::DashMap;
use once_cell::sync::Lazy;

pub struct FastLoggerManager {
    loggers: DashMap<String, Arc<FastLogger>>,
    root_logger: Arc<FastLogger>,
}

impl FastLoggerManager {
    pub fn new() -> Self {
        let root = Arc::new(FastLogger::new(""));
        root.set_level(LogLevel::Warning);

        Self {
            loggers: DashMap::new(),
            root_logger: root,
        }
    }

    pub fn get_logger(&self, name: &str) -> Arc<FastLogger> {
        if name.is_empty() {
            return self.root_logger.clone();
        }

        match self.loggers.get(name) {
            Some(logger) => logger.clone(),
            None => {
                let logger = Arc::new(FastLogger::new(name));
                self.loggers.insert(name.to_string(), logger.clone());
                logger
            }
        }
    }

    pub fn get_root_logger(&self) -> Arc<FastLogger> {
        self.root_logger.clone()
    }
}

/// Global fast logger manager instance
static FAST_LOGGER_MANAGER: Lazy<FastLoggerManager> = Lazy::new(|| FastLoggerManager::new());

pub fn get_fast_logger(name: &str) -> Arc<FastLogger> {
    FAST_LOGGER_MANAGER.get_logger(name)
}

pub fn get_fast_root_logger() -> Arc<FastLogger> {
    FAST_LOGGER_MANAGER.get_root_logger()
}
