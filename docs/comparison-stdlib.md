# LogXide vs Python stdlib `logging`

This page provides a detailed deep-dive comparing LogXide to Python's standard `logging` module. For a high-level compatibility overview, see the [Compatibility Overview](compatibility.md).

LogXide is a **highly compatible, high-performance alternative** to Python's standard `logging` module. For common use cases (`getLogger`, `basicConfig`, `dictConfig`, standard handlers), it provides a familiar API with significant speedups through its Rust native core.

## Architecture

| Aspect | LogXide | stdlib `logging` |
|---|---|---|
| **Implementation** | Rust native core via PyO3 | Pure Python |
| **GIL Strategy** | Releases GIL for Rust dispatch on the fast path; `%`-args & Python handlers/filters hold it | Holds GIL for entire pipeline |
| **Thread Safety** | Rust `RwLock` (lock-free reads) | Python `RLock` (reentrant) |
| **Log Record** | Rust `Arc<LogRecord>` | Python `LogRecord` object |
| **I/O Model** | Rust `BufWriter` / crossbeam channels | Python file I/O |

---

## Performance

LogXide moves formatting and I/O into a Rust core. On the fast path (no Python filter/handler/caller-info) it releases the GIL for the Rust dispatch; `%`-args formatting and any Python handler/filter still hold the GIL. See [Compatibility](compatibility.md#the-gil-and-what-actually-runs-in-rust) for the exact scope.

!!! note "Cross-library numbers are corrected and sink-verified"
    An earlier revision withdrew the per-handler cross-library tables because the old `benchmark/basic_handlers_benchmark.py` was defective (it imported stdlib and LogXide into the same monkey-patched process, counted async drops as delivered, and mislabeled a plain `StreamHandler` as a rotating handler). The harness has since been rebuilt: each library runs in its own subprocess, the sink is verified after flush, and durable throughput is reported separately from producer latency. The corrected numbers below replace the withdrawn ones.

### Durable throughput vs stdlib (corrected, sink-verified)

Measured with `benchmark/basic_handlers_benchmark.py` on macOS M4 Max, CPython 3.14.2, release build, `-n 20000`, subprocess-isolated per library. **Durable** = records the sink confirmed after flush (every row verified at 20,200 / 20,200). Numbers are machine-specific and rounded:

| Sink     | LogXide durable (p50) | stdlib durable (p50)  | LogXide vs stdlib |
| :------- | :-------------------- | :-------------------- | :---------------- |
| FILE     | ~739K rec/s (833 ns)  | 74,605 rec/s (6,167 ns) | **~10×**        |
| STREAM   | ~273K rec/s (917 ns)  | 53,292 rec/s (6,334 ns) | **~5×**         |
| ROTATING | ~202K rec/s (833 ns)  | 42,981 rec/s (8,542 ns) | **~4.7×**       |

The FILE figure varies ~740K–960K rec/s across runs. See [benchmarks.md](benchmarks.md#comparative-benchmark--all-logging-libraries-corrected-sink-verified) for per-library detail and async accounting.

### File I/O Scenarios (100,000 iterations, subprocess-isolated stdlib)

Methodology: `benchmark/perf_vs_stdlib.py`, 100K iterations × 3 runs. stdlib runs in a subprocess so LogXide's `logging` module override does not affect it — the subprocess isolation the audit recommends. `FileHandler` is a **synchronous** Rust handler, so durable throughput equals producer throughput (no async drops). Figures below are machine-specific and cover one format-string scenario:

| Scenario   | Python `logging` |     LogXide | Speedup       |
| :--------- | ---------------: | ----------: | :------------ |
| simple     |  145,562 Ops/sec | **1,922,911** | **13.21× faster** |
| structured |  144,328 Ops/sec | **1,612,029** | **11.17× faster** |
| with `%s` args | 144,156 Ops/sec |   **976,572** | **6.77× faster** |

### Python 3.14

LogXide is also faster on Python 3.14, though the absolute gap narrows because stdlib's per-iteration overhead is lower under 3.14. The corrected vs-stdlib 3.14 file-I/O figures are in [benchmarks.md](benchmarks.md#python-314). The corrected, sink-verified cross-library and async-handler numbers are published above and in [benchmarks.md](benchmarks.md#comparative-benchmark--all-logging-libraries-corrected-sink-verified) (`get_metrics()` reports `emitted`/`sink_acknowledged`/`queue_dropped`/`delivery_failed`/`in_flight`, so async throughput never counts drops).

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
- **Custom Python handlers**: Accepted via `addHandler()`; a foreign Python handler runs once on the Python side, without the fast-path GIL release. Rust-backed handlers are dispatched once and no longer double-emit or leak to unrelated loggers (fixed in 0.2.0)
- **pytest `caplog`**: LogXide provides a custom plugin (auto-registered via entry point); requires explicit `logger.addHandler(caplog.handler)` — see [Testing Guide](testing.md)

For the complete compatibility matrix, see [Compatibility](compatibility.md).

### Compatibility Limitations

While LogXide aims to be a highly compatible alternative for the vast majority of application code, it is fundamentally a Rust-native engine, which means there are some edge cases:

**1. Specialized Handlers are Missing**
LogXide implements the core high-performance handlers, plus modern remote handlers. However, legacy stdlib handlers like `SMTPHandler` or `SocketHandler` are not natively implemented.

**2. Monkeypatching Internal Objects**
Because `LogRecord` and `Logger` logic execute in Rust, any Python libraries that aggressively monkeypatch `logging.Logger` internals will not work.

**3. Custom Filters relying on Python state**
Standard filtering works, but highly dynamic custom `Filter` objects that traverse the Python call stack deeply might behave differently since the core formatting loop runs outside Python.

---
