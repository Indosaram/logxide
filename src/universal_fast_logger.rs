//! Universal fast logging optimization for all log levels
//!
//! This module provides a generic solution that makes ALL disabled logging
//! (debug, info, warning, error, critical) extremely fast, regardless of the
//! current logger level setting.

use crate::core::LogLevel;
use pyo3::prelude::*;
use std::sync::atomic::{AtomicU32, Ordering};

/// Universal fast logger that optimizes ALL log levels uniformly
#[pyclass]
pub struct UniversalFastLogger {
    /// Single atomic containing all state information
    /// Bits 0-7: current level (0-255)
    /// Bit 8: disabled flag
    /// Bits 9-31: reserved for future use
    state: AtomicU32,
    /// Logger name stored as static reference when possible
    name: &'static str,
}

impl UniversalFastLogger {
    // Bit masks for state field
    const LEVEL_MASK: u32 = 0x000000FF;  // Bits 0-7
    const DISABLED_MASK: u32 = 0x00000100;  // Bit 8

    pub fn new_static(name: &'static str) -> Self {
        Self {
            state: AtomicU32::new(LogLevel::Warning as u32),
            name,
        }
    }

    /// Universal fast check - works for ANY log level
    #[inline(always)]
    pub fn is_enabled_for(&self, level: LogLevel) -> bool {
        let state = self.state.load(Ordering::Relaxed);
        // Single comparison: not disabled AND level is high enough
        (state & Self::DISABLED_MASK) == 0 && (level as u32) >= (state & Self::LEVEL_MASK)
    }

    /// Set level and update state atomically
    pub fn set_level(&self, level: LogLevel) {
        let current = self.state.load(Ordering::Relaxed);
        let new_state = (current & !Self::LEVEL_MASK) | (level as u32);
        self.state.store(new_state, Ordering::Relaxed);
    }

    /// Set disabled state
    pub fn set_disabled(&self, disabled: bool) {
        let current = self.state.load(Ordering::Relaxed);
        let new_state = if disabled {
            current | Self::DISABLED_MASK
        } else {
            current & !Self::DISABLED_MASK
        };
        self.state.store(new_state, Ordering::Relaxed);
    }
}

#[pymethods]
impl UniversalFastLogger {
    /// Generic logging method that works efficiently for ALL levels
    fn log(&self, level: u32, msg: &str) {
        let log_level = LogLevel::from_usize(level as usize);
        if self.is_enabled_for(log_level) {
            self.send_message(log_level, msg);
        }
    }

    /// All specific level methods use the same optimized pattern
    fn debug(&self, msg: &str) {
        if self.is_enabled_for(LogLevel::Debug) {
            self.send_message(LogLevel::Debug, msg);
        }
    }

    fn info(&self, msg: &str) {
        if self.is_enabled_for(LogLevel::Info) {
            self.send_message(LogLevel::Info, msg);
        }
    }

    fn warning(&self, msg: &str) {
        if self.is_enabled_for(LogLevel::Warning) {
            self.send_message(LogLevel::Warning, msg);
        }
    }

    fn error(&self, msg: &str) {
        if self.is_enabled_for(LogLevel::Error) {
            self.send_message(LogLevel::Error, msg);
        }
    }

    fn critical(&self, msg: &str) {
        if self.is_enabled_for(LogLevel::Critical) {
            self.send_message(LogLevel::Critical, msg);
        }
    }

    /// Fast level checking without any message processing
    fn is_enabled_for_level(&self, level: u32) -> bool {
        let log_level = LogLevel::from_usize(level as usize);
        self.is_enabled_for(log_level)
    }
}

impl UniversalFastLogger {
    fn send_message(&self, level: LogLevel, msg: &str) {
        use crate::{create_log_record, SENDER, LogMessage};
        let record = create_log_record(
            self.name.to_string(),
            level,
            msg.to_string(),
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
    }
}

/// Macro for generating optimized logging methods
macro_rules! generate_universal_log_method {
    ($level:expr) => {
        #[inline(always)]
        fn log(&self, msg: &str) {
            // Compiler can optimize this constant at compile time
            const LEVEL: LogLevel = $level;
            const LEVEL_U32: u32 = LEVEL as u32;

            let state = self.state.load(Ordering::Relaxed);
            if (state & Self::DISABLED_MASK) == 0 && LEVEL_U32 >= (state & Self::LEVEL_MASK) {
                self.send_message(LEVEL, msg);
            }
        }
    };
}

/// Alternative implementation using trait for compile-time optimization
pub trait FastLoggable {
    const LEVEL: LogLevel;

