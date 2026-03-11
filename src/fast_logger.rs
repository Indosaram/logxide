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

    /// Set level on this logger only (no child propagation).
    /// Prefer `set_level_and_propagate` via the manager for proper inheritance.
    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u32, Ordering::Relaxed);
        // Don't call update_effective_level here — caller should use
        // the manager's set_level_and_propagate for proper inheritance.
        // But we keep a simple self-update for backward compat:
        let effective = if level == LogLevel::NotSet {
            // NotSet means "inherit from parent" — keep current effective_level
            // The manager will handle proper inheritance.
            self.effective_level.load(Ordering::Relaxed)
        } else {
            level as u32
        };
        self.effective_level.store(effective, Ordering::Relaxed);
    }

    pub fn get_level(&self) -> LogLevel {
        LogLevel::from_usize(self.level.load(Ordering::Relaxed) as usize)
    }

    /// Get the effective level (may be inherited from parent).
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
        let parent_level = self.find_parent_effective_level(name);

        let logger = Arc::new(FastLogger::new(name));
        // Initialize with parent's effective level
        logger
            .effective_level
            .store(parent_level, Ordering::Relaxed);

        self.loggers.insert(name.to_string(), logger.clone());
        logger
    }

    /// Set level on a logger and propagate effective level changes to all children.
    /// This mimics stdlib's Logger.setLevel() + manager._clear_cache() behavior.
    pub fn set_level_and_propagate(&self, name: &str, level: LogLevel) {
        let logger = if name.is_empty() || name == "root" {
            self.root_logger.clone()
        } else if let Some(l) = self.loggers.get(name) {
            l.clone()
        } else {
            // Logger doesn't exist yet in fast_logger manager, create it
            return self.get_logger(name).set_level(level);
        };

        // Set the level on this logger
        logger.level.store(level as u32, Ordering::Relaxed);
        let new_effective = if level == LogLevel::NotSet {
            self.find_parent_effective_level(name)
        } else {
            level as u32
        };
        logger.effective_level.store(new_effective, Ordering::Relaxed);

        // Propagate to all child loggers
        self.propagate_effective_levels(name, new_effective);
    }

    /// Find the effective level from the nearest parent logger.
    fn find_parent_effective_level(&self, name: &str) -> u32 {
        let mut current_name = name;
        while let Some(dot_idx) = current_name.rfind('.') {
            current_name = &current_name[0..dot_idx];
            if let Some(parent) = self.loggers.get(current_name) {
                return parent.effective_level.load(Ordering::Relaxed);
            }
        }
        // Fall back to root logger
        self.root_logger.effective_level.load(Ordering::Relaxed)
    }

    /// Propagate effective level changes to all child loggers.
    /// A child logger is one whose name starts with `parent_name + "."`.
    /// Only updates children that have their own level set to NotSet (i.e., inheriting).
    fn propagate_effective_levels(&self, parent_name: &str, parent_effective: u32) {
        let prefix = if parent_name.is_empty() || parent_name == "root" {
            // Root logger: all loggers are children
            String::new()
        } else {
            format!("{}.", parent_name)
        };

        for entry in self.loggers.iter() {
            let child_name = entry.key();
            let child = entry.value();

            // Check if this is a child of the parent
            let is_child = if prefix.is_empty() {
                true // Root: everything is a child
            } else {
                child_name.starts_with(&prefix)
            };

            if !is_child {
                continue;
            }

            // Only update if the child's own level is NotSet (inheriting)
            let child_own_level = child.level.load(Ordering::Relaxed);
            if child_own_level == LogLevel::NotSet as u32 {
                // This child inherits — find its nearest parent effective level.
                // For direct children, it's parent_effective.
                // For deeper descendants, we need to check intermediate parents.
                let nearest_effective = self.find_nearest_effective_level(child_name, parent_name, parent_effective);
                child.effective_level.store(nearest_effective, Ordering::Relaxed);
            }
            // If the child has its own level set, it doesn't inherit and doesn't change.
        }
    }

    /// Find the nearest ancestor's effective level for a child logger,
    /// stopping at `changed_ancestor_name` with `changed_effective`.
    fn find_nearest_effective_level(&self, child_name: &str, changed_ancestor_name: &str, changed_effective: u32) -> u32 {
        let mut current_name = child_name;
        while let Some(dot_idx) = current_name.rfind('.') {
            current_name = &current_name[0..dot_idx];

            // If we reached the changed ancestor, use its new effective level
            if current_name == changed_ancestor_name {
                return changed_effective;
            }

            // Check if there's an intermediate logger with its own level set
            if let Some(intermediate) = self.loggers.get(current_name) {
                let intermediate_level = intermediate.level.load(Ordering::Relaxed);
                if intermediate_level != LogLevel::NotSet as u32 {
                    // This intermediate has its own level — child inherits from here, not from changed ancestor
                    return intermediate_level;
                }
            }
        }

        // Reached root
        if changed_ancestor_name.is_empty() || changed_ancestor_name == "root" {
            changed_effective
        } else {
            self.root_logger.effective_level.load(Ordering::Relaxed)
        }
    }

    #[allow(dead_code)]
    pub fn get_root_logger(&self) -> Arc<FastLogger> {
        self.root_logger.clone()
    }
}

/// Global fast logger manager instance
static FAST_LOGGER_MANAGER: Lazy<FastLoggerManager> = Lazy::new(FastLoggerManager::new);

pub fn get_fast_logger(name: &str) -> Arc<FastLogger> {
    FAST_LOGGER_MANAGER.get_logger(name)
}

/// Set level on a logger and propagate changes to all child loggers.
pub fn set_level_and_propagate(name: &str, level: LogLevel) {
    FAST_LOGGER_MANAGER.set_level_and_propagate(name, level);
}

#[allow(dead_code)]
pub fn get_fast_root_logger() -> Arc<FastLogger> {
    FAST_LOGGER_MANAGER.get_root_logger()
}
