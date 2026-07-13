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
use std::sync::atomic::{AtomicBool, AtomicU64, AtomicU8, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::Duration;

use crate::core::{LogLevel, LogRecord};
use crate::filter::Filter;
use crate::formatter::{Formatter, NoOpFormatter};

fn default_formatter() -> Arc<dyn Formatter + Send + Sync> {
    Arc::new(NoOpFormatter)
}

thread_local! {
    /// True while the current thread is running the GIL-released (detached) producer
    /// dispatch (§4). In that window a Block send may block indefinitely without risking
    /// a same-GIL-sink deadlock, so it uses a true blocking send() instead of the
    /// Phase-2 bounded send_timeout.
    static BLOCK_CAN_WAIT: std::cell::Cell<bool> = const { std::cell::Cell::new(false) };
}

/// RAII scope marking the current thread as running detached (GIL-released) dispatch.
pub struct BlockWaitGuard;

impl BlockWaitGuard {
    pub fn enter() -> Self {
        BLOCK_CAN_WAIT.with(|c| c.set(true));
        BlockWaitGuard
    }
}

impl Drop for BlockWaitGuard {
    fn drop(&mut self) {
        BLOCK_CAN_WAIT.with(|c| c.set(false));
    }
}

fn block_can_wait() -> bool {
    BLOCK_CAN_WAIT.with(|c| c.get())
}

/// Runtime dispatch decision for a text-sink handler, shared with the Python wrapper via
/// the `_inner` Arc. Native = the Rust handler formats+writes directly (GIL-released fast
/// path). Python = the wrapper's `handle()` runs in Python (custom Formatter / {,$ style /
/// handler-level Python filter fallback).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum DispatchMode {
    Native = 0,
    Python = 1,
}

impl DispatchMode {
    fn from_u8(v: u8) -> Self {
        if v == DispatchMode::Python as u8 {
            DispatchMode::Python
        } else {
            DispatchMode::Native
        }
    }
}

pub trait Handler: Send + Sync {
    fn emit(&self, record: &LogRecord);
    fn flush(&self);
    /// Stop the handler's background worker (if any), draining/joining as appropriate.
    /// Default no-op for synchronous handlers (File/Stream/Rotating/Memory).
    fn shutdown(&self) {}
    /// Current dispatch mode. Defaults to Native; text-sink handlers override with an
    /// AtomicU8-backed flag so the wrapper can flip them to Python for fallback formatting.
    fn dispatch_mode(&self) -> DispatchMode {
        DispatchMode::Native
    }
    /// Set the dispatch mode. Default no-op (HTTP/OTLP/Memory never fall back).
    fn set_dispatch_mode(&self, _mode: DispatchMode) {}
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
    drop_rx: crossbeam_channel::Receiver<String>,
    flush_signal: crossbeam_channel::Sender<()>,
    flush_done: crossbeam_channel::Receiver<()>,
    level: AtomicU8,
    dispatch_mode: AtomicU8,
    overflow: OverflowStrategy,
    flush_timeout: Duration,
    emitted: AtomicU64,
    queue_dropped: AtomicU64,
    formatter: parking_lot::Mutex<Arc<dyn Formatter + Send + Sync>>,
}

impl StreamHandler {
    fn new_with_dest(dest: StreamDestination) -> Self {
        let (tx, rx) = crossbeam_channel::bounded::<String>(8192);
        let drop_rx = rx.clone();
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
            drop_rx,
            flush_signal: flush_tx,
            flush_done: done_rx,
            level: AtomicU8::new(LogLevel::Debug as u8),
            dispatch_mode: AtomicU8::new(DispatchMode::Native as u8),
            overflow: OverflowStrategy::DropNewest,
            flush_timeout: DEFAULT_FLUSH_TIMEOUT,
            emitted: AtomicU64::new(0),
            queue_dropped: AtomicU64::new(0),
            formatter: parking_lot::Mutex::new(default_formatter()),
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
                let _ = writeln!(stdout.lock(), "{msg}");
            }
            StreamDestination::Stderr => {
                let stderr = std::io::stderr();
                let _ = writeln!(stderr.lock(), "{msg}");
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
        *self.formatter.lock() = formatter;
    }

