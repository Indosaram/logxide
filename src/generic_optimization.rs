//! Generic optimization strategy for universal fast disabled logging
//!
//! This module implements a comprehensive approach to make ALL log levels
//! perform optimally when disabled, using generic programming and
//! compile-time optimizations.

use crate::core::LogLevel;
use pyo3::prelude::*;
use std::sync::atomic::{AtomicU32, Ordering};

/// Core optimization principle: Single atomic operation for all checks
#[derive(Debug)]
pub struct OptimizedLogState {
    /// Packed state: [disabled:1][reserved:7][level:8][reserved:16]
    /// This allows single atomic load to determine ALL logging decisions
    packed_state: AtomicU32,
}

impl OptimizedLogState {
    const DISABLED_BIT: u32 = 31;
    const LEVEL_SHIFT: u32 = 16;
    const LEVEL_MASK: u32 = 0x00FF0000;

    pub fn new(level: LogLevel) -> Self {
        Self {
            packed_state: AtomicU32::new((level as u32) << Self::LEVEL_SHIFT),
        }
    }

    /// Universal fast check - works for ANY log level with single atomic load
    #[inline(always)]
    pub fn is_enabled_for(&self, level: LogLevel) -> bool {
        let state = self.packed_state.load(Ordering::Relaxed);
        // Single branch: check disabled bit and level threshold
        (state >> Self::DISABLED_BIT) == 0
            && (level as u32) >= ((state & Self::LEVEL_MASK) >> Self::LEVEL_SHIFT)
    }

    pub fn set_level(&self, level: LogLevel) {
        let current = self.packed_state.load(Ordering::Relaxed);
        let new_state = (current & !Self::LEVEL_MASK) | ((level as u32) << Self::LEVEL_SHIFT);
        self.packed_state.store(new_state, Ordering::Relaxed);
    }

    pub fn set_disabled(&self, disabled: bool) {
        if disabled {
            // Set the disabled bit
            self.packed_state.fetch_or(1 << Self::DISABLED_BIT, Ordering::Relaxed);
        } else {
            // Clear the disabled bit
            self.packed_state.fetch_and(!(1 << Self::DISABLED_BIT), Ordering::Relaxed);
        }
    }
}

/// Generic logger that provides uniform performance across all levels
#[pyclass]
pub struct GenericFastLogger {
    state: OptimizedLogState,
    name: String, // Use String for flexibility, optimize later with interning
}

#[pymethods]
impl GenericFastLogger {
    #[new]
    pub fn new(name: String) -> Self {
        Self {
            state: OptimizedLogState::new(LogLevel::Warning),
            name,
        }
    }

    /// Universal logging method - same performance for ALL levels
    fn log(&self, level: u32, msg: &str) {
        let log_level = LogLevel::from_usize(level as usize);
        if self.state.is_enabled_for(log_level) {
            self.emit_log(log_level, msg);
        }
    }

    /// All level-specific methods use identical optimization pattern
    fn debug(&self, msg: &str) {
        if self.state.is_enabled_for(LogLevel::Debug) {
            self.emit_log(LogLevel::Debug, msg);
        }
    }

    fn info(&self, msg: &str) {
        if self.state.is_enabled_for(LogLevel::Info) {
            self.emit_log(LogLevel::Info, msg);
        }
    }

    fn warning(&self, msg: &str) {
        if self.state.is_enabled_for(LogLevel::Warning) {
            self.emit_log(LogLevel::Warning, msg);
        }
    }

    fn error(&self, msg: &str) {
        if self.state.is_enabled_for(LogLevel::Error) {
            self.emit_log(LogLevel::Error, msg);
        }
    }

    fn critical(&self, msg: &str) {
        if self.state.is_enabled_for(LogLevel::Critical) {
            self.emit_log(LogLevel::Critical, msg);
        }
    }

    /// Level checking methods for conditional logging
    fn is_debug_enabled(&self) -> bool { self.state.is_enabled_for(LogLevel::Debug) }
    fn is_info_enabled(&self) -> bool { self.state.is_enabled_for(LogLevel::Info) }
    fn is_warning_enabled(&self) -> bool { self.state.is_enabled_for(LogLevel::Warning) }
    fn is_error_enabled(&self) -> bool { self.state.is_enabled_for(LogLevel::Error) }
    fn is_critical_enabled(&self) -> bool { self.state.is_enabled_for(LogLevel::Critical) }

    /// Generic level check
    fn is_enabled_for(&self, level: u32) -> bool {
        self.state.is_enabled_for(LogLevel::from_usize(level as usize))
    }

    /// Configuration methods
    fn set_level(&mut self, level: u32) {
        self.state.set_level(LogLevel::from_usize(level as usize));
    }

    fn set_disabled(&mut self, disabled: bool) {
        self.state.set_disabled(disabled);
    }
}

