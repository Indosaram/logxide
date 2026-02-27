//! # Log Handlers

use async_trait::async_trait;

use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde_json::Value;
use std::collections::HashMap;
use std::fs::{File, OpenOptions};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU8, AtomicU64, Ordering};
use std::sync::Arc;
use std::sync::Mutex;

use crate::core::{LogLevel, LogRecord};
use crate::filter::Filter;
use crate::formatter::Formatter;

#[async_trait::async_trait]
pub trait Handler: Send + Sync {
    async fn emit(&self, record: &LogRecord);
    async fn flush(&self);
    #[allow(dead_code)]
    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>);
    #[allow(dead_code)]
    fn add_filter(&mut self, filter: Arc<dyn Filter + Send + Sync>);
}

/// A handler that writes log records to stdout or stderr.
///
/// Supports custom formatters for controlling output format.
pub struct StreamHandler {
    stream: Mutex<StreamDestination>,
    level: AtomicU8,
    formatter: Mutex<Option<Arc<dyn Formatter + Send + Sync>>>,
    error_callback: Mutex<Option<Arc<dyn Fn(String) + Send + Sync>>>,
}

#[derive(Clone, Copy)]
pub enum StreamDestination {
    Stdout,
    Stderr,
}

impl StreamHandler {
    pub fn stdout() -> Self {
        Self {
            stream: Mutex::new(StreamDestination::Stdout),
            level: AtomicU8::new(LogLevel::Debug as u8),
            formatter: Mutex::new(None),
            error_callback: Mutex::new(None),
        }
    }

    pub fn stderr() -> Self {
        Self {
            stream: Mutex::new(StreamDestination::Stderr),
            level: AtomicU8::new(LogLevel::Debug as u8),
            formatter: Mutex::new(None),
            error_callback: Mutex::new(None),
        }
    }

    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
    }

    /// Set an error callback for this handler.
    pub fn set_error_callback(&self, callback: Option<Arc<dyn Fn(String) + Send + Sync>>) {
        *self.error_callback.lock().unwrap() = callback;
    }

    /// Report an error via callback and stderr.
    #[allow(dead_code)]
    fn report_error(&self, msg: String) {
        if let Some(cb) = self.error_callback.lock().unwrap().as_ref() {
            cb(msg.clone());
        }
        eprintln!("[LogXide Error] {}", msg);
    }

    /// Set a formatter for this handler.
    /// Thread-safe: can be called while the handler is in use.
    pub fn set_formatter_instance(&self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock().unwrap() = Some(formatter);
    }

    /// Format a record using the configured formatter, or return the raw message.
    fn format_record(&self, record: &LogRecord) -> String {
        if let Some(ref formatter) = *self.formatter.lock().unwrap() {
            formatter.format(record)
        } else {
            record.msg.clone()
        }
    }
}

#[async_trait]
impl Handler for StreamHandler {
    async fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }
        let output = self.format_record(record);
        let dest = *self.stream.lock().unwrap();
        match dest {
            StreamDestination::Stdout => println!("{}", output),
            StreamDestination::Stderr => eprintln!("{}", output),
        }
    }

    async fn flush(&self) {}

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock().unwrap() = Some(formatter);
    }

    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

/// A handler that writes log records to a file.
///
/// Supports custom formatters for controlling output format.
pub struct FileHandler {
    writer: Mutex<BufWriter<File>>,
    level: AtomicU8,
    flush_level: AtomicU8,
    formatter: Mutex<Option<Arc<dyn Formatter + Send + Sync>>>,
    error_callback: Mutex<Option<Arc<dyn Fn(String) + Send + Sync>>>,
}

