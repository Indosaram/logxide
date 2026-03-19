//! # Log Handlers
//!
//! StreamHandler, HTTPHandler, OTLPHandler use crossbeam channels + background threads
//! for non-blocking emit(). FileHandler and RotatingFileHandler use synchronous direct writes.

use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde_json::Value;
use std::collections::HashMap;
use std::fs::{File, OpenOptions};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};
use std::sync::Arc;
use std::sync::Mutex;
use std::time::Duration;

use crate::core::{LogLevel, LogRecord};
use crate::filter::Filter;
use crate::formatter::Formatter;

pub trait Handler: Send + Sync {
    fn emit(&self, record: &LogRecord);
    fn flush(&self);
    #[allow(dead_code)]
    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>);
    #[allow(dead_code)]
    fn add_filter(&mut self, filter: Arc<dyn Filter + Send + Sync>);
}

// ============================================================================
// StreamHandler — non-blocking stdout/stderr via background thread
// ============================================================================

#[derive(Clone, Copy)]
pub enum StreamDestination {
    Stdout,
    Stderr,
}

pub struct StreamHandler {
    sender: crossbeam_channel::Sender<String>,
    flush_signal: crossbeam_channel::Sender<()>,
    flush_done: crossbeam_channel::Receiver<()>,
    level: AtomicU8,
    formatter: Mutex<Option<Arc<dyn Formatter + Send + Sync>>>,
}

impl StreamHandler {
    fn new_with_dest(dest: StreamDestination) -> Self {
        let (tx, rx) = crossbeam_channel::bounded::<String>(8192);
        let (flush_tx, flush_rx) = crossbeam_channel::bounded::<()>(1);
        let (done_tx, done_rx) = crossbeam_channel::bounded::<()>(1);

        std::thread::Builder::new()
            .name("logxide-stream".into())
            .spawn(move || {
                loop {
                    // Check for flush signal
                    if flush_rx.try_recv().is_ok() {
                        // Drain all pending messages
                        while let Ok(msg) = rx.try_recv() {
                            Self::write_to_dest(dest, &msg);
                        }
                        let _ = done_tx.try_send(());
                    }

                    match rx.recv_timeout(Duration::from_millis(50)) {
                        Ok(msg) => {
                            Self::write_to_dest(dest, &msg);
                        }
                        Err(crossbeam_channel::RecvTimeoutError::Timeout) => {}
                        Err(crossbeam_channel::RecvTimeoutError::Disconnected) => {
                            // Drain remaining
                            while let Ok(msg) = rx.try_recv() {
                                Self::write_to_dest(dest, &msg);
                            }
                            let _ = done_tx.try_send(());
                            break;
                        }
                    }
                }
            })
            .expect("Failed to spawn stream handler thread");

        Self {
            sender: tx,
            flush_signal: flush_tx,
            flush_done: done_rx,
            level: AtomicU8::new(LogLevel::Debug as u8),
            formatter: Mutex::new(None),
        }
    }

    pub fn stdout() -> Self {
        Self::new_with_dest(StreamDestination::Stdout)
    }

    pub fn stderr() -> Self {
        Self::new_with_dest(StreamDestination::Stderr)
    }

    fn write_to_dest(dest: StreamDestination, msg: &str) {
        match dest {
            StreamDestination::Stdout => {
                let stdout = std::io::stdout();
                let _ = writeln!(stdout.lock(), "{}", msg);
            }
            StreamDestination::Stderr => {
                let stderr = std::io::stderr();
                let _ = writeln!(stderr.lock(), "{}", msg);
            }
        }
    }

    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
    }

    /// Set an error callback for this handler.
    pub fn set_error_callback(&self, _callback: Option<Arc<dyn Fn(String) + Send + Sync>>) {
        // Error callback not needed for stream handler with channel pattern
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
            record.get_message()
        }
    }
}

impl Handler for StreamHandler {
    fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }
        let output = self.format_record(record);
        let _ = self.sender.try_send(output);
    }

    fn flush(&self) {
        let _ = self.flush_signal.try_send(());
        let _ = self.flush_done.recv_timeout(Duration::from_secs(5));
    }

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock().unwrap() = Some(formatter);
    }

    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

// ============================================================================
// FileHandler — synchronous direct file write
// ============================================================================

pub struct FileHandler {
    writer: Mutex<BufWriter<File>>,
    level: AtomicU8,
    flush_level: AtomicU8,
    formatter: Mutex<Option<Arc<dyn Formatter + Send + Sync>>>,
}

