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

All benchmarks run on macOS ARM64 (Apple Silicon), **Python 3.12** (Picologging's highest supported version), averaged across 3 runs of 10,000 iterations (`benchmark/basic_handlers_benchmark.py`). Same Python version, same harness, same format string for both libraries.

LogXide drops the GIL immediately and delegates formatting and I/O to Rust-native `BufWriter` (file) or crossbeam channels (stream/HTTP), avoiding Python overhead entirely.

> **Note**: Picologging skips `sys._getframe()` caller-frame extraction that the standard library requires, which inflates its raw throughput figures. LogXide performs full stdlib-compatible frame introspection only when the format string requires it (`%(funcName)s`, `%(pathname)s`, etc.).

### Performance Summary (Python 3.12)

| Handler                      |   Picologging |               LogXide | Speedup           |
| :--------------------------- | ------------: | --------------------: | :---------------- |
| **FileHandler**              |       384,319 | **1,139,874 Ops/sec** | **2.97× faster**  |
| **RotatingFileHandler** ¹    |       411,055 |   **897,118 Ops/sec** | **2.18× faster**  |
| **TimedRotatingFileHandler** |    N/A (none) |    **897K Ops/sec**   | LogXide-only      |
| **HTTPHandler**              |    N/A (none) |       (batch + async) | LogXide-only      |
| **OTLPHandler**              |    N/A (none) |             (native)  | LogXide-only      |

¹ *Picologging has no `RotatingFileHandler`; the harness substitutes its `FileHandler`. LogXide's number is for the actual rotating handler with size-based rotation enabled.*

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
- **Custom Python handlers**: Accepted via `addHandler()`, but they run alongside the Rust pipeline (events may be processed twice) and do not run on the zero-GIL Rust path
- **pytest `caplog`**: LogXide provides a custom plugin (auto-registered via entry point); requires explicit `logger.addHandler(caplog.handler)` — see [Testing Guide](testing.md)

For the complete compatibility matrix, see [Compatibility](compatibility.md).

---

## When to Use Which

### Choose LogXide when:
1. **You use Python 3.13+** — Picologging is completely broken on Python 3.13 and newer.
2. **You need raw throughput** — On Python 3.12 (where both run), LogXide is ~3× faster than Picologging on `FileHandler` and `RotatingFileHandler` while still performing full caller-frame introspection.
3. **You need a Richer Handler Ecosystem** — LogXide provides asynchronous HTTP batching, OTLP, time-based rotation, and gzip compression out of the box.
4. **You want Active Maintenance** — Picologging's development essentially stopped in 2023.
5. **Detailed format parity is essential** — LogXide performs exact frame introspections that standard `logging` expects.

### Choose Picologging when:
- You are stuck on Python 3.12 or older **and** cannot install a Rust-toolchain-built wheel for any reason. In every other case, LogXide is both faster and better-supported.