impl FileHandler {
    pub fn new<P: AsRef<Path>>(path: P) -> std::io::Result<Self> {
        let f = OpenOptions::new().create(true).append(true).open(path)?;
        Ok(Self {
            writer: Mutex::new(BufWriter::new(f)),
            level: AtomicU8::new(LogLevel::Debug as u8),
            flush_level: AtomicU8::new(LogLevel::Error as u8),
            formatter: Mutex::new(None),
            error_callback: Mutex::new(None),
        })
    }

    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
    }

    /// Set the flush level. Records at or above this level trigger immediate flush.
    /// Default is ERROR (40).
    pub fn set_flush_level(&self, level: LogLevel) {
        self.flush_level.store(level as u8, Ordering::Relaxed);
    }

    /// Get the current flush level.
    pub fn get_flush_level(&self) -> u8 {
        self.flush_level.load(Ordering::Relaxed)
    }

    /// Set an error callback for this handler.
    pub fn set_error_callback(&self, callback: Option<Arc<dyn Fn(String) + Send + Sync>>) {
        *self.error_callback.lock().unwrap() = callback;
    }

    /// Report an error via callback and stderr.
    fn report_error(&self, msg: String) {
        if let Some(cb) = self.error_callback.lock().unwrap().as_ref() {
            cb(msg.clone());
        }
        eprintln!("[LogXide Error] {}", msg);
    }

    /// Set a formatter for this handler.
    /// Thread-safe: can be called while the handler is in use.
    pub fn set_formatter_instance(&self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock().unwrap() = Some(formatter);
    }

    /// Format a record using the configured formatter, or return the raw message.
    fn format_record(&self, record: &LogRecord) -> String {
        if let Some(ref formatter) = *self.formatter.lock().unwrap() {
            formatter.format(record)
        } else {
            record.msg.clone()
        }
    }
}

#[async_trait]
impl Handler for FileHandler {
    async fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }
        let output = self.format_record(record);
        let mut w = self.writer.lock().unwrap();
        if let Err(e) = writeln!(w, "{}", output) {
            self.report_error(format!("FileHandler write failed: {}", e));
        }
        
        // Level-based flush: only flush if record level >= flush_level
        let flush_level = self.flush_level.load(Ordering::Relaxed);
        if record.levelno >= flush_level as i32 {
            if let Err(e) = w.flush() {
                self.report_error(format!("FileHandler flush failed: {}", e));
            }
        }
    }

    async fn flush(&self) {
        // Manual flush always executes regardless of flush_level
        if let Err(e) = self.writer.lock().unwrap().flush() {
            self.report_error(format!("FileHandler flush failed: {}", e));
        }
    }

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock().unwrap() = Some(formatter);
    }

    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

/// A handler that writes log records to a file with size-based rotation.
///
/// When the log file exceeds `max_bytes`, it rotates:
/// - app.log -> app.log.1
/// - app.log.1 -> app.log.2
/// - ... up to backup_count
pub struct RotatingFileHandler {
    filename: PathBuf,
    max_bytes: u64,
    backup_count: u32,
    level: AtomicU8,
    flush_level: AtomicU8,
    writer: Mutex<BufWriter<File>>,
    current_size: AtomicU64,
    formatter: Mutex<Option<Arc<dyn Formatter + Send + Sync>>>,
    error_callback: Mutex<Option<Arc<dyn Fn(String) + Send + Sync>>>,
}

impl RotatingFileHandler {
    pub fn new(filename: String, max_bytes: u64, backup_count: u32) -> std::io::Result<Self> {
        let path = PathBuf::from(&filename);
        
        // Get initial file size if exists
        let current_size = std::fs::metadata(&path)
            .map(|m| m.len())
            .unwrap_or(0);
        
        // Open file for appending
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)?;
        
