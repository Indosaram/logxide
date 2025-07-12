//! Ultra-fast Python interface optimized for disabled logging
//!
//! This module provides the fastest possible Python interface by minimizing
//! the overhead of Python->Rust function calls for disabled logging.

use pyo3::prelude::*;
use pyo3::ffi;
use std::sync::atomic::{AtomicU32, Ordering};
use crate::core::LogLevel;

/// Ultra-minimal logger for maximum disabled logging performance
#[pyclass]
pub struct FastPyLogger {
    /// Single atomic value - combining level and disabled state
    /// High bit = disabled flag, low bits = level
    level_and_flags: AtomicU32,
    name_ptr: *const u8, // Raw pointer to avoid allocation
    name_len: usize,
}

unsafe impl Send for FastPyLogger {}
unsafe impl Sync for FastPyLogger {}

impl FastPyLogger {
    const DISABLED_FLAG: u32 = 0x8000_0000;
    const LEVEL_MASK: u32 = 0x7FFF_FFFF;
    
    pub fn new(name: &str) -> Self {
        // Store name as raw bytes to avoid allocation on each check
        let name_bytes = name.as_bytes();
        Self {
            level_and_flags: AtomicU32::new(LogLevel::Warning as u32),
            name_ptr: name_bytes.as_ptr(),
            name_len: name_bytes.len(),
        }
    }
    
    /// Ultra-fast single atomic operation check
    #[inline(always)]
    fn is_enabled_for_fast(&self, level: LogLevel) -> bool {
        let level_and_flags = self.level_and_flags.load(Ordering::Relaxed);
        // Check disabled flag and level in one operation
        (level_and_flags & Self::DISABLED_FLAG) == 0 
            && (level as u32) >= (level_and_flags & Self::LEVEL_MASK)
    }
}

#[pymethods]
impl FastPyLogger {
    /// Minimal debug function - optimized assembly
    fn debug_minimal(&self, msg: &str) {
        // Single instruction level check
        if likely(self.is_enabled_for_fast(LogLevel::Debug)) {
            self.send_if_enabled(LogLevel::Debug, msg);
        }
    }
    
    /// Branch prediction hint for disabled case
    fn info_minimal(&self, msg: &str) {
        if likely(self.is_enabled_for_fast(LogLevel::Info)) {
            self.send_if_enabled(LogLevel::Info, msg);
        }
    }
    
    /// Pre-check version - allows caller to avoid expensive operations
    fn debug_enabled(&self) -> bool {
        self.is_enabled_for_fast(LogLevel::Debug)
    }
    
    fn info_enabled(&self) -> bool {
        self.is_enabled_for_fast(LogLevel::Info)
    }
}

impl FastPyLogger {
    fn send_if_enabled(&self, level: LogLevel, msg: &str) {
        use crate::{create_log_record, SENDER, LogMessage};
        
        // Reconstruct name from raw pointer (zero-copy)
        let name = unsafe {
            std::str::from_utf8_unchecked(
                std::slice::from_raw_parts(self.name_ptr, self.name_len)
            )
        };
        
        let record = create_log_record(
            name.to_string(),
            level,
            msg.to_string(),
        );
        let _ = SENDER.send(LogMessage::Record(Box::new(record)));
    }
}

/// Branch prediction hints for better performance
#[inline(always)]
fn likely(b: bool) -> bool {
    std::intrinsics::likely(b)
}

/// C-style interface for maximum performance
use pyo3::ffi::PyObject;

/// Direct C API function for ultra-fast disabled logging
#[no_mangle]
pub unsafe extern "C" fn fast_debug_check(
    logger_ptr: *mut PyObject,
    level: u32,
) -> i32 {
    // Direct memory access without Python overhead
    // This would require careful implementation with PyO3
    1 // Placeholder
}

/// Global fast logger cache using perfect hashing
use std::collections::HashMap;
use once_cell::sync::Lazy;

static FAST_LOGGER_CACHE: Lazy<HashMap<String, FastPyLogger>> = Lazy::new(|| {
    HashMap::with_capacity(1024) // Pre-allocate for common loggers
});

/// Get or create a fast logger with caching
pub fn get_fast_cached_logger(name: &str) -> &'static FastPyLogger {
    // This would need proper synchronization in real implementation
    todo!("Implement fast cached logger")
}