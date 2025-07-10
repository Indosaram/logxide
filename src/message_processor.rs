use crate::core::LogRecord;
use crate::handler::Handler;
use once_cell::sync::Lazy;
use std::sync::{Arc, Mutex};
use tokio::runtime::{Builder, Runtime};
use tokio::sync::mpsc::{self, Receiver, Sender};
use tracing::info;

// Global Tokio runtime for async logging
pub static RUNTIME: Lazy<Runtime> = Lazy::new(|| {
    Builder::new_multi_thread()
        .enable_all()
        .build()
        .expect("Failed to create Tokio runtime")
});

// Global sender for log records
pub static SENDER: Lazy<Sender<LogRecord>> = Lazy::new(|| {
    let (sender, mut receiver): (Sender<LogRecord>, Receiver<LogRecord>) = mpsc::channel(1024);

    // Spawn the background task for processing log records
    RUNTIME.spawn(async move {
        while let Some(record) = receiver.recv().await {
            // Dispatch to all registered handlers
            for handler in HANDLERS.lock().unwrap().iter() {
                let handler = handler.clone();
                let record = record.clone();
                // Spawn each handler emit as a task (optional: for concurrency)
                RUNTIME.spawn(async move {
                    handler.emit(&record).await;
                });
            }
            info!("Async processed log record: {:?}", record);
        }
    });

    sender
});

// Global registry of handlers
pub static HANDLERS: Lazy<Mutex<Vec<Arc<dyn Handler + Send + Sync>>>> =
    Lazy::new(|| Mutex::new(Vec::new()));

// Add a handler to the global registry
pub fn add_handler(handler: Arc<dyn Handler + Send + Sync>) {
    HANDLERS.lock().unwrap().push(handler);
}

// Async dispatch API for log records
pub fn dispatch_log_record(record: LogRecord) {
    let _ = SENDER.try_send(record);
}