        Ok(Self {
            filename: path,
            max_bytes,
            backup_count,
            level: AtomicU8::new(LogLevel::Debug as u8),
            flush_level: AtomicU8::new(LogLevel::Error as u8),
            writer: Mutex::new(BufWriter::new(file)),
            current_size: AtomicU64::new(current_size),
            formatter: Mutex::new(None),
            error_callback: Mutex::new(None),
        })
    }

    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
    }

    /// Set the flush level. Records at or above this level trigger immediate flush.
    pub fn set_flush_level(&self, level: LogLevel) {
        self.flush_level.store(level as u8, Ordering::Relaxed);
    }

    /// Get the current flush level.
    pub fn get_flush_level(&self) -> u8 {
        self.flush_level.load(Ordering::Relaxed)
    }

    /// Set a formatter for this handler.
    pub fn set_formatter_instance(&self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock().unwrap() = Some(formatter);
    }

    /// Set an error callback for this handler.
    pub fn set_error_callback(&self, callback: Option<Arc<dyn Fn(String) + Send + Sync>>) {
        *self.error_callback.lock().unwrap() = callback;
    }

    /// Report an error via callback and stderr.
    fn report_error(&self, msg: String) {
        if let Some(cb) = self.error_callback.lock().unwrap().as_ref() {
            cb(msg.clone());
        }
        eprintln!("[LogXide Error] {}", msg);
    }

    /// Format a record using the configured formatter, or return the raw message.
    fn format_record(&self, record: &LogRecord) -> String {
        if let Some(ref formatter) = *self.formatter.lock().unwrap() {
            formatter.format(record)
        } else {
            record.msg.clone()
        }
    }

    /// Check if rotation is needed based on current size and message size.
    fn should_rotate(&self, message_bytes: usize) -> bool {
        let current = self.current_size.load(Ordering::Relaxed);
        current + message_bytes as u64 > self.max_bytes && self.max_bytes > 0
    }

    /// Generate backup filename for given index (e.g., app.log.1, app.log.2)
    fn backup_filename(&self, index: u32) -> PathBuf {
        let mut path = self.filename.clone();
        let filename = path.file_name()
            .and_then(|s| s.to_str())
            .unwrap_or("app.log");
        path.set_file_name(format!("{}.{}", filename, index));
        path
    }

    /// Perform rotation while holding the writer lock.
    /// IMPORTANT: This method assumes the caller already holds the writer lock.
    fn do_rotation_locked(&self, writer: &mut BufWriter<File>) {
        // Flush before rotation
        let _ = writer.flush();

        // Handle backup_count=0: just truncate, no backups
        if self.backup_count == 0 {
            if let Ok(f) = OpenOptions::new()
                .write(true)
                .truncate(true)
                .open(&self.filename)
            {
                *writer = BufWriter::new(f);
                self.current_size.store(0, Ordering::Relaxed);
            }
            return;
        }

        // Delete excess backup files (if they exist beyond backup_count)
        for i in self.backup_count..self.backup_count + 10 {
            let path = self.backup_filename(i);
            if path.exists() {
                let _ = std::fs::remove_file(&path);
            } else {
                break;
            }
        }

        // Rotate existing backups: .N -> .N+1 (in reverse order)
        for i in (1..self.backup_count).rev() {
            let src = self.backup_filename(i);
            let dst = self.backup_filename(i + 1);
            if src.exists() {
                let _ = std::fs::rename(&src, &dst);
            }
        }

        // Rename current file to .1
        let _ = std::fs::rename(&self.filename, self.backup_filename(1));

        // Create new file
        match OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(true)
            .open(&self.filename)
        {
            Ok(f) => {
                *writer = BufWriter::new(f);
                self.current_size.store(0, Ordering::Relaxed);
            }
            Err(e) => {
                self.report_error(format!("RotatingFileHandler: failed to create new file: {}", e));
            }
        }
    }
}

#[async_trait]
impl Handler for RotatingFileHandler {
    async fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }

        // Format BEFORE acquiring lock to minimize lock time
        let output = self.format_record(record);
        let message_bytes = output.len() + 1; // +1 for newline

        // Acquire writer lock
        let mut writer = self.writer.lock().unwrap();

        // Double-check rotation (TOCTOU prevention)
        if self.should_rotate(message_bytes) {
            self.do_rotation_locked(&mut writer);
        }

        // Write message
        if let Err(e) = writeln!(writer, "{}", output) {
            self.report_error(format!("RotatingFileHandler write failed: {}", e));
        } else {
            self.current_size.fetch_add(message_bytes as u64, Ordering::Relaxed);
        }

        // Level-based flush
        let flush_level = self.flush_level.load(Ordering::Relaxed);
        if record.levelno >= flush_level as i32 {
            if let Err(e) = writer.flush() {
                self.report_error(format!("RotatingFileHandler flush failed: {}", e));
            }
        }
    }

    async fn flush(&self) {
        if let Err(e) = self.writer.lock().unwrap().flush() {
            self.report_error(format!("RotatingFileHandler flush failed: {}", e));
        }
    }

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock().unwrap() = Some(formatter);
    }

    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

