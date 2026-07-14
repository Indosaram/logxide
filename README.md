# LogXide

**Several-fold faster than stdlib logging (roughly 5–11× on file logging, scenario- and machine-dependent), sink-verified. Powered by Rust.**

Same stdlib API. Same `getLogger`. Same format strings. Just faster.

```python
# Before                              # After
import logging                        from logxide import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('myapp')
logger.info('Hello, world!')          # Same code, several-fold faster.
```

[![PyPI](https://img.shields.io/pypi/v/logxide)](https://pypi.org/project/logxide/)
[![Python](https://img.shields.io/pypi/pyversions/logxide)](https://pypi.org/project/logxide/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/Indosaram/logxide/actions/workflows/ci.yml/badge.svg)](https://github.com/Indosaram/logxide/actions/workflows/ci.yml)

## Installation

```bash
pip install logxide
```

```bash
# With Sentry integration
pip install logxide[sentry]
```

## Performance

LogXide is performance-first: its native Rust handlers dispatch on the GIL-released fast path, formatting and writing without materializing a Python `LogRecord`. As of 0.2.0 the text-sink wrappers (`FileHandler`, `StreamHandler`, `RotatingFileHandler`) emit through that native Rust path **by default**; a handler only falls back to the Python path for a custom `Formatter` subclass, `{`/`$`-style format strings, or a handler-level Python filter.

### Benchmarks

Two sink-verified benchmarks, both re-run this session on **macOS M4 Max, release build**, across **Python 3.12.11 and 3.14.2**. *Sink-verified durable throughput* means records the sink actually confirmed after `flush()`, not records merely enqueued. Numbers are machine-specific and rounded to ranges; baselines are noisy run-to-run (roughly ±40%), so treat the ranges as the signal, not any single figure. **CPython 3.12 and 3.14 come out at parity** once the test environments match, so the ranges below apply to both.

**Benchmark A — native `FileHandler` vs stdlib.** `benchmark/perf_vs_stdlib.py`, LogXide and stdlib each measured in isolation. `FileHandler` is synchronous, so these are durable (no async drops). Rounded speedup vs stdlib, comparable on Python 3.12 and 3.14:

| Scenario   | Speedup vs stdlib |
| :--------- | :---------------- |
| simple     | **~7–9×**         |
| structured | **~7–9×**         |
| `%`-args   | **~5–6×**         |

**Benchmark B — durable cross-library sink.** `benchmark/basic_handlers_benchmark.py`, each library in its own subprocess, sink-verified 20,200 / 20,200. Rounded speedup vs stdlib, comparable across Python 3.12 and 3.14:

| Sink     | Speedup vs stdlib         |
| :------- | :------------------------ |
| FILE     | **~6–11×**                |
| ROTATING | **~8–14×**                |
| STREAM   | **~5×** (async, see note) |

> **STREAM is asynchronous.** It reaches ~5× when its queue fully drains, but under a sustained max-rate burst the bounded queue can drop records (one loaded run delivered ~14,420 / 20,200; an idle machine delivered 20,200 / 20,200). Treat STREAM as fast best-effort delivery: call `flush()` and check `get_metrics()` to confirm what landed, rather than as a guaranteed durable multiplier.

Async HTTP delivery is accounted honestly on both versions: `http_block` lands 20,000 / 20,000 (durable), while `http_drop_newest` delivers ~260 / 20,000 and drops the rest, with `emitted == sink_acknowledged + queue_dropped + delivery_failed` holding throughout.

> A prior draft reported a "Python 3.14 regression" (roughly half the file-path speedup on 3.14). That was a measurement artifact, not a real regression: the 3.14 test environment had `sentry-sdk` installed while the 3.12 one did not, and importing it pulled in a formatter-less `NullHandler` that forced process-global caller-frame collection on every log (a ~20% tax that only hit the 3.14 runs). This is fixed in 0.2.1; environment-matched, the two versions are at parity.

For full per-handler p50/p99 latency, cross-library detail, and async accounting, see [docs/benchmarks.md](docs/benchmarks.md).

## Works With

LogXide intercepts stdlib logging — most libraries work without changes.

| Framework / Library | Status | Notes |
|---------------------|--------|-------|
| Flask | ✅ | `app.logger` automatically intercepted |
| Django | ✅ | `LOGGING` dictConfig supported |
| FastAPI / Uvicorn | ✅ | All uvicorn loggers intercepted |
| SQLAlchemy | ✅ | SQL query logging via `echo=True` |
| requests / httpx | ✅ | HTTP connection logs captured |
| boto3 / botocore | ✅ | AWS SDK logs captured |
| Sentry | ✅ | **Native integration** — auto-detects an already-configured SDK |
| Celery | ⚠️ | Requires `setup_logging` signal ([guide](docs/third-party-compatibility.md#celery)) |
| pytest | ⚠️ | Use `caplog_logxide` instead of `caplog` |

[Full compatibility guide for 20+ libraries →](docs/third-party-compatibility.md)

## Built-in Sentry Integration

No extra handlers. No configuration. Just works.

```python
import sentry_sdk
sentry_sdk.init(dsn="your-dsn")

from logxide import logging

logger = logging.getLogger(__name__)
logger.error("This is automatically sent to Sentry")
```

- Auto-detects a **configured** Sentry SDK (a call to `sentry_sdk.init()` must have run first)
- WARNING+ sent as events, INFO as breadcrumbs
- Full stack traces and custom context

An installed-but-unconfigured Sentry SDK does not attach a handler, and (as of 0.2.1) importing it no longer forces process-global caller-frame collection onto unrelated handlers.

## Native OpenTelemetry Support

Ship logs to any OTLP-compatible backend with zero dependencies:

```python
from logxide import OTLPHandler

handler = OTLPHandler(
    url="http://localhost:4318/v1/logs",
    service_name="my-service"
)
```

## Quick Start

```python
from logxide import logging

# Basic setup — same API as stdlib
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('myapp')
logger.info('Hello from LogXide!')
logger.warning('This works exactly like stdlib logging')
```

### Custom fields with `extra`

```python
logger.info("User logged in", extra={
    "user_id": 12345,
    "ip": "192.168.1.1",
    "metadata": {"browser": "Chrome", "version": 120}
})
```

### HTTP log shipping

```python
from logxide import HTTPHandler

handler = HTTPHandler(
    url="https://logs.example.com",
    global_context={"app": "myapp", "env": "production"},
    transform_callback=lambda records: {
        "logs": [{"msg": r["msg"], "level": r["levelname"]} for r in records]
    }
)
```

## What's Different from stdlib

LogXide reimplements Python's logging in Rust for speed. The API is the same, but some advanced stdlib patterns aren't supported:

| Feature | Status |
|---------|--------|
| `getLogger`, `info`, `debug`, `warning`, `error`, `critical` | ✅ Same API |
| `basicConfig`, format strings, levels, filters | ✅ Same API |
| `FileHandler`, `StreamHandler`, `RotatingFileHandler` | ✅ Rust-native |
| `HTTPHandler`, `OTLPHandler` | ✅ Rust-native, high throughput |
| Custom Python handlers via `addHandler()` | ⚠️ Accepted; runs once on the Python side (no fast-path GIL release) |
| Subclassing `LogRecord` or `Logger` | ❌ Rust types, not subclassable |
| pytest `caplog` fixture | ⚠️ Use `caplog_logxide` instead |

**Instead of subclassing LogRecord**, use `extra={}` for custom fields, `global_context` for metadata, or `transform_callback` for output transformation.

## Compatibility

- **Python**: 3.12, 3.13, 3.14 (fully tested and supported)
- **Python 3.15**: Not yet supported — blocked by an upstream `pyo3` ↔ Python 3.15-alpha ABI mismatch (the compiled extension references a CPython internal symbol `_PyType_FromSlots` that current 3.15 alpha builds do not export). Tracking for re-enablement once `pyo3` ships a 3.15-compatible release.
- **Platforms**: macOS, Linux, Windows
- **Dependencies**: None (Rust compiled into native extension)

## Documentation

- [Usage Guide](docs/usage.md) — Complete API guide
- [Integration Guide](docs/integrations/index.md) — Flask, Django, FastAPI
- [Third-Party Compatibility](docs/third-party-compatibility.md) — 20+ libraries
- [Performance Benchmarks](docs/benchmarks.md) — Detailed analysis
- [Architecture](docs/architecture.md) — Technical design
- [API Reference](docs/reference.md) — Full reference

## Contributing

```bash
git clone https://github.com/Indosaram/logxide
cd logxide
pip install maturin
maturin develop
pytest tests/
```

See [development guide](docs/development.md) for details.

## License

MIT License — see [LICENSE](LICENSE) for details.
