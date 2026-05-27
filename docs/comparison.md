# LogXide vs Loguru: Detailed Comparison

This page provides a detailed deep-dive comparing LogXide to Loguru. For a high-level compatibility overview, see the [Compatibility Overview](compatibility.md).

Both LogXide and Loguru aim to improve upon Python's standard `logging` module, but they take fundamentally different approaches. This document provides a comprehensive comparison.

## Architecture

| | LogXide | Loguru |
|---|---|---|
| **Implementation** | Rust native core via PyO3 | Pure Python |
| **GIL Strategy** | Zero-GIL — drops the GIL immediately, all formatting and I/O happens in Rust | Holds GIL throughout the entire logging pipeline |
| **Thread Safety** | Rust `RwLock` + `Arc` (lock-free reads) | Python `threading.Lock` |
| **Log Record** | Rust `Arc<LogRecord>` — never creates a Python object | Python dict/object per log call |
| **I/O Model** | Direct Rust `BufWriter` syscalls (File), crossbeam channels (HTTP/OTLP) | Python file I/O with internal buffering |

---

## Performance: Handler-by-Handler Benchmark

All benchmarks run on macOS ARM64 (Apple Silicon), Python 3.12 / 3.14, averaged across 3 runs.
Handler-by-handler benchmarks use 10,000 iterations (`basic_handlers_benchmark.py`); File I/O scenario benchmarks (Simple / Structured / Error Logging) use 100,000 iterations (`compare_loggers.py`).

LogXide drops the GIL immediately and delegates formatting and I/O to Rust-native `BufWriter` (file) or crossbeam channels (stream/HTTP), avoiding Python overhead entirely.

### Performance Summary

| Handler Type | Python `logging` | Loguru | LogXide | LogXide vs stdlib | LogXide vs Loguru |
|--------------|------------------|--------|---------|-------------------|-------------------|
| **FileHandler** | 153,356 Ops/sec | 140,912 Ops/sec | **281,741 Ops/sec** | **1.8x faster** | **2.0x faster** |
| **StreamHandler** | 8,009 Ops/sec | 5,447 Ops/sec | **48,488 Ops/sec** | **6.0x faster** | **8.9x faster** |
| **RotatingFileHandler** | 65,438 Ops/sec | **117,720 Ops/sec** | 105,844 Ops/sec | **1.6x faster** | 10% slower |
| **TimedRotatingFileHandler** | 52,140 Ops/sec | ⚠️ (via `rotation=` param) | **98,210 Ops/sec** | **1.8x faster** | N/A |
| **Simple Logging** ¹ | 153,356 Ops/sec | 140,912 Ops/sec | **281,741 Ops/sec** | **1.8x faster** | **2.0x faster** |
| **Structured Logging** | N/A | ~133,000 Ops/sec | **266,242 Ops/sec** | N/A | **2.0x faster** |
| **Error Logging** | N/A | ~128,000 Ops/sec | **251,238 Ops/sec** | N/A | **2.0x faster** |

*Test environment: macOS ARM64 (Apple Silicon), Python 3.12 / 3.14*

*¹ Simple Logging uses FileHandler; numbers are identical to the FileHandler row (same test scenario, 100K iterations).*

---

## Feature Comparison Matrix

### Setup & Configuration

| Feature | LogXide | Loguru |
|---------|---------|--------|
| Zero-config (works out of box) | ✅ | ✅ |
| `basicConfig()` | ✅ (stdlib-compatible) | ❌ (uses `logger.add()` instead) |
| `dictConfig()` support | ✅ (`logxide.config.dictConfig`) | ❌ |
| Django/FastAPI framework config | ✅ (dictConfig-compatible) | ⚠️ (requires manual bridge) |
| Single global logger | ❌ (hierarchical loggers) | ✅ (`from loguru import logger`) |
| `getLogger()` hierarchy | ✅ (full dot-notation propagation) | ❌ (single logger, no hierarchy) |

### Handlers & Output

| Feature | LogXide | Loguru |
|---------|---------|--------|
| FileHandler | ✅ (Rust native BufWriter) | ✅ (Python file I/O) |
| StreamHandler | ✅ (Rust crossbeam channel) | ✅ |
| RotatingFileHandler | ✅ (Rust native) | ✅ (built-in `rotation=`) |
| Time-based rotation | ✅ (Rust native, `when="midnight"`) | ✅ (`rotation="1 day"`) |
| Retention policy | ✅ (`backupCount=N`) | ✅ (`retention="7 days"`) |
| Compression | ✅ (`compress=True`, gzip) | ✅ (`compression="gz"`) |
| HTTP batch handler | ✅ (Rust async, background thread) | ❌ (requires custom sink) |
| OTLP/OpenTelemetry | ✅ (native handler) | ❌ (requires custom integration) |
| MemoryHandler (testing) | ✅ (Rust Vec) | ❌ |

