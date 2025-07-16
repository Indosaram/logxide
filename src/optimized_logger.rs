//! Optimized logger implementation for disabled logging performance
//!
//! This module provides ultra-fast implementations specifically optimized
//! for the case where logging is disabled.

use crate::core::LogLevel;
use std::sync::atomic::{AtomicU32, Ordering};

/// Ultra-fast logger optimized for disabled logging scenarios
pub struct OptimizedLogger {
    /// Single atomic for the effective level - no separate disabled flag
    effective_level: AtomicU32,
    /// Cache the logger name as a static reference when possible
    name: &'static str,
}

impl OptimizedLogger {
    /// Create a new optimized logger with a static name
    pub fn new_static(name: &'static str) -> Self {
        Self {
            effective_level: AtomicU32::new(LogLevel::Warning as u32),
            name,
        }
    }

    /// Ultra-fast level check using only one atomic operation
    #[inline(always)]
    pub fn is_debug_enabled(&self) -> bool {
        (LogLevel::Debug as u32) >= self.effective_level.load(Ordering::Relaxed)
    }

    #[inline(always)]
    pub fn is_info_enabled(&self) -> bool {
        (LogLevel::Info as u32) >= self.effective_level.load(Ordering::Relaxed)
    }

    #[inline(always)]
    pub fn is_warning_enabled(&self) -> bool {
        (LogLevel::Warning as u32) >= self.effective_level.load(Ordering::Relaxed)
    }

    /// Set level with immediate effective level update
    pub fn set_level(&self, level: LogLevel) {
        self.effective_level.store(level as u32, Ordering::Relaxed);
    }
}

/// Compile-time optimized logging macros
macro_rules! log_if_enabled {
    ($logger:expr, $level:expr, $msg:expr) => {
        if $level as u32 >= $logger.effective_level.load(Ordering::Relaxed) {
            // Only do expensive work if enabled
            $crate::send_log_message($logger.name, $level, $msg);
        }
    };
}

/// Zero-overhead debug logging when disabled
macro_rules! debug_fast {
    ($logger:expr, $msg:expr) => {
        if (LogLevel::Debug as u32) >= $logger.effective_level.load(Ordering::Relaxed) {
            $crate::send_log_message($logger.name, LogLevel::Debug, $msg);
        }
    };
}

/// Python wrapper functions optimized for each level
use pyo3::prelude::*;

#[pyclass]
pub struct PyOptimizedLogger {
    inner: OptimizedLogger,
}

#[pymethods]
impl PyOptimizedLogger {
    /// Separate methods for each level to minimize function call overhead
    fn debug_fast(&self, msg: &str) {
        // Single atomic check, no string processing unless enabled
        if self.inner.is_debug_enabled() {
            // Only allocate and process if enabled
            self.send_message(LogLevel::Debug, msg);
        }
    }

    fn info_fast(&self, msg: &str) {
        if self.inner.is_info_enabled() {
            self.send_message(LogLevel::Info, msg);
        }
    }

    fn warning_fast(&self, msg: &str) {
        if self.inner.is_warning_enabled() {
            self.send_message(LogLevel::Warning, msg);
        }
    }

    /// Check if level is enabled without any message processing
    fn is_enabled_for(&self, level: u32) -> bool {
        level >= self.inner.effective_level.load(Ordering::Relaxed)
    }
}

impl PyOptimizedLogger {
    fn send_message(&self, level: LogLevel, msg: &str) {
        // Minimal message creation and sending
        use crate::{create_log_record, SENDER, LogMessage};
        let record = create_log_record(
            self.inner.name.to_string(),
            level,
            msg.to_string(),
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
    }
}

/// Global optimization: Pre-compute common loggers
use once_cell::sync::Lazy;
use std::collections::HashMap;

static COMMON_LOGGERS: Lazy<HashMap<&'static str, OptimizedLogger>> = Lazy::new(|| {
    let mut map = HashMap::new();
    map.insert("benchmark", OptimizedLogger::new_static("benchmark"));
    map.insert("main", OptimizedLogger::new_static("main"));
    map.insert("app", OptimizedLogger::new_static("app"));
    map
});

/// Get a pre-optimized logger for common names
pub fn get_optimized_logger(name: &str) -> Option<&'static OptimizedLogger> {
    COMMON_LOGGERS.get(name)
}