    /// Format a record using the configured formatter, or return the raw message.
    fn format_record(&self, record: &LogRecord) -> String {
        self.formatter.lock().format(record)
    }

    fn enqueue(&self, output: String) {
        match self.overflow {
            OverflowStrategy::DropNewest => {
                if self.sender.try_send(output).is_err() {
                    self.queue_dropped.fetch_add(1, Ordering::Relaxed);
                }
            }
            OverflowStrategy::DropOldest => {
                let mut output = output;
                loop {
                    match self.sender.try_send(output) {
                        Ok(()) => break,
                        Err(crossbeam_channel::TrySendError::Full(returned)) => {
                            if self.drop_rx.try_recv().is_ok() {
                                self.queue_dropped.fetch_add(1, Ordering::Relaxed);
                            }
                            output = returned;
                        }
                        Err(crossbeam_channel::TrySendError::Disconnected(_)) => {
                            self.queue_dropped.fetch_add(1, Ordering::Relaxed);
                            break;
                        }
                    }
                }
            }
            OverflowStrategy::Block => {
                // True blocking send on the detached path (§4); bounded on the attached path.
                if block_can_wait() {
                    if self.sender.send(output).is_err() {
                        self.queue_dropped.fetch_add(1, Ordering::Relaxed);
                    }
                } else if self
                    .sender
                    .send_timeout(output, self.flush_timeout)
                    .is_err()
                {
                    self.queue_dropped.fetch_add(1, Ordering::Relaxed);
                }
            }
        }
    }

    pub fn metrics_snapshot(&self) -> (u64, u64) {
        (
            self.emitted.load(Ordering::Relaxed),
            self.queue_dropped.load(Ordering::Relaxed),
        )
    }
}

impl Handler for StreamHandler {
    fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }
        self.emitted.fetch_add(1, Ordering::Relaxed);
        let output = self.format_record(record);
        self.enqueue(output);
    }

    fn flush(&self) {
        let _ = self.flush_signal.try_send(());
        let _ = self.flush_done.recv_timeout(Duration::from_secs(5));
    }

    fn dispatch_mode(&self) -> DispatchMode {
        DispatchMode::from_u8(self.dispatch_mode.load(Ordering::Relaxed))
    }

    fn set_dispatch_mode(&self, mode: DispatchMode) {
        self.dispatch_mode.store(mode as u8, Ordering::Relaxed);
    }

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock() = formatter;
    }

    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

// ============================================================================
// FileHandler — synchronous direct file write
// ============================================================================

pub struct FileHandler {
    writer: parking_lot::Mutex<BufWriter<File>>,
    level: AtomicU8,
    flush_level: AtomicU8,
    dispatch_mode: AtomicU8,
    formatter: parking_lot::Mutex<Arc<dyn Formatter + Send + Sync>>,
}

impl FileHandler {
    pub fn new<P: AsRef<Path>>(path: P) -> std::io::Result<Self> {
        let f = OpenOptions::new().create(true).append(true).open(path)?;
        Ok(Self {
            writer: parking_lot::Mutex::new(BufWriter::new(f)),
            level: AtomicU8::new(LogLevel::Debug as u8),
            flush_level: AtomicU8::new(LogLevel::Error as u8),
            dispatch_mode: AtomicU8::new(DispatchMode::Native as u8),
            formatter: parking_lot::Mutex::new(default_formatter()),
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
        *self.formatter.lock() = formatter;
    }

    /// Format a record using the configured formatter, or return the raw message.
    fn format_record(&self, record: &LogRecord) -> String {
        self.formatter.lock().format(record)
    }
}

impl Handler for FileHandler {
    fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }
        let output = self.format_record(record);
        let mut w = self.writer.lock();
        if let Err(e) = writeln!(w, "{output}") {
            eprintln!("[LogXide Error] FileHandler write failed: {e}");
        }
        // Level-based flush: flush if record level >= flush_level
        let flush_level = self.flush_level.load(Ordering::Relaxed);
        if record.levelno >= flush_level as i32 {
            let _ = w.flush();
        }
    }

    fn flush(&self) {
        let _ = self.writer.lock().flush();
    }

    fn dispatch_mode(&self) -> DispatchMode {
        DispatchMode::from_u8(self.dispatch_mode.load(Ordering::Relaxed))
    }

