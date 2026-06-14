# LogXide vs Structlog

This page provides a detailed deep-dive comparing LogXide to Structlog. For a high-level compatibility overview, see the [Compatibility Overview](compatibility.md).

Structlog focuses on **structured/context-rich logging**, while LogXide focuses on **raw performance with stdlib compatibility**. They serve different use cases but overlap in production Python logging.

## Architecture

| Aspect | LogXide | Structlog |
|---|---|---|
| **Implementation** | Rust native core via PyO3 | Pure Python |
| **GIL Strategy** | Zero-GIL (drops immediately) | Holds GIL for entire pipeline |
| **Core concept** | stdlib `logging` compatible | Processor pipeline |
| **Log Record** | Rust `Arc<LogRecord>` | Python dict (event dict) |
| **Thread Safety** | Rust `RwLock` | Thread-local context |

---

## Performance: Handler-by-Handler Benchmark

All benchmarks run on macOS ARM64 (Apple Silicon), **Python 3.12**, averaged across 3 runs of 10,000 iterations (`benchmark/basic_handlers_benchmark.py`).

LogXide drops the GIL immediately and delegates formatting and I/O to Rust-native `BufWriter` (file) or crossbeam channels (stream/HTTP), avoiding Python overhead entirely.

> **Methodology note**: Structlog's `FileHandler` test uses `ProcessorFormatter` wrapping `ConsoleRenderer` with `fmt="%(message)s"`. LogXide is benchmarked against the more demanding stdlib-style `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"` format, so structlog's column is on a slightly easier path. Even so, LogXide is faster.

### Performance Summary (Python 3.12)

| Handler             |   Structlog | LogXide               | Speedup           |
| :------------------ | ----------: | --------------------: | :---------------- |
| **FileHandler**     |     932,755 | **1,139,874 Ops/sec** | **1.22× faster**  |
| **StreamHandler**   |     920,069 |   **955,112 Ops/sec** | **1.04× faster**  |
| **Simple Logging**  |     932,755 | **1,922,911 Ops/sec** ¹ | **2.06× faster**  |
| **with `%s` args**  |     ~932K   |   **976,572 Ops/sec** ¹ | comparable        |

¹ *Simple/args figures from `benchmark/perf_vs_stdlib.py` (100K iterations × 3 runs). Structlog is approximated from FileHandler since it doesn't have a separate "args" path.*

*Structlog relies on Python's stdlib for actual file output, so its theoretical maximum is capped by stdlib throughput, minus the overhead of its JSON/Console render processors. LogXide bypasses this completely via Rust `BufWriter`.*

---

## Feature Comparison Matrix

| Feature | LogXide | Structlog |
|---------|---------|-----------|
| stdlib API compatible | ⚠️ (common patterns; subclassing/custom formatters limited) | ❌ (wrapper layer) |
| `basicConfig()` | ✅ | ❌ |
| `dictConfig()` | ✅ | ❌ (requires stdlib bridge) |
| Processor pipeline | ❌ | ✅ (core feature) |
| Context binding (`bind()`) | ❌ | ✅ |
| JSON rendering | ✅ (HTTPHandler) | ✅ (`JSONRenderer`) |
| Console rendering | ✅ (`ColorFormatter`) | ✅ (`ConsoleRenderer`) |
| FileHandler | ✅ (Rust BufWriter) | ⚠️ (via stdlib) |
| HTTPHandler (async batch) | ✅ | ❌ |
| OTLPHandler | ✅ | ❌ |
| TimedRotatingFileHandler| ✅ (Rust + gzip) | ⚠️ (via stdlib) |
| Sentry integration | ✅ (native) | ⚠️ (stdlib bridge) |

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
- **Performance is the priority** — 1.2–2× faster than Structlog on file/stream I/O on Python 3.12, leveraging Rust to bypass the GIL.
- **You have existing stdlib code** — Minimal migration cost; API-compatible for common patterns.
- **You need native production handlers** — Async HTTP batching, OTLP export, and native Sentry integration without Python-side overhead.
- **Framework integration** — Transparently hooks into Django/FastAPI `dictConfig`.

### Choose Structlog when:
- **Structured data is core** — A chainable processor pipeline for field transformation/filtering is essential.
- **Context binding is a must** — You heavily rely on `.bind()` or thread-local context variables to track requests.
- **Custom processors** — You need extreme flexibility in mutating log records before they hit the output.
- **JSON-first architecture** — Every single output must be rigidly structured JSON.