    #[inline(always)]
    fn log_if_enabled(&self, logger: &UniversalFastLogger, msg: &str) {
        if logger.is_enabled_for(Self::LEVEL) {
            logger.send_message(Self::LEVEL, msg);
        }
    }
}

/// Zero-cost abstractions for each log level
pub struct DebugLevel;
pub struct InfoLevel;
pub struct WarningLevel;
pub struct ErrorLevel;
pub struct CriticalLevel;

impl FastLoggable for DebugLevel {
    const LEVEL: LogLevel = LogLevel::Debug;
}

impl FastLoggable for InfoLevel {
    const LEVEL: LogLevel = LogLevel::Info;
}

impl FastLoggable for WarningLevel {
    const LEVEL: LogLevel = LogLevel::Warning;
}

impl FastLoggable for ErrorLevel {
    const LEVEL: LogLevel = LogLevel::Error;
}

impl FastLoggable for CriticalLevel {
    const LEVEL: LogLevel = LogLevel::Critical;
}

/// Generic logging function that works for all levels
#[pyfunction]
pub fn log_universal(logger: &UniversalFastLogger, level: u32, msg: &str) {
    logger.log(level, msg);
}

/// Pre-compiled level checking functions for maximum performance
#[pyfunction]
pub fn debug_enabled(logger: &UniversalFastLogger) -> bool {
    logger.is_enabled_for(LogLevel::Debug)
}

#[pyfunction]
pub fn info_enabled(logger: &UniversalFastLogger) -> bool {
    logger.is_enabled_for(LogLevel::Info)
}

#[pyfunction]
pub fn warning_enabled(logger: &UniversalFastLogger) -> bool {
    logger.is_enabled_for(LogLevel::Warning)
}

#[pyfunction]
pub fn error_enabled(logger: &UniversalFastLogger) -> bool {
    logger.is_enabled_for(LogLevel::Error)
}

#[pyfunction]
pub fn critical_enabled(logger: &UniversalFastLogger) -> bool {
    logger.is_enabled_for(LogLevel::Critical)
}

/// Batch level checking for multiple levels at once
#[pyfunction]
pub fn get_enabled_levels(logger: &UniversalFastLogger) -> Vec<u32> {
    let state = logger.state.load(Ordering::Relaxed);
    if (state & UniversalFastLogger::DISABLED_MASK) != 0 {
        return Vec::new(); // All disabled
    }

    let current_level = state & UniversalFastLogger::LEVEL_MASK;
    let mut enabled = Vec::new();

    if LogLevel::Debug as u32 >= current_level { enabled.push(LogLevel::Debug as u32); }
    if LogLevel::Info as u32 >= current_level { enabled.push(LogLevel::Info as u32); }
    if LogLevel::Warning as u32 >= current_level { enabled.push(LogLevel::Warning as u32); }
    if LogLevel::Error as u32 >= current_level { enabled.push(LogLevel::Error as u32); }
    if LogLevel::Critical as u32 >= current_level { enabled.push(LogLevel::Critical as u32); }

    enabled
}

/// Ultra-fast logging with compile-time level specialization
pub struct SpecializedLogger<L: FastLoggable> {
    inner: UniversalFastLogger,
    _phantom: std::marker::PhantomData<L>,
}

impl<L: FastLoggable> SpecializedLogger<L> {
    pub fn new(name: &'static str) -> Self {
        Self {
            inner: UniversalFastLogger::new_static(name),
            _phantom: std::marker::PhantomData,
        }
    }

    #[inline(always)]
    pub fn log(&self, msg: &str) {
        L::log_if_enabled(&self.inner, msg);
    }
}

/// Type aliases for specialized loggers
pub type FastDebugLogger = SpecializedLogger<DebugLevel>;
pub type FastInfoLogger = SpecializedLogger<InfoLevel>;
pub type FastWarningLogger = SpecializedLogger<WarningLevel>;
pub type FastErrorLogger = SpecializedLogger<ErrorLevel>;
pub type FastCriticalLogger = SpecializedLogger<CriticalLevel>;