impl FileHandler {
    pub fn new<P: AsRef<Path>>(path: P) -> std::io::Result<Self> {
        let f = OpenOptions::new().create(true).append(true).open(path)?;
        Ok(Self {
            writer: Mutex::new(BufWriter::new(f)),
            level: AtomicU8::new(LogLevel::Debug as u8),
            flush_level: AtomicU8::new(LogLevel::Error as u8),
            formatter: Mutex::new(None),
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
    pub fn set_error_callback(&self, _callback: Option<Arc<dyn Fn(String) + Send + Sync>>) {}

    /// Set a formatter for this handler.
    pub fn set_formatter_instance(&self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock().unwrap() = Some(formatter);
    }

    /// Format a record using the configured formatter, or return the raw message.
    fn format_record(&self, record: &LogRecord) -> String {
        if let Some(ref formatter) = *self.formatter.lock().unwrap() {
            formatter.format(record)
        } else {
            record.get_message()
        }
    }
}

impl Handler for FileHandler {
    fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }
        let output = self.format_record(record);
        let mut w = self.writer.lock().unwrap();
        if let Err(e) = writeln!(w, "{}", output) {
            eprintln!("[LogXide Error] FileHandler write failed: {}", e);
        }
        // Level-based flush: flush if record level >= flush_level
        let flush_level = self.flush_level.load(Ordering::Relaxed);
        if record.levelno >= flush_level as i32 {
            let _ = w.flush();
        }
    }

    fn flush(&self) {
        let _ = self.writer.lock().unwrap().flush();
    }

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock().unwrap() = Some(formatter);
    }

    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

// ============================================================================
// RotatingFileHandler — synchronous direct file write with rotation
// ============================================================================

pub struct RotatingFileHandler {
    writer: Mutex<BufWriter<File>>,
    filename: PathBuf,
    max_bytes: u64,
    backup_count: u32,
    current_size: std::sync::atomic::AtomicU64,
    level: AtomicU8,
    flush_level: AtomicU8,
    formatter: Mutex<Option<Arc<dyn Formatter + Send + Sync>>>,
}

impl RotatingFileHandler {
    pub fn new(filename: String, max_bytes: u64, backup_count: u32) -> std::io::Result<Self> {
        let path = PathBuf::from(&filename);

        let initial_size = std::fs::metadata(&path)
            .map(|m| m.len())
            .unwrap_or(0);

        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)?;

        Ok(Self {
            writer: Mutex::new(BufWriter::new(file)),
            filename: path,
            max_bytes,
            backup_count,
            current_size: std::sync::atomic::AtomicU64::new(initial_size),
            level: AtomicU8::new(LogLevel::Debug as u8),
            flush_level: AtomicU8::new(LogLevel::Error as u8),
            formatter: Mutex::new(None),
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
    pub fn set_error_callback(&self, _callback: Option<Arc<dyn Fn(String) + Send + Sync>>) {}

    /// Format a record using the configured formatter, or return the raw message.
    fn format_record(&self, record: &LogRecord) -> String {
        if let Some(ref formatter) = *self.formatter.lock().unwrap() {
            formatter.format(record)
        } else {
            record.get_message()
        }
    }

    /// Generate backup filename for given index (e.g., app.log.1, app.log.2)
    fn backup_filename(path: &Path, index: u32) -> PathBuf {
        let mut backup = path.to_path_buf();
        let filename = backup.file_name()
            .and_then(|s| s.to_str())
            .unwrap_or("app.log");
        backup.set_file_name(format!("{}.{}", filename, index));
        backup
    }

    /// Perform rotation.
    fn do_rotation(
        path: &Path,
        backup_count: u32,
        writer: &mut BufWriter<File>,
        current_size: &std::sync::atomic::AtomicU64,
    ) {
        let _ = writer.flush();

        if backup_count == 0 {
            if let Ok(f) = OpenOptions::new()
                .write(true)
                .truncate(true)
                .open(path)
            {
                *writer = BufWriter::new(f);
                current_size.store(0, Ordering::Relaxed);
            }
            return;
        }

        for i in backup_count..backup_count + 10 {
            let bp = Self::backup_filename(path, i);
            if bp.exists() {
                let _ = std::fs::remove_file(&bp);
            } else {
                break;
            }
        }

        for i in (1..backup_count).rev() {
            let src = Self::backup_filename(path, i);
            let dst = Self::backup_filename(path, i + 1);
            if src.exists() {
                let _ = std::fs::rename(&src, &dst);
            }
        }

        let _ = std::fs::rename(path, Self::backup_filename(path, 1));

        match OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(true)
            .open(path)
        {
            Ok(f) => {
                *writer = BufWriter::new(f);
                current_size.store(0, Ordering::Relaxed);
            }
            Err(e) => {
                eprintln!("[LogXide Error] RotatingFileHandler: failed to create new file: {}", e);
            }
        }
    }
}

impl Handler for RotatingFileHandler {
    fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }

        let output = self.format_record(record);
        let message_bytes = output.len() as u64 + 1;

        let mut w = self.writer.lock().unwrap();

        // Check rotation
        let cur = self.current_size.load(Ordering::Relaxed);
        if self.max_bytes > 0 && cur + message_bytes > self.max_bytes {
            Self::do_rotation(&self.filename, self.backup_count, &mut w, &self.current_size);
        }

        if let Err(e) = writeln!(w, "{}", output) {
            eprintln!("[LogXide Error] RotatingFileHandler write failed: {}", e);
        } else {
            self.current_size.fetch_add(message_bytes, Ordering::Relaxed);
        }

        // Level-based flush
        let flush_level = self.flush_level.load(Ordering::Relaxed);
        if record.levelno >= flush_level as i32 {
            let _ = w.flush();
        }
    }

