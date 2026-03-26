# Architecture

LogXide delivers high performance through its native Rust implementation, providing Python applications with fast logging while maintaining a familiar API.

## Core Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Python API    │    │   Rust Core      │    │   I/O Output    │
│                 │    │                  │    │                 │
│ ┌─────────────┐ │    │ ┌──────────────┐ │    │ ┌─────────────┐ │
│ │ PyLogger    │ │───▶│ │ LogRecord    │ │───▶│ │ Files       │ │
│ │ Methods     │ │    │ │ Creation     │ │    │ │ Streams     │ │
│ └─────────────┘ │    │ └──────────────┘ │    │ │ HTTP/OTLP   │ │
│                 │    │                  │    │ └─────────────┘ │
│ ┌─────────────┐ │    │ ┌──────────────┐ │    │                 │
│ │ basicConfig │ │───▶│ │ Direct       │ │    │                 │
│ │ flush()     │ │    │ │ Handler Call │ │    │                 │
│ └─────────────┘ │    │ └──────────────┘ │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Message Processing Flow

1. **Python Call** → LogXide PyLogger methods via PyO3
2. **Record Creation** → Rust `LogRecord` with full metadata (logger name, level, timestamp, thread info)
3. **Handler Dispatch** → Each handler's `emit()` is called (non-blocking for stream/HTTP/OTLP, synchronous for file handlers)
4. **Output** → Formatted messages written to files/streams/HTTP endpoints

## Key Components

### PyO3 Integration (`src/lib.rs`, `src/py_logger.rs`, `src/py_handlers.rs`)
- Python bindings exposing Logger, Handler, and Formatter types
- `addHandler()` accepts only LogXide's Rust native handlers
- Python `logging.Handler` subclasses are explicitly rejected

### Core Types (`src/core.rs`)
- `LogRecord` — Rust struct holding log metadata (name, level, message, timestamp, thread info, extras)
- `Logger` — Core logger with level filtering and handler dispatch
- `LoggerManager` — Hierarchical logger registry with parent-child relationships

### Fast Logger (`src/fast_logger.rs`)
- Lock-free implementation using atomic operations
- Optimized for high-performance scenarios where mutex contention is a concern
- Uses `AtomicU8` for fast level checking

### FastLoggerWrapper (`logxide/fast_logger_wrapper.py`)

Python-side optimization wrapper that intercepts logging calls before they cross the PyO3 boundary:

```
Python call → FastLoggerWrapper.info() → level check (Python) → [skip if disabled]
                                                               → [delegate to Rust if enabled]
```

- **2-5x speedup** for disabled log calls by avoiding:
    - `PyObject` creation for messages
    - `PyTuple`/`PyDict` packaging for args/kwargs
    - PyO3 boundary crossing overhead
- Caches `getEffectiveLevel()` on the Python side and invalidates on `setLevel()`/`addHandler()`/`removeHandler()`
- Transparent delegation: all non-hot-path attributes fall through to the underlying Rust `PyLogger` via `__getattr__`

### Handlers (`src/handler.rs`)

All handlers implement the synchronous `Handler` trait:

```rust
pub trait Handler: Send + Sync {
    fn emit(&self, record: &LogRecord);
    fn flush(&self);
}
```

| Handler | Description | I/O Strategy |
|---------|-------------|-------------|
| `StreamHandler` | stdout/stderr output | crossbeam 채널 + 백그라운드 스레드 (논블로킹) |
| `FileHandler` | File output | 동기 직접 write (`Mutex<BufWriter>`) |
| `RotatingFileHandler` | Auto-rotating files | 동기 직접 write + size-based rotation |
| `HTTPHandler` | HTTP log shipping | crossbeam 채널 + 백그라운드 스레드 (배치) |
| `OTLPHandler` | OpenTelemetry OTLP | crossbeam 채널 + 백그라운드 스레드 (Protobuf) |
| `MemoryHandler` | In-memory capture | 동기 `Vec::push` (`Mutex`) |
| `NullHandler` | Discards all logs | Zero overhead |

### Non-blocking Handlers (Stream/HTTP/OTLP)

