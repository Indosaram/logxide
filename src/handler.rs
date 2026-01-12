//! # Log Handlers

use async_trait::async_trait;

use std::collections::HashMap;
use std::fs::{File, OpenOptions};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU8, Ordering};
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
    level: AtomicU8,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OverflowStrategy {
    DropOldest,
    DropNewest,
    Block,
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
        let (s, r) = crossbeam_channel::bounded(capacity);
        std::thread::spawn(move || {
            let mut buffer = Vec::with_capacity(batch_size);
            let mut last_flush = std::time::Instant::now();
            loop {
                match r.recv_timeout(std::time::Duration::from_millis(100)) {
                    Ok(rec) => {
                        buffer.push(rec);
                        if buffer.len() >= batch_size {
                            Self::send_batch(&url, &headers, &mut buffer);
                            last_flush = std::time::Instant::now();
                        }
                    }
                    Err(crossbeam_channel::RecvTimeoutError::Timeout) => {
                        if !buffer.is_empty() && last_flush.elapsed().as_secs() >= flush_interval {
                            Self::send_batch(&url, &headers, &mut buffer);
                            last_flush = std::time::Instant::now();
                        }
                    }
                    Err(_) => {
                        break;
                    }
                }
            }
        });
        Self {
            sender: s,
            level: AtomicU8::new(LogLevel::Debug as u8),
        }
    }

    fn send_batch(url: &str, headers: &HashMap<String, String>, buffer: &mut Vec<LogRecord>) {
        if buffer.is_empty() {
            return;
        }
        let batch: Vec<LogRecord> = buffer.drain(..).collect();

        let mut request = ureq::post(url).set("Content-Type", "application/json");

        for (key, value) in headers {
            request = request.set(key, value);
        }

        let _ = request.send_json(&batch);
    }

    pub fn set_level(&self, level: LogLevel) {
        self.level.store(level as u8, Ordering::Relaxed);
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