/// HTTP handler that sends log records as JSON to a remote endpoint.
/// Uses internal buffering and batch processing for efficient network I/O.
/// HTTP handler that sends log records as JSON to a remote endpoint.
/// Uses internal buffering and batch processing for efficient network I/O.
///
/// Supports level-based flush: records at or above `flush_level` trigger immediate flush.
pub struct HTTPHandler {
    sender: crossbeam_channel::Sender<LogRecord>,
    flush_signal: crossbeam_channel::Sender<()>,
    level: AtomicU8,
    flush_level: AtomicU8,
    shutdown: Arc<AtomicBool>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OverflowStrategy {
    DropOldest,
    DropNewest,
    Block,
}

pub struct HTTPHandlerConfig {
    pub url: String,
    pub headers: HashMap<String, String>,
    pub global_context: HashMap<String, Value>,
    pub transform_callback: Option<Py<PyAny>>,
    pub context_provider: Option<Py<PyAny>>,
    pub error_callback: Option<Py<PyAny>>,
}

impl HTTPHandler {
    pub fn new(
        url: String,
        headers: HashMap<String, String>,
        capacity: usize,
        batch_size: usize,
        flush_interval: u64,
        _: OverflowStrategy,
    ) -> Self {
        Self::with_config(
            HTTPHandlerConfig {
                url,
                headers,
                global_context: HashMap::new(),
                transform_callback: None,
                context_provider: None,
                error_callback: None,
            },
            capacity,
            batch_size,
            flush_interval,
        )
    }

    pub fn with_config(
        config: HTTPHandlerConfig,
        capacity: usize,
        batch_size: usize,
        flush_interval: u64,
    ) -> Self {
        let (s, r) = crossbeam_channel::bounded(capacity);
        let (flush_tx, flush_rx) = crossbeam_channel::bounded::<()>(1);
        let shutdown = Arc::new(AtomicBool::new(false));
        let shutdown_clone = shutdown.clone();

        let url = config.url;
        let headers = config.headers;
        let global_context = config.global_context;
        let transform_callback = config.transform_callback;
        let context_provider = config.context_provider;
        let error_callback = config.error_callback;

        std::thread::spawn(move || {
            let mut buffer = Vec::with_capacity(batch_size);
            let mut last_flush = std::time::Instant::now();

            loop {
                if shutdown_clone.load(Ordering::Relaxed) && buffer.is_empty() {
                    break;
                }

                let should_flush = match flush_rx.try_recv() {
                    Ok(()) => true,
                    Err(_) => false,
                };

                match r.recv_timeout(std::time::Duration::from_millis(100)) {
                    Ok(rec) => {
                        buffer.push(rec);
                        if buffer.len() >= batch_size || should_flush {
                            Self::send_batch_with_callbacks(
                                &url,
                                &headers,
                                &global_context,
                                &transform_callback,
                                &context_provider,
                                &error_callback,
                                &mut buffer,
                            );
                            last_flush = std::time::Instant::now();
                        }
                    }
                    Err(crossbeam_channel::RecvTimeoutError::Timeout) => {
                        let should_time_flush =
                            !buffer.is_empty() && last_flush.elapsed().as_secs() >= flush_interval;
                        if should_time_flush || should_flush {
                            Self::send_batch_with_callbacks(
                                &url,
                                &headers,
                                &global_context,
                                &transform_callback,
                                &context_provider,
                                &error_callback,
                                &mut buffer,
                            );
                            last_flush = std::time::Instant::now();
                        }
                    }
                    Err(crossbeam_channel::RecvTimeoutError::Disconnected) => {
                        if !buffer.is_empty() {
                            Self::send_batch_with_callbacks(
                                &url,
                                &headers,
                                &global_context,
                                &transform_callback,
                                &context_provider,
                                &error_callback,
                                &mut buffer,
                            );
                        }
                        break;
                    }
                }
            }
        });

        Self {
            sender: s,
            flush_signal: flush_tx,
            level: AtomicU8::new(LogLevel::Debug as u8),
            flush_level: AtomicU8::new(LogLevel::Error as u8),  // Default: ERROR+ triggers immediate flush
            shutdown,
        }
    }

