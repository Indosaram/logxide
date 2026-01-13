//! # Log Handlers

use async_trait::async_trait;

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

pub struct StreamHandler {
    stream: Mutex<StreamDestination>,
    level: AtomicU8,
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
        }
    }
    pub fn stderr() -> Self {
        Self {
            stream: Mutex::new(StreamDestination::Stderr),
            level: AtomicU8::new(LogLevel::Debug as u8),
        }
    }
    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
    }
}
#[async_trait]
impl Handler for StreamHandler {
    async fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }
        let dest = *self.stream.lock().unwrap();
        match dest {
            StreamDestination::Stdout => println!("{}", record.msg),
            StreamDestination::Stderr => eprintln!("{}", record.msg),
        }
    }
    async fn flush(&self) {}
    fn set_formatter(&mut self, _: Arc<dyn Formatter + Send + Sync>) {}
    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

pub struct FileHandler {
    writer: Mutex<BufWriter<File>>,
    level: AtomicU8,
}
impl FileHandler {
    pub fn new<P: AsRef<Path>>(path: P) -> std::io::Result<Self> {
        let f = OpenOptions::new().create(true).append(true).open(path)?;
        Ok(Self {
            writer: Mutex::new(BufWriter::new(f)),
            level: AtomicU8::new(LogLevel::Debug as u8),
        })
    }
    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
    }
}
#[async_trait]
impl Handler for FileHandler {
    async fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }
        let mut w = self.writer.lock().unwrap();
        let _ = writeln!(w, "{}", record.msg);
        let _ = w.flush();
    }
    async fn flush(&self) {
        let _ = self.writer.lock().unwrap().flush();
    }
    fn set_formatter(&mut self, _: Arc<dyn Formatter + Send + Sync>) {}
    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

pub struct RotatingFileHandler {
    filename: PathBuf,
    #[allow(dead_code)] // TODO: implement rotation logic
    max_bytes: u64,
    #[allow(dead_code)] // TODO: implement rotation logic
    backup_count: u32,
    level: AtomicU8,
}
impl RotatingFileHandler {
    pub fn new(filename: String, max_bytes: u64, backup_count: u32) -> Self {
        Self {
            filename: PathBuf::from(filename),
            max_bytes,
            backup_count,
            level: AtomicU8::new(LogLevel::Debug as u8),
        }
    }
    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
    }
}
#[async_trait]
impl Handler for RotatingFileHandler {
    async fn emit(&self, record: &LogRecord) {
        let level = self.level.load(Ordering::Relaxed);
        if record.levelno < level as i32 {
            return;
        }
        if let Ok(f) = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.filename)
        {
            let mut w = BufWriter::new(f);
            let _ = writeln!(w, "{}", record.msg);
        }
    }
    async fn flush(&self) {}
    fn set_formatter(&mut self, _: Arc<dyn Formatter + Send + Sync>) {}
    fn add_filter(&mut self, _: Arc<dyn Filter + Send + Sync>) {}
}

pub struct BufferedHTTPHandler {
    sender: crossbeam_channel::Sender<LogRecord>,
    flush_signal: crossbeam_channel::Sender<()>,
    level: AtomicU8,
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

impl BufferedHTTPHandler {
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

        let batch: Vec<LogRecord> = buffer.drain(..).collect();

        let json_payload: Value = Python::with_gil(|py| {
            let dynamic_context: HashMap<String, Value> = context_provider
                .as_ref()
                .and_then(|cb| {
                    cb.call0(py).ok().and_then(|result| {
                        let dict = result.downcast_bound::<PyDict>(py).ok()?;
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
                Python::with_gil(|py| {
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
    } else if let Ok(list) = obj.downcast::<PyList>() {
        let arr: Vec<Value> = list.iter().map(|item| py_to_value(&item)).collect();
        Value::Array(arr)
    } else if let Ok(dict) = obj.downcast::<PyDict>() {
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
impl Handler for BufferedHTTPHandler {
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