    fn set_dispatch_mode(&self, mode: DispatchMode) {
        self.dispatch_mode.store(mode as u8, Ordering::Relaxed);
    }

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock() = formatter;
    }

    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

// ============================================================================
// RotatingFileHandler — synchronous direct file write with rotation
// ============================================================================

pub struct RotatingFileHandler {
    writer: parking_lot::Mutex<BufWriter<File>>,
    filename: PathBuf,
    max_bytes: u64,
    backup_count: u32,
    current_size: std::sync::atomic::AtomicU64,
    level: AtomicU8,
    flush_level: AtomicU8,
    dispatch_mode: AtomicU8,
    formatter: parking_lot::Mutex<Arc<dyn Formatter + Send + Sync>>,
}

impl RotatingFileHandler {
    pub fn new(filename: String, max_bytes: u64, backup_count: u32) -> std::io::Result<Self> {
        let path = PathBuf::from(&filename);

        let initial_size = std::fs::metadata(&path).map(|m| m.len()).unwrap_or(0);

        let file = OpenOptions::new().create(true).append(true).open(&path)?;

        Ok(Self {
            writer: parking_lot::Mutex::new(BufWriter::new(file)),
            filename: path,
            max_bytes,
            backup_count,
            current_size: std::sync::atomic::AtomicU64::new(initial_size),
            level: AtomicU8::new(LogLevel::Debug as u8),
            flush_level: AtomicU8::new(LogLevel::Error as u8),
            dispatch_mode: AtomicU8::new(DispatchMode::Native as u8),
            formatter: parking_lot::Mutex::new(default_formatter()),
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
        *self.formatter.lock() = formatter;
    }

    /// Set an error callback for this handler.
    pub fn set_error_callback(&self, _callback: Option<Arc<dyn Fn(String) + Send + Sync>>) {}

    /// Format a record using the configured formatter, or return the raw message.
    fn format_record(&self, record: &LogRecord) -> String {
        self.formatter.lock().format(record)
    }

    /// Generate backup filename for given index (e.g., app.log.1, app.log.2)
    fn backup_filename(path: &Path, index: u32) -> PathBuf {
        let mut backup = path.to_path_buf();
        let filename = backup
            .file_name()
            .and_then(|s| s.to_str())
            .unwrap_or("app.log");
        backup.set_file_name(format!("{filename}.{index}"));
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
            if let Ok(f) = OpenOptions::new().write(true).truncate(true).open(path) {
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
                eprintln!("[LogXide Error] RotatingFileHandler: failed to create new file: {e}");
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

        let mut w = self.writer.lock();

        // Check rotation
        let cur = self.current_size.load(Ordering::Relaxed);
        if self.max_bytes > 0 && cur + message_bytes > self.max_bytes {
            Self::do_rotation(
                &self.filename,
                self.backup_count,
                &mut w,
                &self.current_size,
            );
        }

        if let Err(e) = writeln!(w, "{output}") {
            eprintln!("[LogXide Error] RotatingFileHandler write failed: {e}");
        } else {
            self.current_size
                .fetch_add(message_bytes, Ordering::Relaxed);
        }

        // Level-based flush
        let flush_level = self.flush_level.load(Ordering::Relaxed);
        if record.levelno >= flush_level as i32 {
            let _ = w.flush();
        }
    }

    fn flush(&self) {
        let _ = self.writer.lock().flush();
    }

    fn dispatch_mode(&self) -> DispatchMode {
        DispatchMode::from_u8(self.dispatch_mode.load(Ordering::Relaxed))
    }

    fn set_dispatch_mode(&self, mode: DispatchMode) {
        self.dispatch_mode.store(mode as u8, Ordering::Relaxed);
    }

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock() = formatter;
    }

    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

// ============================================================================
// HTTPHandler — batch JSON to remote endpoint (already uses channel pattern)
// ============================================================================

pub struct HTTPHandler {
    sender: crossbeam_channel::Sender<LogRecord>,
    drop_rx: crossbeam_channel::Receiver<LogRecord>,
    flush_signal: crossbeam_channel::Sender<()>,
    flush_done: crossbeam_channel::Receiver<()>,
    level: AtomicU8,
    flush_level: AtomicU8,
    shutdown: Arc<AtomicBool>,
    stopped: AtomicBool,
    overflow: OverflowStrategy,
    flush_timeout: Duration,
    join_handle: Mutex<Option<JoinHandle<()>>>,
    emitted: AtomicU64,
    queue_dropped: AtomicU64,
    sink_acknowledged: Arc<AtomicU64>,
    delivery_failed: Arc<AtomicU64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OverflowStrategy {
    DropOldest,
    DropNewest,
    Block,
}

/// Default bound for the flush/shutdown handshake so callers never hang unboundedly.
const DEFAULT_FLUSH_TIMEOUT: Duration = Duration::from_secs(30);

impl OverflowStrategy {
    pub fn from_overflow_str(s: &str) -> Self {
        match s.to_ascii_lowercase().replace(['-', '_'], "").as_str() {
            "dropoldest" => OverflowStrategy::DropOldest,
            "dropnewest" => OverflowStrategy::DropNewest,
            _ => OverflowStrategy::Block,
        }
    }
}

pub struct HTTPHandlerConfig {
    pub url: String,
    pub headers: HashMap<String, String>,
    pub global_context: HashMap<String, Value>,
    pub transform_callback: Option<Py<PyAny>>,
    pub context_provider: Option<Py<PyAny>>,
    pub error_callback: Option<Py<PyAny>>,
    pub overflow: OverflowStrategy,
}

impl HTTPHandler {
    pub fn new(
        url: String,
        headers: HashMap<String, String>,
        capacity: usize,
        batch_size: usize,
        flush_interval: u64,
        overflow: OverflowStrategy,
    ) -> Self {
        Self::with_config(
            HTTPHandlerConfig {
                url,
                headers,
                global_context: HashMap::new(),
                transform_callback: None,
                context_provider: None,
                error_callback: None,
                overflow,
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
        let drop_rx = r.clone();
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

        let sink_acknowledged = Arc::new(AtomicU64::new(0));
        let delivery_failed = Arc::new(AtomicU64::new(0));
        let sink_ack_worker = sink_acknowledged.clone();
        let delivery_failed_worker = delivery_failed.clone();

        let handle = std::thread::spawn(move || {
            let mut buffer = Vec::with_capacity(batch_size);
            let mut last_flush = std::time::Instant::now();

            let send = |buffer: &mut Vec<LogRecord>| {
                Self::send_batch_with_callbacks(
                    &url,
                    &headers,
                    &global_context,
                    &transform_callback,
                    &context_provider,
                    &error_callback,
                    buffer,
                    &sink_ack_worker,
                    &delivery_failed_worker,
                );
            };

            loop {
                if matches!(flush_rx.try_recv(), Ok(())) {
                    // Drain the queue to empty (batching) before signalling done, so a
                    // returning flush() has attempted every record enqueued at signal time.
                    while let Ok(rec) = r.try_recv() {
                        buffer.push(rec);
                        if buffer.len() >= batch_size {
                            send(&mut buffer);
                        }
                    }
                    send(&mut buffer);
                    last_flush = std::time::Instant::now();
                    let _ = done_tx.try_send(());
                }

                if shutdown_clone.load(Ordering::Relaxed) {
                    while let Ok(rec) = r.try_recv() {
                        buffer.push(rec);
                        if buffer.len() >= batch_size {
                            send(&mut buffer);
                        }
                    }
                    send(&mut buffer);
                    let _ = done_tx.try_send(());
                    break;
                }

                match r.recv_timeout(Duration::from_millis(100)) {
                    Ok(rec) => {
                        buffer.push(rec);
                        if buffer.len() >= batch_size {
                            send(&mut buffer);
                            last_flush = std::time::Instant::now();
                        }
                    }
                    Err(crossbeam_channel::RecvTimeoutError::Timeout) => {
                        if !buffer.is_empty() && last_flush.elapsed().as_secs() >= flush_interval {
                            send(&mut buffer);
                            last_flush = std::time::Instant::now();
                        }
                    }
                    Err(crossbeam_channel::RecvTimeoutError::Disconnected) => {
                        while let Ok(rec) = r.try_recv() {
                            buffer.push(rec);
                            if buffer.len() >= batch_size {
                                send(&mut buffer);
                            }
                        }
                        send(&mut buffer);
                        let _ = done_tx.try_send(());
                        break;
                    }
                }
            }
        });

        Self {
            sender: s,
            drop_rx,
            flush_signal: flush_tx,
            flush_done: done_rx,
            level: AtomicU8::new(LogLevel::Debug as u8),
            flush_level: AtomicU8::new(LogLevel::Error as u8),
            shutdown,
            stopped: AtomicBool::new(false),
            overflow: config.overflow,
            flush_timeout: DEFAULT_FLUSH_TIMEOUT,
            join_handle: Mutex::new(Some(handle)),
            emitted: AtomicU64::new(0),
            queue_dropped: AtomicU64::new(0),
            sink_acknowledged,
            delivery_failed,
        }
    }

    /// Enqueue a record honoring the configured overflow strategy, counting drops.
    fn enqueue(&self, record: LogRecord) {
        match self.overflow {
            OverflowStrategy::DropNewest => {
                if self.sender.try_send(record).is_err() {
                    self.queue_dropped.fetch_add(1, Ordering::Relaxed);
                }
            }
            OverflowStrategy::DropOldest => {
                let mut record = record;
                loop {
                    match self.sender.try_send(record) {
                        Ok(()) => break,
                        Err(crossbeam_channel::TrySendError::Full(returned)) => {
                            if self.drop_rx.try_recv().is_ok() {
                                self.queue_dropped.fetch_add(1, Ordering::Relaxed);
                            }
                            record = returned;
                        }
                        Err(crossbeam_channel::TrySendError::Disconnected(_)) => {
                            self.queue_dropped.fetch_add(1, Ordering::Relaxed);
                            break;
                        }
                    }
                }
            }
            OverflowStrategy::Block => {
                if block_can_wait() {
                    // Detached producer path (§4): GIL is released, so a true blocking
                    // send is safe (a same-GIL sink can still make progress) and never
                    // drops — it only errors on channel disconnect.
                    if self.sender.send(record).is_err() {
                        self.queue_dropped.fetch_add(1, Ordering::Relaxed);
                    }
                } else if self
                    .sender
                    .send_timeout(record, self.flush_timeout)
                    .is_err()
                {
                    // Attached path (GIL may be held): bound the wait by flush_timeout so a
                    // stalled same-GIL sink degrades to a counted drop instead of a
                    // deadlock. Fully GIL-safe blocking is the detached branch above.
                    self.queue_dropped.fetch_add(1, Ordering::Relaxed);
                }
            }
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
        sink_acknowledged: &AtomicU64,
        delivery_failed: &AtomicU64,
    ) {
        if buffer.is_empty() {
            return;
        }

        let batch = std::mem::take(buffer);
        let batch_len = batch.len() as u64;

        let json_payload: Value = if transform_callback.is_none() && context_provider.is_none() {
            // FAST PATH (§3): no callbacks => build the payload in pure Rust with NO
            // Python::attach. Byte-identical to the previous no-callback default branch
            // (dynamic_context is empty when context_provider is None).
            let records_with_context: Vec<Value> = batch
                .iter()
                .map(|rec| {
                    let mut rec_map = serde_json::to_value(rec).unwrap_or(Value::Null);
                    if let Value::Object(ref mut obj) = rec_map {
                        for (k, v) in global_context {
                            obj.insert(k.clone(), v.clone());
                        }
                    }
                    rec_map
                })
                .collect();
            Value::Array(records_with_context)
        } else {
            Python::attach(|py| {
                let dynamic_context: HashMap<String, Value> = context_provider
                    .as_ref()
                    .and_then(|cb| {
                        cb.call0(py).ok().and_then(|result| {
                            let dict = result.cast_bound::<PyDict>(py).ok()?;
                            let mut map = HashMap::new();
                            for (k, v) in dict.iter() {
                                if let Ok(key) = k.extract::<String>() {
                                    map.insert(key, crate::py_logger::py_to_json_value(&v));
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
            })
        };

        let mut request = ureq::post(url).set("Content-Type", "application/json");
        for (key, value) in headers {
            request = request.set(key, value);
        }

        match request.send_json(&json_payload) {
            Ok(_) => {
                sink_acknowledged.fetch_add(batch_len, Ordering::Relaxed);
            }
            Err(e) => {
                delivery_failed.fetch_add(batch_len, Ordering::Relaxed);
                if let Some(ref cb) = error_callback {
                    Python::attach(|py| {
                        let _ = cb.call1(py, (e.to_string(),));
                    });
                }
            }
        }
    }

    pub fn flush(&self) {
        let _ = self.flush_signal.try_send(());
        let _ = self.flush_done.recv_timeout(self.flush_timeout);
    }

    pub fn shutdown(&self) {
        if self.stopped.swap(true, Ordering::SeqCst) {
            return;
        }
        self.shutdown.store(true, Ordering::Relaxed);
        let _ = self.flush_signal.try_send(());
        if let Some(handle) = self.join_handle.lock().unwrap().take() {
            let _ = handle.join();
        }
    }

    pub fn metrics_snapshot(&self) -> (u64, u64, u64, u64) {
        (
            self.emitted.load(Ordering::Relaxed),
            self.sink_acknowledged.load(Ordering::Relaxed),
            self.queue_dropped.load(Ordering::Relaxed),
            self.delivery_failed.load(Ordering::Relaxed),
        )
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

impl Handler for HTTPHandler {
    fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }
        self.emitted.fetch_add(1, Ordering::Relaxed);
        self.enqueue(record.clone());

        // Level-based flush: immediately flush if record level >= flush_level
        let flush_level = self.flush_level.load(Ordering::Relaxed);
        if record.levelno >= flush_level as i32 {
            let _ = self.flush_signal.try_send(());
        }
    }

    fn flush(&self) {
        HTTPHandler::flush(self);
    }

    fn shutdown(&self) {
        HTTPHandler::shutdown(self);
    }

    fn set_formatter(&mut self, _: Arc<dyn Formatter + Send + Sync>) {}
    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

impl Drop for HTTPHandler {
    fn drop(&mut self) {
        // Do NOT join here: Drop may run under the GIL (e.g. gc.collect) while the worker
        // needs the GIL for a callback/error path — joining would deadlock. Signalling
        // shutdown and dropping `sender` (which disconnects the channel) still terminates
        // the worker; explicit shutdown()/close() via py.detach performs the join.
        self.shutdown.store(true, Ordering::Relaxed);
        let _ = self.flush_signal.try_send(());
    }
}

// ============================================================================
// OTLPHandler — batch protobuf to OTLP endpoint
// ============================================================================

pub struct OTLPHandler {
    sender: crossbeam_channel::Sender<LogRecord>,
    drop_rx: crossbeam_channel::Receiver<LogRecord>,
    flush_signal: crossbeam_channel::Sender<()>,
    flush_done: crossbeam_channel::Receiver<()>,
    level: AtomicU8,
    shutdown: Arc<AtomicBool>,
    stopped: AtomicBool,
    overflow: OverflowStrategy,
    flush_timeout: Duration,
    join_handle: Mutex<Option<JoinHandle<()>>>,
    emitted: AtomicU64,
    queue_dropped: AtomicU64,
    sink_acknowledged: Arc<AtomicU64>,
    delivery_failed: Arc<AtomicU64>,
}

pub struct OTLPHandlerConfig {
    pub url: String,
    pub headers: HashMap<String, String>,
    pub service_name: String,
    pub error_callback: Option<Py<PyAny>>,
    pub overflow: OverflowStrategy,
}

impl OTLPHandler {
    pub fn new(
        url: String,
        headers: HashMap<String, String>,
        service_name: String,
        capacity: usize,
        batch_size: usize,
        flush_interval: u64,
        overflow: OverflowStrategy,
    ) -> Self {
        Self::with_config(
            OTLPHandlerConfig {
                url,
                headers,
                service_name,
                error_callback: None,
                overflow,
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
        let drop_rx = r.clone();
        let (flush_tx, flush_rx) = crossbeam_channel::bounded::<()>(1);
        let (done_tx, done_rx) = crossbeam_channel::bounded::<()>(1);
        let shutdown = Arc::new(AtomicBool::new(false));
        let shutdown_clone = shutdown.clone();

        let url = config.url;
        let headers = config.headers;
        let service_name = config.service_name;
        let error_callback = config.error_callback;

        let sink_acknowledged = Arc::new(AtomicU64::new(0));
        let delivery_failed = Arc::new(AtomicU64::new(0));
        let sink_ack_worker = sink_acknowledged.clone();
        let delivery_failed_worker = delivery_failed.clone();

        let handle = std::thread::spawn(move || {
            let mut buffer = Vec::with_capacity(batch_size);
            let mut last_flush = std::time::Instant::now();

            let send = |buffer: &mut Vec<LogRecord>| {
                Self::send_otlp_batch(
                    &url,
                    &headers,
                    &service_name,
                    &error_callback,
                    buffer,
                    &sink_ack_worker,
                    &delivery_failed_worker,
                );
            };

            loop {
                if matches!(flush_rx.try_recv(), Ok(())) {
                    while let Ok(rec) = r.try_recv() {
                        buffer.push(rec);
                        if buffer.len() >= batch_size {
                            send(&mut buffer);
                        }
                    }
                    send(&mut buffer);
                    last_flush = std::time::Instant::now();
                    let _ = done_tx.try_send(());
                }

                if shutdown_clone.load(Ordering::Relaxed) {
                    while let Ok(rec) = r.try_recv() {
                        buffer.push(rec);
                        if buffer.len() >= batch_size {
                            send(&mut buffer);
                        }
                    }
                    send(&mut buffer);
                    let _ = done_tx.try_send(());
                    break;
                }

                match r.recv_timeout(Duration::from_millis(100)) {
                    Ok(rec) => {
                        buffer.push(rec);
                        if buffer.len() >= batch_size {
                            send(&mut buffer);
                            last_flush = std::time::Instant::now();
                        }
                    }
                    Err(crossbeam_channel::RecvTimeoutError::Timeout) => {
                        if !buffer.is_empty() && last_flush.elapsed().as_secs() >= flush_interval {
                            send(&mut buffer);
                            last_flush = std::time::Instant::now();
                        }
                    }
                    Err(crossbeam_channel::RecvTimeoutError::Disconnected) => {
                        while let Ok(rec) = r.try_recv() {
                            buffer.push(rec);
                            if buffer.len() >= batch_size {
                                send(&mut buffer);
                            }
                        }
                        send(&mut buffer);
                        let _ = done_tx.try_send(());
                        break;
                    }
                }
            }
        });

        Self {
            sender: s,
            drop_rx,
            flush_signal: flush_tx,
            flush_done: done_rx,
            level: AtomicU8::new(LogLevel::Debug as u8),
            shutdown,
            stopped: AtomicBool::new(false),
            overflow: config.overflow,
            flush_timeout: DEFAULT_FLUSH_TIMEOUT,
            join_handle: Mutex::new(Some(handle)),
            emitted: AtomicU64::new(0),
            queue_dropped: AtomicU64::new(0),
            sink_acknowledged,
            delivery_failed,
        }
    }

    fn enqueue(&self, record: LogRecord) {
        match self.overflow {
            OverflowStrategy::DropNewest => {
                if self.sender.try_send(record).is_err() {
                    self.queue_dropped.fetch_add(1, Ordering::Relaxed);
                }
            }
            OverflowStrategy::DropOldest => {
                let mut record = record;
                loop {
                    match self.sender.try_send(record) {
                        Ok(()) => break,
                        Err(crossbeam_channel::TrySendError::Full(returned)) => {
                            if self.drop_rx.try_recv().is_ok() {
                                self.queue_dropped.fetch_add(1, Ordering::Relaxed);
                            }
                            record = returned;
                        }
                        Err(crossbeam_channel::TrySendError::Disconnected(_)) => {
                            self.queue_dropped.fetch_add(1, Ordering::Relaxed);
                            break;
                        }
                    }
                }
            }
            OverflowStrategy::Block => {
                // See HTTPHandler::enqueue: true blocking send on the detached path (§4),
                // bounded send_timeout on the attached path to avoid same-GIL deadlock.
                if block_can_wait() {
                    if self.sender.send(record).is_err() {
                        self.queue_dropped.fetch_add(1, Ordering::Relaxed);
                    }
                } else if self
                    .sender
                    .send_timeout(record, self.flush_timeout)
                    .is_err()
                {
                    self.queue_dropped.fetch_add(1, Ordering::Relaxed);
                }
            }
        }
    }

    fn send_otlp_batch(
        url: &str,
        headers: &HashMap<String, String>,
        service_name: &str,
        error_callback: &Option<Py<PyAny>>,
        buffer: &mut Vec<LogRecord>,
        sink_acknowledged: &AtomicU64,
        delivery_failed: &AtomicU64,
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
        let batch_len = batch.len() as u64;

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

        match request.send_bytes(&payload) {
            Ok(_) => {
                sink_acknowledged.fetch_add(batch_len, Ordering::Relaxed);
            }
            Err(e) => {
                delivery_failed.fetch_add(batch_len, Ordering::Relaxed);
                if let Some(ref cb) = error_callback {
                    Python::attach(|py| {
                        let _ = cb.call1(py, (e.to_string(),));
                    });
                }
            }
        }
    }

    pub fn flush(&self) {
        let _ = self.flush_signal.try_send(());
        let _ = self.flush_done.recv_timeout(self.flush_timeout);
    }

    pub fn shutdown(&self) {
        if self.stopped.swap(true, Ordering::SeqCst) {
            return;
        }
        self.shutdown.store(true, Ordering::Relaxed);
        let _ = self.flush_signal.try_send(());
        if let Some(handle) = self.join_handle.lock().unwrap().take() {
            let _ = handle.join();
        }
    }

    pub fn metrics_snapshot(&self) -> (u64, u64, u64, u64) {
        (
            self.emitted.load(Ordering::Relaxed),
            self.sink_acknowledged.load(Ordering::Relaxed),
            self.queue_dropped.load(Ordering::Relaxed),
            self.delivery_failed.load(Ordering::Relaxed),
        )
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
        self.emitted.fetch_add(1, Ordering::Relaxed);
        self.enqueue(record.clone());
    }

    fn flush(&self) {
        OTLPHandler::flush(self);
    }

    fn shutdown(&self) {
        OTLPHandler::shutdown(self);
    }

    fn set_formatter(&mut self, _: Arc<dyn Formatter + Send + Sync>) {}
    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

impl Drop for OTLPHandler {
    fn drop(&mut self) {
        // See HTTPHandler::drop — never join under the GIL; signal + channel disconnect
        // terminate the worker, explicit shutdown() (via py.detach) joins.
        self.shutdown.store(true, Ordering::Relaxed);
        let _ = self.flush_signal.try_send(());
    }
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
    records: Arc<parking_lot::Mutex<Vec<LogRecord>>>,
    level: AtomicU8,
    formatter: parking_lot::Mutex<Option<Arc<dyn Formatter + Send + Sync>>>,
}

impl MemoryHandler {
    pub fn new() -> Self {
        Self {
            records: Arc::new(parking_lot::Mutex::new(Vec::new())),
            level: AtomicU8::new(LogLevel::Debug as u8),
            formatter: parking_lot::Mutex::new(None),
        }
    }

    /// Returns all captured log records.
    pub fn get_records(&self) -> Vec<LogRecord> {
        self.records.lock().clone()
    }

    /// Returns all captured log messages as a single newline-separated string.
    /// Uses the formatter if set, otherwise returns raw messages.
    pub fn get_text(&self) -> String {
        let records = self.records.lock();
        let formatter_guard = self.formatter.lock();
        records
            .iter()
            .map(|r| {
                if let Some(ref fmt) = *formatter_guard {
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
            .iter()
            .map(|r| (r.name.clone(), r.levelno, r.get_message()))
            .collect()
    }

    /// Clear all captured records.
    pub fn clear(&self) {
        self.records.lock().clear();
    }

    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
    }

    /// Set a formatter for this handler.
    /// Thread-safe: can be called while the handler is in use.
    pub fn set_formatter_instance(&self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock() = Some(formatter);
    }

    /// Format a record using the configured formatter, or return the raw message.
    #[allow(dead_code)]
    fn format_record(&self, record: &LogRecord) -> String {
        let guard = self.formatter.lock();
        if let Some(ref formatter) = *guard {
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
        self.records.lock().push(record.clone());
    }

    fn flush(&self) {}

    fn set_formatter(&mut self, formatter: Arc<dyn Formatter + Send + Sync>) {
        *self.formatter.lock() = Some(formatter);
    }

    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

impl Default for MemoryHandler {
    fn default() -> Self {
        Self::new()
    }
}