`StreamHandler`, `HTTPHandler`, `OTLPHandler` use the channel + background thread pattern:

```
Logger → emit() → crossbeam-channel sender → Background thread → I/O output
```

- `emit()` formats the message and sends it to a bounded `crossbeam-channel` (non-blocking)
- A dedicated background thread performs actual I/O
- HTTP/OTLP handlers additionally batch records before sending

### Synchronous Handlers (File/RotatingFile)

`FileHandler`, `RotatingFileHandler` use direct synchronous writes:

```
Logger → emit() → Mutex<BufWriter<File>> → write + conditional flush
```

- `emit()` acquires a `Mutex` lock and writes directly to `BufWriter`
- Level-based flush: records at `ERROR` or above trigger immediate `flush()`
- Simpler and faster for single-thread-dominant workloads

### Formatters (`src/formatter.rs`)
- `PercentStyle` — `%(name)s` format (default)
- `StrFormatStyle` — `{name}` format
- `StringTemplateStyle` — `$name` / `${name}` format
- Full support for padding, alignment, and date formatting

### Filters (`src/filter.rs`)
- Name-based filtering matching Python's `logging.Filter`
- Hierarchical name matching (e.g., `"myapp"` matches `"myapp.database"`)

### String Cache (`src/string_cache.rs`)
- `Arc<str>`-based interning for logger names and level names
- Reduces allocation overhead for frequently used strings

## Handler Architecture

```
┌─────────────────────┐
│   PyLogger          │
│   (per-logger       │
│    handler list)    │
├─────────────────────┤
│ ┌─────────────────┐ │
│ │ FileHandler     │ │─── Mutex<BufWriter> → 동기 직접 write
│ └─────────────────┘ │
│ ┌─────────────────┐ │
│ │ StreamHandler   │ │─── crossbeam-channel → Background thread → stderr/stdout
│ └─────────────────┘ │
│ ┌─────────────────┐ │
│ │ HTTPHandler     │ │─── crossbeam-channel → Background thread → HTTP batch
│ └─────────────────┘ │
│ ┌─────────────────┐ │
│ │ OTLPHandler     │ │─── crossbeam-channel → Background thread → OTLP Protobuf
│ └─────────────────┘ │
└─────────────────────┘
```

Each logger maintains its own handler list. When `logger.addHandler()` is called with a Rust handler, it is stored in the logger's local handler list. Global handlers configured via `basicConfig()` are also supported.

## Thread Safety

- **Mutex-protected handlers** — `parking_lot::Mutex` for handler state
- **Thread-safe logger registry** — `DashMap` for concurrent logger access
- **Atomic level checks** — `AtomicU8` for fast level filtering without locks
- **OS-level stream writes** — stdout/stderr bypass Python's GIL

## Memory Management

- **Rust ownership** prevents memory leaks
- **`Arc`-based sharing** for handlers and formatters across loggers
- **`BufWriter`** with 64KB buffers reduces syscall overhead for file handlers
- **String interning** via `Arc<str>` for repeated logger/level names

## Comparison with Standard Logging

| Aspect | Python logging | LogXide |
|--------|---------------|---------|
| **Implementation** | Pure Python | Native Rust via PyO3 |
| **Handler calls** | Python method dispatch | Direct Rust function calls |
| **String formatting** | Python string operations | Rust native formatting |
| **Thread safety** | Global lock (`_lock`) | Per-handler mutexes |
| **I/O** | Python file objects | Direct OS I/O (bypasses GIL) |
| **Custom handlers** | Unlimited (Python subclasses) | Rust handlers only |
| **subclassing** | Full support | Not supported |

## Dependencies

| Crate | Purpose |
|-------|---------|
| `pyo3` | Python-Rust bindings |
| `chrono` | Timestamp formatting |
| `regex` | Format string parsing |
| `parking_lot` | Fast mutexes |
| `dashmap` | Concurrent logger map |
| `crossbeam-channel` | Stream/HTTP/OTLP handler channels |
| `ureq` | HTTP requests (HTTPHandler) |
| `serde` / `serde_json` | JSON serialization |
| `prost` / `opentelemetry-proto` | OTLP Protobuf encoding |