    fn send_batch_with_callbacks(
        url: &str,
        headers: &HashMap<String, String>,
        global_context: &HashMap<String, Value>,
        transform_callback: &Option<Py<PyAny>>,
        context_provider: &Option<Py<PyAny>>,
        error_callback: &Option<Py<PyAny>>,
        buffer: &mut Vec<LogRecord>,
    ) {
        if buffer.is_empty() {
            return;
        }

        let batch = std::mem::take(buffer);

        let json_payload: Value = Python::attach(|py| {
            let dynamic_context: HashMap<String, Value> = context_provider
                .as_ref()
                .and_then(|cb| {
                    cb.call0(py).ok().and_then(|result| {
                        let dict = result.cast_bound::<PyDict>(py).ok()?;
                        let mut map = HashMap::new();
                        for (k, v) in dict.iter() {
                            if let Ok(key) = k.extract::<String>() {
                                map.insert(key, py_to_value(&v));
                            }
                        }
                        Some(map)
                    })
                })
                .unwrap_or_default();

            if let Some(ref cb) = transform_callback {
                let records_list: Vec<Value> = batch
                    .iter()
                    .map(|rec| {
                        let mut rec_map = serde_json::to_value(rec).unwrap_or(Value::Null);
                        if let Value::Object(ref mut obj) = rec_map {
                            for (k, v) in global_context {
                                obj.insert(k.clone(), v.clone());
                            }
                            for (k, v) in &dynamic_context {
                                obj.insert(k.clone(), v.clone());
                            }
                        }
                        rec_map
                    })
                    .collect();

                let py_records = serde_json::to_string(&records_list).ok().and_then(|s| {
                    py.import("json")
                        .ok()
                        .and_then(|json_mod| json_mod.call_method1("loads", (s,)).ok())
                });

                if let Some(py_recs) = py_records {
                    if let Ok(result) = cb.call1(py, (py_recs,)) {
                        if let Ok(json_mod) = py.import("json") {
                            if let Ok(json_str) = json_mod.call_method1("dumps", (result,)) {
                                if let Ok(s) = json_str.extract::<String>() {
                                    if let Ok(v) = serde_json::from_str(&s) {
                                        return v;
                                    }
                                }
                            }
                        }
                    }
                }
            }

            let records_with_context: Vec<Value> = batch
                .iter()
                .map(|rec| {
                    let mut rec_map = serde_json::to_value(rec).unwrap_or(Value::Null);
                    if let Value::Object(ref mut obj) = rec_map {
                        for (k, v) in global_context {
                            obj.insert(k.clone(), v.clone());
                        }
                        for (k, v) in &dynamic_context {
                            obj.insert(k.clone(), v.clone());
                        }
                    }
                    rec_map
                })
                .collect();

            Value::Array(records_with_context)
        });

        let mut request = ureq::post(url).set("Content-Type", "application/json");
        for (key, value) in headers {
            request = request.set(key, value);
        }

        let result = request.send_json(&json_payload);

        if let Err(e) = result {
            if let Some(ref cb) = error_callback {
                Python::attach(|py| {
                    let _ = cb.call1(py, (e.to_string(),));
                });
            }
        }
    }

    pub fn flush(&self) {
        let _ = self.flush_signal.try_send(());
    }

    pub fn shutdown(&self) {
        self.shutdown.store(true, Ordering::Relaxed);
        let _ = self.flush_signal.try_send(());
    }

    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
    }

