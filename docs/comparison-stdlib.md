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

All benchmarks run on macOS ARM64 (Apple Silicon), Python 3.12, averaged across 3 runs of 10,000 iterations (`benchmark/basic_handlers_benchmark.py`). Format string `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"` for both libraries.

LogXide drops the GIL immediately and delegates formatting and I/O to Rust-native `BufWriter` (file) or crossbeam channels (stream/HTTP), avoiding Python overhead entirely.

### Performance Summary (Python 3.12)

| Handler                    | Python `logging` | LogXide               | Speedup        |
| :------------------------- | ---------------: | --------------------: | :------------- |
| **FileHandler**            |  145,260 Ops/sec | **1,139,874 Ops/sec** | **7.85× faster** |
| **StreamHandler**          |   17,006 Ops/sec |   **955,112 Ops/sec** | **56.16× faster** |
| **RotatingFileHandler**    |   55,579 Ops/sec |   **897,118 Ops/sec** | **16.14× faster** |

### File I/O Scenarios (100,000 iterations, subprocess-isolated stdlib)

Methodology: `benchmark/perf_vs_stdlib.py`, 100K iterations × 3 runs. stdlib runs in a subprocess so LogXide's `logging` module override does not affect it.

| Scenario   | Python `logging` |     LogXide | Speedup       |
| :--------- | ---------------: | ----------: | :------------ |
| simple     |  145,562 Ops/sec | **1,922,911** | **13.21× faster** |
| structured |  144,328 Ops/sec | **1,612,029** | **11.17× faster** |
| with `%s` args | 144,156 Ops/sec |   **976,572** | **6.77× faster** |

### Python 3.14

LogXide is also faster on Python 3.14, though the absolute gap narrows because stdlib's per-iteration overhead is lower under 3.14:

| Handler                 | stdlib (3.14) | LogXide (3.14)        | Speedup       |
| :---------------------- | ------------: | --------------------: | :------------ |
| **FileHandler**         |       170,332 | **1,231,079 Ops/sec** | **7.23× faster** |
| **StreamHandler**       |        12,206 |   **932,489 Ops/sec** | **76.40× faster** |
| **RotatingFileHandler** |        99,296 |   **910,023 Ops/sec** | **9.16× faster** |

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
# notest
from logxide.config import dictConfig
dictConfig(LOGGING_CONFIG)  # Transparently promotes stdlib handlers to LogXide
```

## ⚠️ Compatibility Caveats

LogXide prioritizes performance over full stdlib compatibility. Before adopting, note:

- **Custom Python formatters**: `logging.Formatter` subclasses are not called; format strings are processed natively in Rust
- **Subclassing**: `LogRecord` and `Logger` are Rust types and cannot be subclassed
- **Custom Python handlers**: Accepted via `addHandler()`, but they run alongside the Rust pipeline (events may be processed twice) and do not run on the zero-GIL Rust path
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