### Formatting & Output

| Feature | LogXide | Loguru |
|---------|---------|--------|
| `%`-style formatting | ✅ | ❌ |
| `{}`-style formatting | ✅ | ✅ |
| Color output | ✅ (`ColorFormatter`) | ✅ (built-in) |
| Custom format string | ✅ | ✅ |
| Structured JSON output | ✅ (via HTTPHandler) | ✅ (`serialize=True`) |

### Error Handling

| Feature | LogXide | Loguru |
|---------|---------|--------|
| `exc_info=True` | ✅ | ✅ |
| `logger.exception()` | ✅ | ✅ |
| `@logger.catch` decorator | ❌ | ✅ |
| Colored tracebacks | ❌ | ✅ (built-in) |
| Error callbacks | ✅ (`setErrorCallback`) | ❌ |

### Contextual Logging

| Feature | LogXide | Loguru |
|---------|---------|--------|
| `extra` fields | ✅ | ✅ |
| `bind()` (persistent context) | ❌ | ✅ |
| `contextualize()` (temporary context) | ❌ | ✅ |
| `patch()` (record mutation) | ❌ | ✅ |

### Custom Levels

| Feature | LogXide | Loguru |
|---------|---------|--------|
| Standard levels (DEBUG-CRITICAL) | ✅ | ✅ |
| `TRACE` level | ❌ | ✅ |
| `SUCCESS` level | ❌ | ✅ |
| Custom level creation | ✅ (`addLevelName`) | ✅ (`logger.level()`) |

### Testing & Debugging

| Feature | LogXide | Loguru |
|---------|---------|--------|
| pytest `caplog` compatible | ⚠️ (custom plugin; requires explicit `addHandler(caplog.handler)`) | ⚠️ (requires PropagateHandler hack) |
| MemoryHandler for capture | ✅ | ❌ |
| `record_tuples` property | ✅ | ❌ |

### Ecosystem & Integration

| Feature | LogXide | Loguru |
|---------|---------|--------|
| Sentry integration | ✅ (native) | ⚠️ (via LoggingIntegration bridge) |
| OpenTelemetry export | ✅ (native OTLPHandler) | ❌ |
| 3rd-party log interception | ✅ (`intercept_stdlib()`) | ✅ (`InterceptHandler` recipe) |
| stdlib `logging` compatibility | ⚠️ (API-compatible for common patterns; subclassing/custom formatters unsupported) | ❌ (separate API) |

---

## ⚠️ Compatibility Caveats

LogXide prioritizes performance over full stdlib compatibility. Before adopting, note:

- **Custom Python formatters**: `logging.Formatter` subclasses are not called; format strings are processed natively in Rust
- **Subclassing**: `LogRecord` and `Logger` are Rust types and cannot be subclassed
- **Custom Python handlers**: Accepted via `addHandler()`, but they run alongside the Rust pipeline (events may be processed twice) and do not run on the zero-GIL Rust path
- **pytest `caplog`**: LogXide provides a custom plugin (auto-registered via entry point); requires explicit `logger.addHandler(caplog.handler)` — see [Testing Guide](testing.md)

For the complete compatibility matrix, see [Compatibility](compatibility.md).

---

## When to Use Which

### Choose LogXide when:
- **Performance is critical** — high-throughput services, real-time systems
- **You need stdlib compatibility** — existing `logging.getLogger()` code, Django/FastAPI `dictConfig`
- **You need production observability** — built-in HTTP batching, OTLP export, Sentry integration
- **Multi-threaded workloads** — Zero-GIL gives true parallel logging without contention
- **pytest integration** — native `caplog` support without hacks

### Choose Loguru when:
- **You want the simplest possible API** — single `logger`, no setup required
- **You need log file management** — time-based rotation, retention, compression are built-in
- **Contextual logging is essential** — `bind()`, `contextualize()`, `patch()` are powerful
- **You want `@logger.catch`** — elegant decorator-based exception catching
- **You prefer `{}`-style formatting exclusively** — Loguru was designed around it

---

## Migration Paths

### From Loguru to LogXide

```python
# Loguru
# notest
from loguru import logger
logger.add("app.log", rotation="10 MB")
logger.info("Hello {}", "world")

# LogXide equivalent
from logxide import logging
logging.basicConfig(level=logging.INFO, filename="app.log",
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
logger.info("Hello %s", "world")
```

### From LogXide to Loguru

```python
# LogXide
# notest
from logxide import logging
logger = logging.getLogger(__name__)
logger.info("Request from %s", ip)

# Loguru equivalent
from loguru import logger
logger.info("Request from {}", ip)
```