    /// Set the flush level. Records at or above this level trigger immediate flush.
    /// Default is ERROR (40).
    pub fn set_flush_level(&self, level: LogLevel) {
        self.flush_level.store(level as u8, Ordering::Relaxed);
    }

    /// Get the current flush level.
    pub fn get_flush_level(&self) -> u8 {
        self.flush_level.load(Ordering::Relaxed)
    }
}

fn py_to_value(obj: &Bound<PyAny>) -> Value {
    use pyo3::types::PyList;

    if obj.is_none() {
        Value::Null
    } else if let Ok(b) = obj.extract::<bool>() {
        Value::Bool(b)
    } else if let Ok(i) = obj.extract::<i64>() {
        Value::Number(i.into())
    } else if let Ok(f) = obj.extract::<f64>() {
        serde_json::Number::from_f64(f)
            .map(Value::Number)
            .unwrap_or(Value::Null)
    } else if let Ok(s) = obj.extract::<String>() {
        Value::String(s)
    } else if let Ok(list) = obj.cast::<PyList>() {
        let arr: Vec<Value> = list.iter().map(|item| py_to_value(&item)).collect();
        Value::Array(arr)
    } else if let Ok(dict) = obj.cast::<PyDict>() {
        let mut map = serde_json::Map::new();
        for (k, v) in dict.iter() {
            if let Ok(key) = k.extract::<String>() {
                map.insert(key, py_to_value(&v));
            }
        }
        Value::Object(map)
    } else if let Ok(s) = obj.str() {
        Value::String(s.to_string())
    } else {
        Value::Null
    }
}

#[async_trait]
impl Handler for HTTPHandler {
    async fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }
        let _ = self
            .sender
            .send_timeout(record.clone(), std::time::Duration::from_millis(5));
        
        // Level-based flush: immediately flush if record level >= flush_level
        let flush_level = self.flush_level.load(Ordering::Relaxed);
        if record.levelno >= flush_level as i32 {
            let _ = self.flush_signal.try_send(());
        }
    }
    async fn flush(&self) {}

    fn set_formatter(&mut self, _: Arc<dyn Formatter + Send + Sync>) {}
    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

/// HTTP handler that sends log records as OpenTelemetry OTLP (protobuf) to a remote endpoint.
/// Uses internal buffering and batch processing for efficient network I/O.
/// Compatible with OTLP (OpenTelemetry Protocol) receivers.
pub struct OTLPHandler {
    sender: crossbeam_channel::Sender<LogRecord>,
    flush_signal: crossbeam_channel::Sender<()>,
    level: AtomicU8,
    shutdown: Arc<AtomicBool>,
}

pub struct OTLPHandlerConfig {
    pub url: String,
    pub headers: HashMap<String, String>,
    pub service_name: String,
    pub error_callback: Option<Py<PyAny>>,
}

impl OTLPHandler {
    pub fn new(
        url: String,
        headers: HashMap<String, String>,
        service_name: String,
        capacity: usize,
        batch_size: usize,
        flush_interval: u64,
    ) -> Self {
        Self::with_config(
            OTLPHandlerConfig {
                url,
                headers,
                service_name,
                error_callback: None,
            },
            capacity,
            batch_size,
            flush_interval,
        )
    }

