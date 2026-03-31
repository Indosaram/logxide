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

All benchmarks run on macOS ARM64 (Apple Silicon), Python 3.12 / 3.14, averaged across 3 runs.
Handler-by-handler benchmarks use 10,000 iterations (`basic_handlers_benchmark.py`); File I/O scenario benchmarks (Simple / Structured / Error Logging) use 100,000 iterations (`compare_loggers.py`).

LogXide drops the GIL immediately and delegates formatting and I/O to Rust-native `BufWriter` (file) or crossbeam channels (stream/HTTP), avoiding Python overhead entirely.

### Performance Summary

| Handler / Scenario | Structlog | LogXide | LogXide vs Structlog |
|--------------------|-----------|---------|----------------------|
| **FileHandler (Raw I/O)** | ~98,000 Ops/sec | **281,741 Ops/sec** | **2.8x faster** |
| **Simple Logging** | 122,995 Ops/sec | **281,741 Ops/sec** | **2.2x faster** |
| **Structured Logging** | 96,546 Ops/sec | **266,242 Ops/sec** | **2.7x faster** |
| **Error Logging** | ~85,000 Ops/sec | **251,238 Ops/sec** | **2.9x faster** |

*\*Note: Structlog relies on Python's stdlib for actual file output, so its theoretical maximum is capped by stdlib throughput, minus the overhead of its JSON/Console render processors. LogXide bypasses this completely via Rust `BufWriter`.*

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
- **Custom Python handlers**: Accepted via `addHandler()` but bypass the Rust performance pipeline
- **pytest `caplog`**: LogXide provides a custom plugin (auto-registered via entry point); requires explicit `logger.addHandler(caplog.handler)` — see [Testing Guide](testing.md)

For the complete compatibility matrix, see [Compatibility](compatibility.md).

---

## When to Use Which

### Choose LogXide when:
- **Performance is the priority** — 2.2–2.9x faster across real-world scenarios, leveraging Rust to bypass the GIL.
- **You have existing stdlib code** — Minimal migration cost; API-compatible for common patterns.
- **You need native production handlers** — Async HTTP batching, OTLP export, and native Sentry integration without Python-side overhead.
- **Framework integration** — Transparently hooks into Django/FastAPI `dictConfig`.

### Choose Structlog when:
- **Structured data is core** — A chainable processor pipeline for field transformation/filtering is essential.
- **Context binding is a must** — You heavily rely on `.bind()` or thread-local context variables to track requests.
- **Custom processors** — You need extreme flexibility in mutating log records before they hit the output.
- **JSON-first architecture** — Every single output must be rigidly structured JSON.
