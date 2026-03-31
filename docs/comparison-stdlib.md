# LogXide vs Python stdlib `logging`

This page provides a detailed deep-dive comparing LogXide to Python's standard `logging` module. For a high-level compatibility overview, see the [Compatibility Overview](compatibility.md).

LogXide is a **highly compatible, high-performance alternative** to Python's standard `logging` module. For common use cases (`getLogger`, `basicConfig`, `dictConfig`, standard handlers), it provides a familiar API with significant speedups through its Rust native core.

## Architecture

| Aspect | LogXide | stdlib `logging` |
|---|---|---|
| **Implementation** | Rust native core via PyO3 | Pure Python |
| **GIL Strategy** | Zero-GIL (drops immediately) | Holds GIL for entire pipeline |
| **Thread Safety** | Rust `RwLock` (lock-free reads) | Python `RLock` (reentrant) |
| **Log Record** | Rust `Arc<LogRecord>` | Python `LogRecord` object |
| **I/O Model** | Rust `BufWriter` / crossbeam channels | Python file I/O |

---

## Performance: Handler-by-Handler Benchmark

All benchmarks run on macOS ARM64 (Apple Silicon), Python 3.12 / 3.14, averaged across 3 runs.
Handler-by-handler benchmarks use 10,000 iterations (`basic_handlers_benchmark.py`); File I/O scenario benchmarks (Simple / Structured / Error Logging) use 100,000 iterations (`compare_loggers.py`).

LogXide drops the GIL immediately and delegates formatting and I/O to Rust-native `BufWriter` (file) or crossbeam channels (stream/HTTP), avoiding Python overhead entirely.

### Performance Summary

| Handler / Scenario | Python `logging` | LogXide | LogXide vs stdlib |
|--------------------|------------------|---------|-------------------|
| **FileHandler** | 153,356 Ops/sec | **281,741 Ops/sec** | **1.8x faster** |
| **StreamHandler** | 8,009 Ops/sec | **48,488 Ops/sec** | **6.0x faster** |
| **RotatingFileHandler** | 65,438 Ops/sec | **105,844 Ops/sec** | **1.6x faster** |
| **TimedRotatingFileHandler**| 52,140 Ops/sec | **98,210 Ops/sec** | **1.8x faster** |
| **Simple Logging** | 153,356 Ops/sec | **281,741 Ops/sec** | **1.8x faster** |
| **Structured Logging** | N/A | **266,242 Ops/sec** | N/A |
| **Error Logging** | N/A | **251,238 Ops/sec** | N/A |

---

## Feature Comparison Matrix

| Feature | LogXide | stdlib |
|---------|---------|-------|
| `basicConfig()` | ✅ (compatible) | ✅ |
| `dictConfig()` | ✅ (`logxide.config.dictConfig`) | ✅ |
| `getLogger()` hierarchy| ✅ | ✅ |
| FileHandler | ✅ (Rust BufWriter) | ✅ |
| StreamHandler | ✅ (crossbeam channel) | ✅ |
| RotatingFileHandler | ✅ (Rust native) | ✅ |
| TimedRotatingFileHandler| ✅ (Rust native + gzip) | ✅ |
| HTTPHandler | ✅ (async batch) | ⚠️ (blocking) |
| OTLPHandler | ✅ (native) | ❌ |
| Color output | ✅ (`ColorFormatter`) | ❌ |
| Sentry integration | ✅ (native) | ⚠️ (via SentryHandler) |
| 3rd-party interception | ✅ (`intercept_stdlib()`) | N/A |

---

## Migration Paths

For standard use cases, transitioning to LogXide is as simple as changing your imports:

```python
# Before
import logging
logger = logging.getLogger(__name__)

# After — same API for common patterns, drastically faster
from logxide import logging
logger = logging.getLogger(__name__)
```

Django and FastAPI `dictConfig` setups also work transparently:

```python
from logxide.config import dictConfig
dictConfig(LOGGING_CONFIG)  # Transparently promotes stdlib handlers to LogXide
```

## ⚠️ Compatibility Caveats

LogXide prioritizes performance over full stdlib compatibility. Before adopting, note:

- **Custom Python formatters**: `logging.Formatter` subclasses are not called; format strings are processed natively in Rust
- **Subclassing**: `LogRecord` and `Logger` are Rust types and cannot be subclassed
- **Custom Python handlers**: Accepted via `addHandler()` but bypass the Rust performance pipeline
- **pytest `caplog`**: LogXide provides a custom plugin (auto-registered via entry point); requires explicit `logger.addHandler(caplog.handler)` — see [Testing Guide](testing.md)

For the complete compatibility matrix, see [Compatibility](compatibility.md).

### Compatibility Limitations

While LogXide aims to be a highly compatible alternative for the vast majority of application code, it is fundamentally a Rust-native engine, which means there are some edge cases:

**1. Specialized Handlers are Missing**
LogXide implements the core high-performance handlers, plus modern remote handlers. However, legacy stdlib handlers like `SMTPHandler` or `SocketHandler` are not natively implemented.

**2. Monkeypatching Internal Objects**
Because `LogRecord` and `Logger` logic execute in Rust (Zero-GIL), any Python libraries that aggressively monkeypatch `logging.Logger` internals will not work.

**3. Custom Filters relying on Python state**
Standard filtering works, but highly dynamic custom `Filter` objects that traverse the Python call stack deeply might behave differently since the core formatting loop runs outside Python.

---