    pub fn with_config(
        config: OTLPHandlerConfig,
        capacity: usize,
        batch_size: usize,
        flush_interval: u64,
    ) -> Self {
        let (s, r) = crossbeam_channel::bounded(capacity);
        let (flush_tx, flush_rx) = crossbeam_channel::bounded::<()>(1);
        let shutdown = Arc::new(AtomicBool::new(false));
        let shutdown_clone = shutdown.clone();

        let url = config.url;
        let headers = config.headers;
        let service_name = config.service_name;
        let error_callback = config.error_callback;

        std::thread::spawn(move || {
            let mut buffer = Vec::with_capacity(batch_size);
            let mut last_flush = std::time::Instant::now();

            loop {
                if shutdown_clone.load(Ordering::Relaxed) && buffer.is_empty() {
                    break;
                }

                let should_flush = matches!(flush_rx.try_recv(), Ok(()));

                match r.recv_timeout(std::time::Duration::from_millis(100)) {
                    Ok(rec) => {
                        buffer.push(rec);
                        if buffer.len() >= batch_size || should_flush {
                            Self::send_otlp_batch(
                                &url,
                                &headers,
                                &service_name,
                                &error_callback,
                                &mut buffer,
                            );
                            last_flush = std::time::Instant::now();
                        }
                    }
                    Err(crossbeam_channel::RecvTimeoutError::Timeout) => {
                        let should_time_flush =
                            !buffer.is_empty() && last_flush.elapsed().as_secs() >= flush_interval;
                        if should_time_flush || should_flush {
                            Self::send_otlp_batch(
                                &url,
                                &headers,
                                &service_name,
                                &error_callback,
                                &mut buffer,
                            );
                            last_flush = std::time::Instant::now();
                        }
                    }
                    Err(crossbeam_channel::RecvTimeoutError::Disconnected) => {
                        if !buffer.is_empty() {
                            Self::send_otlp_batch(
                                &url,
                                &headers,
                                &service_name,
                                &error_callback,
                                &mut buffer,
                            );
                        }
                        break;
                    }
                }
            }
        });

        Self {
            sender: s,
            flush_signal: flush_tx,
            level: AtomicU8::new(LogLevel::Debug as u8),
            shutdown,
        }
    }

    fn send_otlp_batch(
        url: &str,
        headers: &HashMap<String, String>,
        service_name: &str,
        error_callback: &Option<Py<PyAny>>,
        buffer: &mut Vec<LogRecord>,
    ) {
        use opentelemetry_proto::tonic::common::v1::{any_value, AnyValue, KeyValue};
        use opentelemetry_proto::tonic::logs::v1::{
            LogRecord as OtlpLogRecord, ResourceLogs, ScopeLogs,
        };
        use opentelemetry_proto::tonic::resource::v1::Resource;
        use prost::Message;

        if buffer.is_empty() {
            return;
        }

        let batch = std::mem::take(buffer);

        let log_records: Vec<OtlpLogRecord> = batch
            .iter()
            .map(|rec| {
                OtlpLogRecord {
                    time_unix_nano: (rec.created * 1_000_000_000.0) as u64,
                    observed_time_unix_nano: (rec.created * 1_000_000_000.0) as u64,
                    severity_number: match rec.levelno {
                        10 => 5,  // DEBUG
                        20 => 9,  // INFO
                        30 => 13, // WARN
                        40 => 17, // ERROR
                        50 => 21, // FATAL
                        _ => 0,
                    },
                    severity_text: rec.levelname.clone(),
                    body: Some(AnyValue {
                        value: Some(any_value::Value::StringValue(rec.msg.clone())),
                    }),
                    attributes: vec![
                        KeyValue {
                            key: "logger.name".to_string(),
                            value: Some(AnyValue {
                                value: Some(any_value::Value::StringValue(rec.name.clone())),
                            }),
                        },
                        KeyValue {
                            key: "code.filepath".to_string(),
                            value: Some(AnyValue {
                                value: Some(any_value::Value::StringValue(rec.pathname.clone())),
                            }),
                        },
                        KeyValue {
                            key: "code.lineno".to_string(),
                            value: Some(AnyValue {
                                value: Some(any_value::Value::IntValue(rec.lineno as i64)),
                            }),
                        },
                        KeyValue {
                            key: "code.function".to_string(),
                            value: Some(AnyValue {
                                value: Some(any_value::Value::StringValue(rec.func_name.clone())),
                            }),
                        },
                    ],
                    ..Default::default()
                }
            })
            .collect();

        let resource_logs = ResourceLogs {
            resource: Some(Resource {
                attributes: vec![KeyValue {
                    key: "service.name".to_string(),
                    value: Some(AnyValue {
                        value: Some(any_value::Value::StringValue(service_name.to_string())),
                    }),
                }],
                ..Default::default()
            }),
            scope_logs: vec![ScopeLogs {
                log_records,
                ..Default::default()
            }],
            ..Default::default()
        };

        let payload = resource_logs.encode_to_vec();

        let mut request = ureq::post(url).set("Content-Type", "application/x-protobuf");
        for (key, value) in headers {
            request = request.set(key, value);
        }

        let result = request.send_bytes(&payload);

        if let Err(e) = result {
            if let Some(ref cb) = error_callback {
                Python::attach(|py| {
                    let _ = cb.call1(py, (e.to_string(),));
                });
            }
        }
    }

