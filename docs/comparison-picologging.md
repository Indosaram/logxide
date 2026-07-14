# LogXide vs Picologging

This page provides a detailed deep-dive comparing LogXide to Picologging. For a high-level compatibility overview, see the [Compatibility Overview](compatibility.md).

Both LogXide and Picologging pursue the same goal — accelerate Python logging with native code. Picologging uses Cython, while LogXide uses Rust via PyO3.

## Architecture

| Aspect | LogXide | Picologging |
|---|---|---|
| **Implementation** | Rust native core via PyO3 | Cython (C extension) |
| **GIL Strategy** | Releases GIL for Rust dispatch on the fast path; `%`-args & Python handlers/filters hold it | Holds GIL for entire pipeline |
| **Thread Safety** | Rust `RwLock` + `Arc` | CPython `RLock` |
| **Log Record** | Rust `Arc<LogRecord>` | Cython-optimized `LogRecord` |
| **Python 3.13+** | ✅ (3.14 tested) | ❌ (incompatible) |

> ⚠️ **Picologging does not install or run on Python 3.13 or newer.** Its Cython bindings are fundamentally incompatible with recent CPython API changes.

---

## Performance

LogXide moves formatting and I/O into a Rust core and releases the GIL for the Rust dispatch on the fast path (no Python filter/handler/caller-info); `%`-args formatting and Python handlers/filters still hold the GIL. See [Compatibility](compatibility.md#the-gil-and-what-actually-runs-in-rust).

!!! note "Picologging is not in the corrected cross-library runs"
    An earlier revision withdrew the per-handler multipliers vs Picologging because the old `benchmark/basic_handlers_benchmark.py` was defective (closed output stream, async drops counted as delivered, a mislabeled "RotatingFileHandler", same-process library imports). The harness has since been rebuilt with subprocess isolation, sink verification, and separate durable-throughput vs producer-latency reporting. **Picologging is excluded from the corrected runs because it does not install on Python 3.13+ (the benchmark machine runs CPython 3.14.2)**, so no cross-library multiplier against Picologging is asserted here — the comparison below stays qualitative. For the libraries that do run (stdlib, Loguru, Structlog), LogXide leads on every sink (~6–11× stdlib on file, ~8–14× on rotating, ~5× on the async stream sink; comparable on Python 3.12 and 3.14); see [benchmarks.md](benchmarks.md#comparative-benchmark--all-logging-libraries-corrected-sink-verified).

### Qualitative differences that still hold

- **Frame introspection**: Picologging skips the `sys._getframe()` caller-frame extraction that the standard library performs, which inflates its raw throughput figures. LogXide performs full stdlib-compatible frame introspection only when the format string requires it (`%(funcName)s`, `%(pathname)s`, etc.), so like-for-like comparisons must account for that difference.
- **Implementation**: Rust core (LogXide) vs Cython C extension (Picologging); LogXide runs on Python 3.13+ where Picologging does not.
- **Handler ecosystem**: LogXide adds async HTTP batching, OTLP, time-based rotation, and gzip compression that Picologging lacks.
- **Async accounting**: `get_metrics()` reports `emitted`/`sink_acknowledged`/`queue_dropped`/`delivery_failed`/`in_flight`, so async "throughput" always counts records the sink confirmed.

| Handler                      |   Picologging |               LogXide |
| :--------------------------- | ------------: | --------------------: |
| **FileHandler**              |            ✅ | ✅ (Rust `BufWriter`) |
| **RotatingFileHandler**      |    N/A (none) | ✅ (Rust native)      |
| **TimedRotatingFileHandler** |    N/A (none) | ✅ (Rust native)      |
| **HTTPHandler**              |    N/A (none) | ✅ (batch + async)    |
| **OTLPHandler**              |    N/A (none) | ✅ (native)           |

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
- **Custom Python handlers**: Accepted via `addHandler()`; a foreign Python handler runs once on the Python side, without the fast-path GIL release. Rust-backed handlers are dispatched once and no longer double-emit or leak to unrelated loggers (fixed in 0.2.0)
- **pytest `caplog`**: LogXide provides a custom plugin (auto-registered via entry point); requires explicit `logger.addHandler(caplog.handler)` — see [Testing Guide](testing.md)

For the complete compatibility matrix, see [Compatibility](compatibility.md).

---

## When to Use Which

### Choose LogXide when:
1. **You use Python 3.13+** — Picologging is completely broken on Python 3.13 and newer.
2. **You need raw throughput** — LogXide runs its formatting and I/O in a Rust core while still performing full caller-frame introspection (which Picologging skips). A direct sink-verified LogXide-vs-Picologging multiplier is not asserted because Picologging cannot run on the Python 3.13+ benchmark machine; against the libraries that do run, LogXide leads every sink.
3. **You need a Richer Handler Ecosystem** — LogXide provides asynchronous HTTP batching, OTLP, time-based rotation, and gzip compression out of the box.
4. **You want Active Maintenance** — Picologging's development essentially stopped in 2023.
5. **Detailed format parity is essential** — LogXide performs exact frame introspections that standard `logging` expects.

### Choose Picologging when:
- You are stuck on Python 3.12 or older **and** cannot install a Rust-toolchain-built wheel for any reason. In every other case, LogXide is both faster and better-supported.
