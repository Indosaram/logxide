# LogXide vs Structlog

This page provides a detailed deep-dive comparing LogXide to Structlog. For a high-level compatibility overview, see the [Compatibility Overview](compatibility.md).

Structlog focuses on **structured/context-rich logging**, while LogXide focuses on **raw performance with stdlib compatibility**. They serve different use cases but overlap in production Python logging.

## Architecture

| Aspect | LogXide | Structlog |
|---|---|---|
| **Implementation** | Rust native core via PyO3 | Pure Python |
| **GIL Strategy** | Releases GIL for Rust dispatch on the fast path; `%`-args & Python handlers/filters hold it | Holds GIL for entire pipeline |
| **Core concept** | stdlib `logging` compatible | Processor pipeline |
| **Log Record** | Rust `Arc<LogRecord>` | Python dict (event dict) |
| **Thread Safety** | Rust `RwLock` | Thread-local context |

---

## Performance

LogXide moves formatting and I/O into a Rust core and releases the GIL for the Rust dispatch on the fast path (no Python filter/handler/caller-info); `%`-args formatting and Python handlers/filters still hold the GIL. See [Compatibility](compatibility.md#the-gil-and-what-actually-runs-in-rust).

!!! note "Cross-library numbers are corrected and sink-verified"
    An earlier revision withdrew the per-handler tables because the old `benchmark/basic_handlers_benchmark.py` was defective (closed output stream, async drops counted as delivered, a mislabeled "RotatingFileHandler", and stdlib plus LogXide in the same patched process, which also contaminated the stdlib-backed Structlog column). The harness has been rebuilt: each library runs in its own subprocess, the sink is verified after flush, and durable throughput is reported separately from producer latency. The corrected numbers below replace the withdrawn ones.

### Durable throughput vs Structlog (corrected, sink-verified)

Measured with `benchmark/basic_handlers_benchmark.py` on macOS M4 Max, CPython 3.14.2, release build, `-n 20000`, subprocess-isolated per library. **Durable** = records the sink confirmed after flush (every row verified at 20,200 / 20,200). Numbers are machine-specific and rounded:

| Sink   | LogXide durable (p50) | Structlog durable (p50) | stdlib durable |
| :----- | :-------------------- | :---------------------- | :------------- |
| FILE   | ~739K rec/s (833 ns)  | 41,364 rec/s (5,583 ns) | 74,605 rec/s   |
| STREAM | ~273K rec/s (917 ns)  | 116,796 rec/s (5,208 ns) | 53,292 rec/s  |

Structlog is genuinely fast on the **stream** sink here, beating stdlib at ~2.2× (116,796 vs 53,292 rec/s) and outrunning both stdlib and Loguru. On the **file** sink it trails stdlib. LogXide leads all libraries on both sinks (~10× stdlib on file, ~5× on stream). The FILE figure varies ~740K–960K rec/s across runs. See [benchmarks.md](benchmarks.md#comparative-benchmark--all-logging-libraries-corrected-sink-verified) for the full tables and async accounting.

### Architectural advantages (independent of any single benchmark)

- Structlog relies on Python's stdlib for actual file output, so its throughput is bounded by stdlib plus its JSON/Console render processors. LogXide writes files through a Rust `BufWriter` and does background async I/O for stream/HTTP/OTLP.
- **Explicit async accounting**: `get_metrics()` reports `emitted`/`sink_acknowledged`/`queue_dropped`/`delivery_failed`/`in_flight`, so async "throughput" always counts records the sink confirmed — never records that were merely enqueued.

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
- **Custom Python handlers**: Accepted via `addHandler()`; a foreign Python handler runs once on the Python side, without the fast-path GIL release. Rust-backed handlers are dispatched once and no longer double-emit or leak to unrelated loggers (fixed in 0.2.0)
- **pytest `caplog`**: LogXide provides a custom plugin (auto-registered via entry point); requires explicit `logger.addHandler(caplog.handler)` — see [Testing Guide](testing.md)

For the complete compatibility matrix, see [Compatibility](compatibility.md).

---

## When to Use Which

### Choose LogXide when:
- **Performance is the priority** — LogXide runs formatting and file I/O in a Rust core rather than through Python's stdlib output path. On the corrected, sink-verified harness it leads Structlog on every sink (~10× stdlib on file, ~5× on stream), even though Structlog itself beats stdlib on the stream sink.
- **You have existing stdlib code** — Minimal migration cost; API-compatible for common patterns.
- **You need native production handlers** — Async HTTP batching, OTLP export, and native Sentry integration without Python-side overhead.
- **Framework integration** — Transparently hooks into Django/FastAPI `dictConfig`.

### Choose Structlog when:
- **Structured data is core** — A chainable processor pipeline for field transformation/filtering is essential.
- **Context binding is a must** — You heavily rely on `.bind()` or thread-local context variables to track requests.
- **Custom processors** — You need extreme flexibility in mutating log records before they hit the output.
- **JSON-first architecture** — Every single output must be rigidly structured JSON.