    pub fn flush(&self) {
        let _ = self.flush_signal.try_send(());
    }

    pub fn shutdown(&self) {
        self.shutdown.store(true, Ordering::Relaxed);
        let _ = self.flush_signal.try_send(());
    }

    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
    }
}

#[async_trait]
impl Handler for OTLPHandler {
    async fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }
        let _ = self
            .sender
            .send_timeout(record.clone(), std::time::Duration::from_millis(5));
    }

    async fn flush(&self) {}

    fn set_formatter(&mut self, _: Arc<dyn Formatter + Send + Sync>) {}
    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

/// Handler that stores log records in memory.
/// Highly efficient for testing and log capture.
///
/// Provides pytest-compatible access to captured logs:
/// - `get_records()` - Returns all captured LogRecord objects
/// - `get_text()` - Returns all captured messages as a single string
/// - `get_record_tuples()` - Returns (logger_name, level, message) tuples
///
/// # Examples
///
/// ```rust
/// use logxide::handler::MemoryHandler;
///
/// let handler = MemoryHandler::new();
/// // ... emit some records ...
/// let text = handler.get_text();  // All messages joined
/// let tuples = handler.get_record_tuples();  // [("root", 20, "msg"), ...]
/// ```
pub struct MemoryHandler {
    records: Arc<Mutex<Vec<LogRecord>>>,
    level: AtomicU8,
    formatter: Mutex<Option<Arc<dyn Formatter + Send + Sync>>>,
}

impl MemoryHandler {
    pub fn new() -> Self {
        Self {
            records: Arc::new(Mutex::new(Vec::new())),
            level: AtomicU8::new(LogLevel::Debug as u8),
            formatter: Mutex::new(None),
        }
    }

    /// Returns all captured log records.
    pub fn get_records(&self) -> Vec<LogRecord> {
        self.records.lock().unwrap().clone()
    }

    /// Returns all captured log messages as a single newline-separated string.
    /// Uses the formatter if set, otherwise returns raw messages.
    pub fn get_text(&self) -> String {
        let records = self.records.lock().unwrap();
        let formatter = self.formatter.lock().unwrap();
        records
            .iter()
            .map(|r| {
                if let Some(ref fmt) = *formatter {
                    fmt.format(r)
                } else {
                    r.msg.clone()
                }
            })
            .collect::<Vec<_>>()
            .join("\n")
    }

    /// Returns record tuples in pytest caplog format: (logger_name, level_num, message).
    pub fn get_record_tuples(&self) -> Vec<(String, i32, String)> {
        self.records
            .lock()
            .unwrap()
            .iter()
            .map(|r| (r.name.clone(), r.levelno, r.msg.clone()))
            .collect()
    }

    /// Clear all captured records.
    pub fn clear(&self) {
        self.records.lock().unwrap().clear();
    }

    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
    }

    /// Set a formatter for this handler.
    /// Thread-safe: can be called while the handler is in use.
    pub fn set_formatter_instance(&self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock().unwrap() = Some(formatter);
    }

    /// Format a record using the configured formatter, or return the raw message.
    #[allow(dead_code)]
    fn format_record(&self, record: &LogRecord) -> String {
        if let Some(ref formatter) = *self.formatter.lock().unwrap() {
            formatter.format(record)
        } else {
            record.msg.clone()
        }
    }
}

#[async_trait]
impl Handler for MemoryHandler {
    async fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }
        self.records.lock().unwrap().push(record.clone());
    }

    async fn flush(&self) {}

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock().unwrap() = Some(formatter);
    }

    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

impl Default for MemoryHandler {
    fn default() -> Self {
        Self::new()
    }
}
