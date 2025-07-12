//! String caching and interning for LogXide
//!
//! This module provides efficient string interning for commonly used strings
//! in logging, such as log level names and logger names. By reusing Arc<str>
//! references, we reduce memory allocation and improve cache performance.

use crate::core::LogLevel;
use once_cell::sync::Lazy;
use parking_lot::RwLock;
use std::collections::HashMap;
use std::sync::Arc;

/// String interner with statistics tracking
pub struct StringInterner {
    cache: RwLock<HashMap<String, Arc<str>>>,
    stats: StringInternerStats,
}

#[derive(Default)]
pub struct StringInternerStats {
    hits: std::sync::atomic::AtomicU64,
    misses: std::sync::atomic::AtomicU64,
    memory_saved: std::sync::atomic::AtomicU64,
}

impl StringInterner {
    pub fn new() -> Self {
        Self {
            cache: RwLock::new(HashMap::new()),
            stats: StringInternerStats::default(),
        }
    }

    pub fn intern(&self, s: &str) -> Arc<str> {
        // Fast path: check if already cached
        {
            let cache = self.cache.read();
            if let Some(interned) = cache.get(s) {
                self.stats
                    .hits
                    .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                return interned.clone();
            }
        }

        // Slow path: insert into cache
        let mut cache = self.cache.write();
        match cache.entry(s.to_string()) {
            std::collections::hash_map::Entry::Occupied(entry) => {
                self.stats
                    .hits
                    .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                entry.get().clone()
            }
            std::collections::hash_map::Entry::Vacant(entry) => {
                let interned: Arc<str> = Arc::from(s);
                entry.insert(interned.clone());
                self.stats
                    .misses
                    .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                self.stats
                    .memory_saved
                    .fetch_add(s.len() as u64, std::sync::atomic::Ordering::Relaxed);
                interned
            }
        }
    }

    pub fn get_stats(&self) -> (u64, u64, u64) {
        (
            self.stats.hits.load(std::sync::atomic::Ordering::Relaxed),
            self.stats.misses.load(std::sync::atomic::Ordering::Relaxed),
            self.stats
                .memory_saved
                .load(std::sync::atomic::Ordering::Relaxed),
        )
    }

    pub fn clear(&self) {
        self.cache.write().clear();
    }
}

/// Specialized string cache for logging operations
pub struct LogStringCache {
    level_names: [Arc<str>; 6],
    common_loggers: StringInterner,
    common_messages: StringInterner,
}

impl LogStringCache {
    pub fn new() -> Self {
        Self {
            level_names: [
                Arc::from("NOTSET"),
                Arc::from("DEBUG"),
                Arc::from("INFO"),
                Arc::from("WARNING"),
                Arc::from("ERROR"),
                Arc::from("CRITICAL"),
            ],
            common_loggers: StringInterner::new(),
            common_messages: StringInterner::new(),
        }
    }

    pub fn get_level_name(&self, level: LogLevel) -> Arc<str> {
        match level {
            LogLevel::NotSet => self.level_names[0].clone(),
            LogLevel::Debug => self.level_names[1].clone(),
            LogLevel::Info => self.level_names[2].clone(),
            LogLevel::Warning => self.level_names[3].clone(),
            LogLevel::Error => self.level_names[4].clone(),
            LogLevel::Critical => self.level_names[5].clone(),
        }
    }

    pub fn get_logger_name(&self, name: &str) -> Arc<str> {
        self.common_loggers.intern(name)
    }

    pub fn get_common_message(&self, message: &str) -> Arc<str> {
        if message.len() < 256 && self.is_likely_repeated(message) {
            self.common_messages.intern(message)
        } else {
            Arc::from(message)
        }
    }

    fn is_likely_repeated(&self, message: &str) -> bool {
        // Heuristics for messages likely to be repeated
        message.contains("error")
            || message.contains("warning")
            || message.contains("failed")
            || message.contains("success")
            || message.len() < 50
    }

    pub fn get_stats(&self) -> ((u64, u64, u64), (u64, u64, u64)) {
        (
            self.common_loggers.get_stats(),
            self.common_messages.get_stats(),
        )
    }
}

/// Global string cache instance
static STRING_CACHE: Lazy<LogStringCache> = Lazy::new(|| LogStringCache::new());

pub fn get_level_name(level: LogLevel) -> Arc<str> {
    STRING_CACHE.get_level_name(level)
}

pub fn get_logger_name(name: &str) -> Arc<str> {
    STRING_CACHE.get_logger_name(name)
}

pub fn get_common_message(message: &str) -> Arc<str> {
    STRING_CACHE.get_common_message(message)
}

pub fn get_cache_stats() -> ((u64, u64, u64), (u64, u64, u64)) {
    STRING_CACHE.get_stats()
}