impl GenericFastLogger {
    fn emit_log(&self, level: LogLevel, msg: &str) {
        use crate::{create_log_record, SENDER, LogMessage};
        let record = create_log_record(
            self.name.clone(),
            level,
            msg.to_string(),
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
    }
}

/// Macro for generating optimized logging calls
macro_rules! log_if_enabled {
    ($logger:expr, $level:ident, $msg:expr) => {
        if $logger.state.is_enabled_for(LogLevel::$level) {
            $logger.emit_log(LogLevel::$level, $msg);
        }
    };
}

/// Function-based API for even faster logging
#[pyfunction]
pub fn fast_log(logger: &GenericFastLogger, level: u32, msg: &str) {
    logger.log(level, msg);
}

/// Specialized functions for each level (can be inlined by compiler)
#[pyfunction]
pub fn fast_debug(logger: &GenericFastLogger, msg: &str) {
    if logger.state.is_enabled_for(LogLevel::Debug) {
        logger.emit_log(LogLevel::Debug, msg);
    }
}

#[pyfunction]
pub fn fast_info(logger: &GenericFastLogger, msg: &str) {
    if logger.state.is_enabled_for(LogLevel::Info) {
        logger.emit_log(LogLevel::Info, msg);
    }
}

#[pyfunction]
pub fn fast_warning(logger: &GenericFastLogger, msg: &str) {
    if logger.state.is_enabled_for(LogLevel::Warning) {
        logger.emit_log(LogLevel::Warning, msg);
    }
}

#[pyfunction]
pub fn fast_error(logger: &GenericFastLogger, msg: &str) {
    if logger.state.is_enabled_for(LogLevel::Error) {
        logger.emit_log(LogLevel::Error, msg);
    }
}

#[pyfunction]
pub fn fast_critical(logger: &GenericFastLogger, msg: &str) {
    if logger.state.is_enabled_for(LogLevel::Critical) {
        logger.emit_log(LogLevel::Critical, msg);
    }
}

/// Batch operations for multiple log levels
#[pyfunction]
pub fn bulk_check_levels(logger: &GenericFastLogger, levels: Vec<u32>) -> Vec<bool> {
    let state = logger.state.packed_state.load(Ordering::Relaxed);

    // Early return if logger is disabled
    if (state >> OptimizedLogState::DISABLED_BIT) == 1 {
        return vec![false; levels.len()];
    }

    let current_level = (state & OptimizedLogState::LEVEL_MASK) >> OptimizedLogState::LEVEL_SHIFT;
    levels.into_iter()
          .map(|level| level >= current_level)
          .collect()
}

/// Zero-allocation string interning for logger names
use std::collections::HashMap;
use once_cell::sync::Lazy;
use std::sync::Mutex;

static NAME_INTERNER: Lazy<Mutex<HashMap<String, &'static str>>> =
    Lazy::new(|| Mutex::new(HashMap::new()));

pub fn intern_name(name: String) -> &'static str {
    let mut interner = NAME_INTERNER.lock().unwrap();
    if let Some(&interned) = interner.get(&name) {
        return interned;
    }

    let leaked: &'static str = Box::leak(name.clone().into_boxed_str());
    interner.insert(name, leaked);
    leaked
}

/// Optimized logger with interned names
#[pyclass]
pub struct InternedFastLogger {
    state: OptimizedLogState,
    name: &'static str,
}

#[pymethods]
impl InternedFastLogger {
    #[new]
    pub fn new(name: String) -> Self {
        Self {
            state: OptimizedLogState::new(LogLevel::Warning),
            name: intern_name(name),
        }
    }

    // Same methods as GenericFastLogger but with zero-allocation name handling
    fn debug(&self, msg: &str) {
        if self.state.is_enabled_for(LogLevel::Debug) {
            self.emit_log_interned(LogLevel::Debug, msg);
        }
    }

    fn info(&self, msg: &str) {
        if self.state.is_enabled_for(LogLevel::Info) {
            self.emit_log_interned(LogLevel::Info, msg);
        }
    }

    fn warning(&self, msg: &str) {
        if self.state.is_enabled_for(LogLevel::Warning) {
            self.emit_log_interned(LogLevel::Warning, msg);
        }
    }

    fn error(&self, msg: &str) {
        if self.state.is_enabled_for(LogLevel::Error) {
            self.emit_log_interned(LogLevel::Error, msg);
        }
    }

    fn critical(&self, msg: &str) {
        if self.state.is_enabled_for(LogLevel::Critical) {
            self.emit_log_interned(LogLevel::Critical, msg);
        }
    }
}

impl InternedFastLogger {
    fn emit_log_interned(&self, level: LogLevel, msg: &str) {
        use crate::{create_log_record, SENDER, LogMessage};
        let record = create_log_record(
            self.name.to_string(), // Convert &str to String only when needed
            level,
            msg.to_string(),
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
    }
}
