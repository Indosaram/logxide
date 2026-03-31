# LogXide vs Picologging

This page provides a detailed deep-dive comparing LogXide to Picologging. For a high-level compatibility overview, see the [Compatibility Overview](compatibility.md).

Both LogXide and Picologging pursue the same goal — accelerate Python logging with native code. Picologging uses Cython, while LogXide uses Rust via PyO3.

## Architecture

| Aspect | LogXide | Picologging |
|---|---|---|
| **Implementation** | Rust native core via PyO3 | Cython (C extension) |
| **GIL Strategy** | Zero-GIL (drops immediately) | Holds GIL for entire pipeline |
| **Thread Safety** | Rust `RwLock` + `Arc` | CPython `RLock` |
| **Log Record** | Rust `Arc<LogRecord>` | Cython-optimized `LogRecord` |
| **Python 3.13+** | ✅ (3.14 tested) | ❌ (incompatible) |

> ⚠️ **Picologging does not install or run on Python 3.13 or newer.** Its Cython bindings are fundamentally incompatible with recent CPython API changes.

---

## Performance: Handler-by-Handler Benchmark

All benchmarks run on macOS ARM64 (Apple Silicon), Python 3.12 / 3.14, averaged across 3 runs.
Handler-by-handler benchmarks use 10,000 iterations (`basic_handlers_benchmark.py`); File I/O scenario benchmarks (Simple / Structured / Error Logging) use 100,000 iterations (`compare_loggers.py`).

LogXide drops the GIL immediately and delegates formatting and I/O to Rust-native `BufWriter` (file) or crossbeam channels (stream/HTTP), avoiding Python overhead entirely.

> **Note on Picologging numbers**: Picologging was benchmarked on Python 3.12 (its highest supported version) while LogXide numbers are from Python 3.14. Picologging also skips `sys._getframe()` caller frame extraction that the standard library requires, which synthetically inflates its throughput figures.

### Performance Summary

| Handler / Scenario | Picologging (3.12) ¹ | LogXide (3.14) | LogXide vs Picologging |
|--------------------|----------------------|----------------|------------------------|
| **FileHandler** | 411,327 Ops/sec | **281,741 Ops/sec** | Picologging 1.5x faster ¹ |
| **StreamHandler** | 758,828 Ops/sec | **48,488 Ops/sec** | Picologging 15.6x faster ¹ |
| **RotatingFileHandler** | 132,699 Ops/sec | **105,844 Ops/sec** | Picologging 1.3x faster ¹ |
| **TimedRotatingFileHandler**| N/A | **98,210 Ops/sec** | N/A |
| **Simple Logging** ² | N/A | **281,741 Ops/sec** | N/A |
| **Structured Logging** ² | N/A | **266,242 Ops/sec** | N/A |
| **Error Logging** ² | N/A | **251,238 Ops/sec** | N/A |

¹ *Picologging runs on Python 3.12 only; LogXide on 3.14. Picologging skips caller frame extraction (`sys._getframe`), which inflates throughput. Direct comparison is approximate.*
² *Simple / Structured / Error Logging use `compare_loggers.py` (100K iterations). Picologging is excluded because it lacks the Loguru/structlog-compatible test harness used in that script.*

---

## Feature Comparison Matrix

| Feature | LogXide | Picologging |
|---------|---------|-------------|
| stdlib API compatible | ⚠️ | ✅ |
| Python 3.13+ Support | ✅ | ❌ |
| Python 3.14+ Support | ✅ | ❌ |
| FileHandler | ✅ (Rust BufWriter) | ✅ (Cython) |
| StreamHandler | ✅ (crossbeam channel) | ✅ (Cython) |
| RotatingFileHandler | ✅ (Rust native) | ✅ (Cython) |
| TimedRotatingFileHandler| ✅ (Rust native + gzip) | ❌ |
| HTTPHandler | ✅ (async batch) | ❌ |
| OTLPHandler | ✅ (native) | ❌ |
| Color output | ✅ (`ColorFormatter`) | ❌ |
| Sentry integration | ✅ (native) | ❌ |
| Active maintenance| ✅ | ⚠️ (stale since 2023) |

---

## ⚠️ Compatibility Caveats

LogXide prioritizes performance over full stdlib compatibility. Before adopting, note:

- **Custom Python formatters**: `logging.Formatter` subclasses are not called; format strings are processed natively in Rust
- **Subclassing**: `LogRecord` and `Logger` are Rust types and cannot be subclassed
- **Custom Python handlers**: Accepted via `addHandler()` but bypass the Rust performance pipeline
- **pytest `caplog`**: LogXide provides a custom plugin (auto-registered via entry point); requires explicit `logger.addHandler(caplog.handler)` — see [Testing Guide](testing.md)

For the complete compatibility matrix, see [Compatibility](compatibility.md).

---

## When to Use Which

### Choose LogXide when:
1. **You use Python 3.13+** — Picologging is completely broken on Python 3.13 and newer.
2. **You need a Richer Handler Ecosystem** — LogXide provides asynchronous HTTP batching, OTLP, time-based rotation, and gzip compression out of the box.
3. **You want Active Maintenance** — Picologging's development essentially stopped in 2023.
4. **Detailed format parity is essential** — LogXide performs exact frame introspections that standard `logging` expects.

### Choose Picologging when:
1. **You are stuck on Python 3.12 or older**.
2. **You want absolute maximum throughput at the expense of functionality** — skipping frame extraction makes Picologging synthetically faster in file bursts.
