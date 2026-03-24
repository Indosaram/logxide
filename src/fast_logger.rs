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
    pub(crate) effective_level: AtomicU32,
    disabled: AtomicBool,
    #[allow(dead_code)]
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

    pub fn get_effective_level(&self) -> u32 {
        self.effective_level.load(Ordering::Relaxed)
    }

    #[allow(dead_code)]
    pub fn set_disabled(&self, disabled: bool) {
        self.disabled.store(disabled, Ordering::Relaxed);
    }

    #[allow(dead_code)]
    pub fn is_disabled(&self) -> bool {
        self.disabled.load(Ordering::Relaxed)
    }

    fn update_effective_level(&self) {
        let level = self.level.load(Ordering::Relaxed);
        // Only update effective_level when an explicit level is set.
        // For NOTSET, leave effective_level unchanged — it will be
        // resolved correctly by propagate_effective_levels().
        if level != LogLevel::NotSet as u32 {
            self.effective_level.store(level, Ordering::Relaxed);
        }
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
        let root = Arc::new(FastLogger::new("root"));
        root.set_level(LogLevel::Warning);

        Self {
            loggers: DashMap::new(),
            root_logger: root,
        }
    }

    pub fn get_logger(&self, name: &str) -> Arc<FastLogger> {
        if name.is_empty() || name == "root" {
            return self.root_logger.clone();
        }

        if let Some(logger) = self.loggers.get(name) {
            return logger.clone();
        }

        // Inheritance logic: Find nearest ancestor to inherit effective level
        let mut parent_level = self.root_logger.effective_level.load(Ordering::Relaxed);
        let mut current_name = name;

        while let Some(dot_idx) = current_name.rfind('.') {
            current_name = &current_name[0..dot_idx];
            if let Some(parent) = self.loggers.get(current_name) {
                parent_level = parent.effective_level.load(Ordering::Relaxed);
                break;
            }
        }

        let logger = Arc::new(FastLogger::new(name));
        // Initialize with parent's effective level
        logger
            .effective_level
            .store(parent_level, Ordering::Relaxed);

        self.loggers.insert(name.to_string(), logger.clone());
        logger
    }

    #[allow(dead_code)]
    pub fn get_root_logger(&self) -> Arc<FastLogger> {
        self.root_logger.clone()
    }

    /// Recompute effective_level for all loggers based on their parent chain.
    /// Called after any logger's level changes (cold path — setLevel is rare).
    pub fn propagate_effective_levels(&self) {
        // Update root's effective level first
        let root_level = self.root_logger.level.load(Ordering::Relaxed);
        let root_effective = if root_level == LogLevel::NotSet as u32 {
            LogLevel::Warning as u32
        } else {
            root_level
        };
        self.root_logger
            .effective_level
            .store(root_effective, Ordering::Relaxed);

        // Update all other loggers
        for entry in self.loggers.iter() {
            let logger = entry.value();
            let own_level = logger.level.load(Ordering::Relaxed);
            let effective = if own_level != LogLevel::NotSet as u32 {
                own_level
            } else {
                self.resolve_parent_effective_level(entry.key())
            };
            logger.effective_level.store(effective, Ordering::Relaxed);
        }
    }

    /// Walk up the parent chain to find the nearest ancestor with a non-NOTSET level.
    fn resolve_parent_effective_level(&self, name: &str) -> u32 {
        let mut current: &str = name;
        while let Some(dot_idx) = current.rfind('.') {
            current = &current[..dot_idx];
            if let Some(parent) = self.loggers.get(current) {
                let parent_level = parent.level.load(Ordering::Relaxed);
                if parent_level != LogLevel::NotSet as u32 {
                    return parent_level;
                }
                // Parent is also NOTSET, keep walking up
            }
        }
        // Reached root
        let root_level = self.root_logger.level.load(Ordering::Relaxed);
        if root_level != LogLevel::NotSet as u32 {
            root_level
        } else {
            LogLevel::Warning as u32
        }
    }
}

/// Global fast logger manager instance
static FAST_LOGGER_MANAGER: Lazy<FastLoggerManager> = Lazy::new(FastLoggerManager::new);

pub fn get_fast_logger(name: &str) -> Arc<FastLogger> {
    FAST_LOGGER_MANAGER.get_logger(name)
}

#[allow(dead_code)]
pub fn get_fast_root_logger() -> Arc<FastLogger> {
    FAST_LOGGER_MANAGER.get_root_logger()
}

/// Propagate effective levels for all loggers after a level change.
pub fn propagate_all_effective_levels() {
    FAST_LOGGER_MANAGER.propagate_effective_levels();
}
