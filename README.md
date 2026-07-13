# LogXide

**Up to 13× faster Python logging, powered by Rust.**

Same stdlib API. Same `getLogger`. Same format strings. Just faster.

```python
# Before                              # After
import logging                        from logxide import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('myapp')
logger.info('Hello, world!')          # Up to 13× faster. Same code.
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

### Cross-library durable throughput (sink-verified)

Measured with `benchmark/basic_handlers_benchmark.py` on macOS M4 Max, CPython 3.14.2, release build, `-n 20000`, each library in its own subprocess. **Durable** = records the sink actually confirmed after flush (every row verified at 20,200 / 20,200), not records merely enqueued. Numbers are machine-specific and rounded:

| Sink        |  LogXide durable rec/s |    stdlib | LogXide vs stdlib |
| :---------- | ---------------------: | --------: | :---------------- |
| FILE        |             ~739K–960K |    74,605 | **~10×**          |
| STREAM      |                ~273K   |    53,292 | **~5×**           |
| ROTATING    |                ~202K   |    42,981 | **~4.7×**         |

LogXide leads every sink. On STREAM, Structlog is the runner-up (~117K rec/s, ~2.2× stdlib) but still well behind LogXide. Full tables, per-library p50 latencies, and async delivery accounting are in [docs/benchmarks.md](docs/benchmarks.md#comparative-benchmark--all-logging-libraries-corrected-sink-verified).

### vs stdlib, single-format FileHandler (subprocess-isolated)

FileHandler benchmark, Python 3.12, 100K iterations, format `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`, LogXide vs stdlib with stdlib in a subprocess for fair isolation. `FileHandler` is synchronous, so these are durable numbers (no async drops). Figures are machine-specific:

| Scenario              |   LogXide |  stdlib | Speedup     |
| :-------------------- | --------: | ------: | :---------- |
| Simple                | 1,922,911 | 145,562 | **13.21×**  |
| Structured (f-string) | 1,612,029 | 144,328 | **11.17×**  |
| With `%s` args        |   976,572 | 144,156 | **6.77×**   |

> **Python 3.14**: LogXide is also faster (4.25–7.23× vs stdlib), though the absolute gap narrows because stdlib's per-iteration overhead is lower under 3.14. See [docs/benchmarks.md](docs/benchmarks.md#python-314) for the full Python 3.14 table.

For per-handler latency, async accounting, internal optimization wave breakdown, and historical comparison data, see [docs/benchmarks.md](docs/benchmarks.md).

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

An installed-but-unconfigured Sentry SDK does not attach a handler, and (as of 0.2.0) importing it no longer forces process-global caller-frame collection onto unrelated handlers.

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