    fn flush(&self) {
        let _ = self.writer.lock().unwrap().flush();
    }

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock().unwrap() = Some(formatter);
    }

    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

// ============================================================================
// HTTPHandler — batch JSON to remote endpoint (already uses channel pattern)
// ============================================================================

pub struct HTTPHandler {
    sender: crossbeam_channel::Sender<LogRecord>,
    flush_signal: crossbeam_channel::Sender<()>,
    flush_done: crossbeam_channel::Receiver<()>,
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
        let (done_tx, done_rx) = crossbeam_channel::bounded::<()>(1);
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

                match r.recv_timeout(Duration::from_millis(100)) {
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
                            if should_flush {
                                let _ = done_tx.try_send(());
                            }
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
                            if should_flush {
                                let _ = done_tx.try_send(());
                            }
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
                        let _ = done_tx.try_send(());
                        break;
                    }
                }
            }
        });

        Self {
            sender: s,
            flush_signal: flush_tx,
            flush_done: done_rx,
            level: AtomicU8::new(LogLevel::Debug as u8),
            flush_level: AtomicU8::new(LogLevel::Error as u8),
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
        let _ = self.flush_done.recv_timeout(Duration::from_secs(5));
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

impl Handler for HTTPHandler {
    fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }
        let _ = self
            .sender
            .send_timeout(record.clone(), Duration::from_millis(5));

        // Level-based flush: immediately flush if record level >= flush_level
        let flush_level = self.flush_level.load(Ordering::Relaxed);
        if record.levelno >= flush_level as i32 {
            let _ = self.flush_signal.try_send(());
        }
    }

    fn flush(&self) {
        let _ = self.flush_signal.try_send(());
        let _ = self.flush_done.recv_timeout(Duration::from_secs(5));
    }

    fn set_formatter(&mut self, _: Arc<dyn Formatter + Send + Sync>) {}
    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

// ============================================================================
// OTLPHandler — batch protobuf to OTLP endpoint
// ============================================================================

pub struct OTLPHandler {
    sender: crossbeam_channel::Sender<LogRecord>,
    flush_signal: crossbeam_channel::Sender<()>,
    flush_done: crossbeam_channel::Receiver<()>,
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
        let (done_tx, done_rx) = crossbeam_channel::bounded::<()>(1);
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

                match r.recv_timeout(Duration::from_millis(100)) {
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
                            if should_flush {
                                let _ = done_tx.try_send(());
                            }
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
                            if should_flush {
                                let _ = done_tx.try_send(());
                            }
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
                        let _ = done_tx.try_send(());
                        break;
                    }
                }
            }
        });

        Self {
            sender: s,
            flush_signal: flush_tx,
            flush_done: done_rx,
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
        let _ = self.flush_done.recv_timeout(Duration::from_secs(5));
    }

    pub fn shutdown(&self) {
        self.shutdown.store(true, Ordering::Relaxed);
        let _ = self.flush_signal.try_send(());
    }

    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
    }
}

impl Handler for OTLPHandler {
    fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }
        let _ = self
            .sender
            .send_timeout(record.clone(), Duration::from_millis(5));
    }

    fn flush(&self) {
        let _ = self.flush_signal.try_send(());
        let _ = self.flush_done.recv_timeout(Duration::from_secs(5));
    }

    fn set_formatter(&mut self, _: Arc<dyn Formatter + Send + Sync>) {}
    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

// ============================================================================
// MemoryHandler — in-memory log capture (synchronous, no channel needed)
// ============================================================================

/// Handler that stores log records in memory.
/// Highly efficient for testing and log capture.
///
/// Provides pytest-compatible access to captured logs:
/// - `get_records()` - Returns all captured LogRecord objects
/// - `get_text()` - Returns all captured messages as a single string
/// - `get_record_tuples()` - Returns (logger_name, level, message) tuples
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
                    let mut s = format!("{} {} {}\n", r.name, r.levelname, r.get_message());
                    if let Some(ref exc_text) = r.exc_text {
                        s.push_str(exc_text);
                    }
                    s
                }
            })
            .collect::<Vec<_>>()
            .join("")
    }

    /// Returns record tuples in pytest caplog format: (logger_name, level_num, message).
    pub fn get_record_tuples(&self) -> Vec<(String, i32, String)> {
        self.records
            .lock()
            .unwrap()
            .iter()
            .map(|r| (r.name.clone(), r.levelno, r.get_message()))
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
            record.get_message()
        }
    }
}

impl Handler for MemoryHandler {
    fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }
        self.records.lock().unwrap().push(record.clone());
    }

    fn flush(&self) {}

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
