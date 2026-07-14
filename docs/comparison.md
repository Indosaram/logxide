# LogXide vs Loguru: Detailed Comparison

This page provides a detailed deep-dive comparing LogXide to Loguru. For a high-level compatibility overview, see the [Compatibility Overview](compatibility.md).

Both LogXide and Loguru aim to improve upon Python's standard `logging` module, but they take fundamentally different approaches. This document provides a comprehensive comparison.

## Architecture

| | LogXide | Loguru |
|---|---|---|
| **Implementation** | Rust native core via PyO3 | Pure Python |
| **GIL Strategy** | Releases the GIL for Rust dispatch on the fast path (no Python filter/handler/caller-info); `%`-args formatting and Python handlers/filters still hold it | Holds GIL throughout the entire logging pipeline |
| **Thread Safety** | Rust `RwLock` + `Arc` (lock-free reads) | Python `threading.Lock` |
| **Log Record** | Rust `Arc<LogRecord>` — never creates a Python object | Python dict/object per log call |
| **I/O Model** | Direct Rust `BufWriter` syscalls (File), crossbeam channels (HTTP/OTLP) | Python file I/O with internal buffering |

---

## Performance

LogXide is performance-first. As of 0.2.0 its text-sink wrappers (`FileHandler`, `StreamHandler`, `RotatingFileHandler`) emit through the native Rust fast path by default, falling back to the Python path only for custom `Formatter` subclasses, `{`/`$`-style format strings, or handler-level Python filters.

### Corrected, sink-verified throughput vs Loguru

Measured with `benchmark/basic_handlers_benchmark.py` on macOS M4 Max, release build, `-n 20000`, each library in its own subprocess, re-run this session on both CPython 3.12.11 and 3.14.2. **Durable** throughput counts records the sink confirmed after flush (every row verified at 20,200 / 20,200), reported separately from producer latency (p50 shown). Numbers are machine-specific and rounded:

| Sink     | LogXide vs stdlib | Loguru (p50)       |
| :------- | :---------------- | :----------------- |
| FILE     | ~6–11×            | 57,511 rec/s (8,500 ns) |
| STREAM   | ~5× (async, see note)    | 52,508 rec/s (8,459 ns) |
| ROTATING | ~8–14×            | 33,095 rec/s (9,666 ns) |

LogXide leads Loguru by roughly an order of magnitude on every sink here; Loguru trails stdlib on all three. For reference, LogXide is ~6–11× stdlib on file and ~8–14× on rotating, plus ~5× on the async stream sink when it fully drains — comparable on Python 3.12 and 3.14, with that stream figure best-effort under sustained bursts, so confirm delivery with `flush()` and `get_metrics()`. Full cross-library tables and async delivery accounting are in [benchmarks.md](benchmarks.md#comparative-benchmark--all-logging-libraries-corrected-sink-verified).

### Architectural advantages (independent of any single benchmark)

- **Rust core** formats and writes without materializing a Python `LogRecord` on the fast path.
- **Background async I/O**: stream/HTTP/OTLP handlers hand records to a worker thread instead of blocking the caller on the sink; `FileHandler` writes through a Rust `BufWriter` synchronously.
- **Explicit async accounting**: `get_metrics()` reports `emitted`, `sink_acknowledged`, `queue_dropped`, `delivery_failed`, and `in_flight`, so "throughput" always counts records the sink confirmed.

On current CPython GIL builds, expect no linear producer scaling across threads — the fast path shares a handler mutex and sink I/O is serialized. LogXide releases the GIL for Rust dispatch only on the fast path; `%`-args formatting and any Python handler/filter still take the GIL. See [Compatibility](compatibility.md#the-gil-and-what-actually-runs-in-rust) for the exact scope.

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
- **Custom Python handlers**: Accepted via `addHandler()`; a foreign Python handler runs once on the Python side, without the fast-path GIL release. Rust-backed handlers are dispatched once and no longer double-emit or leak to unrelated loggers (fixed in 0.2.0)
- **pytest `caplog`**: LogXide provides a custom plugin (auto-registered via entry point); requires explicit `logger.addHandler(caplog.handler)` — see [Testing Guide](testing.md)

For the complete compatibility matrix, see [Compatibility](compatibility.md).

---

## When to Use Which

### Choose LogXide when:
- **Performance is critical** — high-throughput services, real-time systems
- **You need stdlib compatibility** — existing `logging.getLogger()` code, Django/FastAPI `dictConfig`
- **You need production observability** — built-in HTTP batching, OTLP export, Sentry integration
- **Multi-threaded workloads** — the fast path releases the GIL for Rust dispatch, so no-args/preformatted logging can proceed off the GIL (note: current CPython GIL builds serialize on a shared handler mutex, so throughput does not scale linearly across threads yet)
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
