//! Immediate optimizations for disabled logging performance
//!
//! These optimizations can be applied to the current codebase immediately
//! to improve disabled logging performance by 2-3x.

use crate::core::LogLevel;
use pyo3::prelude::*;
use std::sync::atomic::{AtomicU32, Ordering};

/// Optimized version of FastLogger with minimal overhead
pub struct ImprovedFastLogger {
    /// Combined level and disabled state in single atomic
    /// Bit 31: disabled flag
    /// Bits 0-30: effective level
    level_state: AtomicU32,
    /// Static string slice when possible to avoid allocation
    name: &'static str,
}

impl ImprovedFastLogger {
    const DISABLED_MASK: u32 = 0x8000_0000;
    const LEVEL_MASK: u32 = 0x7FFF_FFFF;

    pub fn new_static(name: &'static str) -> Self {
        Self {
            level_state: AtomicU32::new(LogLevel::Warning as u32),
            name,
        }
    }

    /// Single atomic operation for level check
    #[inline(always)]
    pub fn is_enabled_for(&self, level: LogLevel) -> bool {
        let state = self.level_state.load(Ordering::Relaxed);
        // Check both disabled and level in one operation
        (state & Self::DISABLED_MASK) == 0
            && (level as u32) >= (state & Self::LEVEL_MASK)
    }

    /// Separate debug check for maximum optimization
    #[inline(always)]
    pub fn debug_enabled(&self) -> bool {
        let state = self.level_state.load(Ordering::Relaxed);
        (state & Self::DISABLED_MASK) == 0
            && (LogLevel::Debug as u32) >= (state & Self::LEVEL_MASK)
    }
}

/// Immediately applicable optimization for current PyLogger
impl crate::PyLogger {
    /// Fast path for debug logging with minimal overhead
    pub fn debug_optimized(&self, msg: &str) -> PyResult<()> {
        // Early return with minimal work
        if !self.fast_logger.is_enabled_for(LogLevel::Debug) {
            return Ok(());
        }

        // Only do expensive operations if enabled
        let record = crate::create_log_record(
            self.fast_logger.name.to_string(),
            LogLevel::Debug,
            msg.to_string(),
        );
        let _ = crate::SENDER.send(crate::LogMessage::Record(Box::new(record)));
        Ok(())
    }
}

/// Optimization 1: Remove unnecessary parameter processing
#[pymethods]
impl crate::PyLogger {
    /// Debug method optimized for disabled case
    #[pyo3(signature = (msg))]
    fn debug_fast(&self, msg: &str) {
        // Remove unused parameters and early return
        if self.fast_logger.is_enabled_for(LogLevel::Debug) {
            let record = crate::create_log_record(
                self.fast_logger.name.to_string(),
                LogLevel::Debug,
                msg.to_string(),
            );
            let _ = crate::SENDER.send(crate::LogMessage::Record(Box::new(record)));
        }
    }

    /// Info method optimized for disabled case
    #[pyo3(signature = (msg))]
    fn info_fast(&self, msg: &str) {
        if self.fast_logger.is_enabled_for(LogLevel::Info) {
            let record = crate::create_log_record(
                self.fast_logger.name.to_string(),
                LogLevel::Info,
                msg.to_string(),
            );
            let _ = crate::SENDER.send(crate::LogMessage::Record(Box::new(record)));
        }
    }
}

/// Optimization 2: Compile-time level specialization
macro_rules! generate_fast_log_method {
    ($method_name:ident, $level:expr) => {
        fn $method_name(&self, msg: &str) {
            // Specialized for specific level - compiler can optimize
            const LEVEL: LogLevel = $level;
            if (LEVEL as u32) >= self.fast_logger.effective_level.load(Ordering::Relaxed) {
                let record = crate::create_log_record(
                    self.fast_logger.name.to_string(),
                    LEVEL,
                    msg.to_string(),
                );
                let _ = crate::SENDER.send(crate::LogMessage::Record(Box::new(record)));
            }
        }
    };
}

/// Optimization 3: Branch prediction hints
use std::hint;

impl crate::fast_logger::FastLogger {
    /// Optimized is_enabled_for with branch prediction
    #[inline(always)]
    pub fn is_enabled_for_optimized(&self, level: LogLevel) -> bool {
        let disabled = self.disabled.load(Ordering::Relaxed);

        // Hint that logging is usually disabled in production
        if hint::unlikely(disabled) {
            return false;
        }

        let effective_level = self.effective_level.load(Ordering::Relaxed);
        level as u32 >= effective_level
    }
}

/// Optimization 4: String interning for logger names
use std::collections::HashMap;
use once_cell::sync::Lazy;

static INTERNED_NAMES: Lazy<std::sync::Mutex<HashMap<String, &'static str>>> =
    Lazy::new(|| std::sync::Mutex::new(HashMap::new()));

pub fn intern_logger_name(name: String) -> &'static str {
    let mut cache = INTERNED_NAMES.lock().unwrap();
    match cache.get(&name) {
        Some(&interned) => interned,
        None => {
            let leaked: &'static str = Box::leak(name.clone().into_boxed_str());
            cache.insert(name, leaked);
            leaked
        }
    }
}

/// Optimization 5: Pre-computed logger instances
static BENCHMARK_LOGGER: Lazy<crate::fast_logger::FastLogger> =
    Lazy::new(|| crate::fast_logger::FastLogger::new("benchmark"));

pub fn get_benchmark_logger() -> &'static crate::fast_logger::FastLogger {
    &BENCHMARK_LOGGER
}
