# LogXide

**High-Performance Rust-Powered Logging for Python**

LogXide is a high-performance logging library for Python, delivering exceptional performance through its native Rust implementation. It provides a familiar logging API but prioritizes **performance over full compatibility**.

## Key Features

- **High Performance**: Rust-powered logging with exceptional throughput
- **Familiar API**: Similar to Python's logging module (not a drop-in replacement)
- **Thread-Safe**: Complete support for multi-threaded applications
- **Direct Processing**: Efficient log message processing with native Rust handlers
- **Rich Formatting**: All Python logging format specifiers with advanced features
- **Level Filtering**: Hierarchical logger levels with inheritance
- **Sentry Integration**: Automatic error tracking with Sentry (optional)

## ⚠️ Important: Not a Drop-in Replacement

LogXide is **NOT** a drop-in replacement for Python's logging module. It prioritizes performance over compatibility:

| Feature | Status | Notes |
|---------|--------|-------|
| Basic logging API | ✅ | `getLogger`, `info`, `debug`, etc. |
| Formatters | ✅ | `PercentStyle`, `StrFormatStyle`, `StringTemplateStyle` |
| Rust handlers | ✅ | `FileHandler`, `StreamHandler`, `RotatingFileHandler`, `HTTPHandler`, `OTLPHandler` |
| Custom Python handlers | ❌ | Not supported - use Rust handlers only |
| Subclassing `LogRecord` | ❌ | Rust type, not subclassable |
| Subclassing `Logger` | ❌ | Rust type, not subclassable |
| pytest `caplog` | ❌ | Not compatible |
| StringIO capture | ❌ | Use file-based logging |

**If your project requires:**
- Subclassing `LogRecord` or `Logger`
- Custom Python handlers
- pytest `caplog` fixture
- Full stdlib logging compatibility

**→ Use standard Python logging instead.**

## Quick Start

```python
from logxide import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('myapp')
logger.info('Hello from LogXide!')
```

LogXide automatically installs itself when imported.

## Installation

```bash
# Basic installation
pip install logxide

# With Sentry integration
pip install logxide[sentry]

# Development dependencies
pip install logxide[dev]
```

> **📘 [Usage Guide](USAGE.md)** - Common mistakes, correct patterns, and troubleshooting

## Documentation

- **[Feature Comparison](PYTHON_LOGGING_FEATURE_COMPARISON.md)** - Complete comparison with Python's standard logging
- **[Feature Analysis Summary](FEATURE_ANALYSIS_SUMMARY.md)** - Quick summary of supported features
- **[Usage Guide](docs/usage.md)** - Complete usage examples and API guide
- **[Integration Guide](docs/integration.md)** - Flask, Django, and FastAPI integration
- **[Sentry Integration](docs/sentry.md)** - Automatic error tracking with Sentry
- **[Performance Benchmarks](docs/benchmarks.md)** - Comprehensive performance analysis
- **[Architecture](docs/architecture.md)** - Technical architecture and design
- **[Installation](docs/installation.md)** - Installation and setup guide
- **[Development](docs/development.md)** - Contributing and development guide
- **[API Reference](docs/reference.md)** - Complete API documentation

## Sentry Integration

LogXide includes optional Sentry integration for automatic error tracking:

```python
# Configure Sentry first
import sentry_sdk
sentry_sdk.init(dsn="your-sentry-dsn")

# Import LogXide - Sentry integration is automatic!
from logxide import logging

logger = logging.getLogger(__name__)
logger.warning("This will appear in Sentry")
logger.error("This error will be tracked")
```

**Features:**
- **Automatic detection** of Sentry configuration
- **Level filtering** (WARNING and above sent to Sentry)
- **Rich context** including stack traces and custom data
- **Zero configuration** required

## Performance

LogXide delivers exceptional performance through its Rust-powered native architecture. See our [comprehensive benchmarks](docs/benchmarks.md) for detailed performance analysis.

### Python 3.12 Benchmark Results (File I/O)

**Real-world file logging performance (100,000 iterations):**

| Test Scenario | LogXide | Picologging | Python logging | vs Pico | vs Stdlib |
|--------------|---------|-------------|----------------|---------|-----------|
| **Simple Logging** | 446,135 ops/sec | 372,020 ops/sec | 157,220 ops/sec | **+20%** | **+184%** |
| **Structured Logging** | 412,235 ops/sec | 357,193 ops/sec | 153,547 ops/sec | **+15%** | **+168%** |
| **Error Logging** | 426,294 ops/sec | 361,053 ops/sec | 155,332 ops/sec | **+18%** | **+174%** |

**Key highlights:**
- **15-20% faster** than Picologging (C-based) in production file I/O scenarios
- **2.7x faster** than standard Python logging - upgrade with zero code changes!
- **2.5x faster** than Structlog across all tests
- **Native Rust I/O** provides measurable performance advantages
- **Consistent performance** across all logging patterns

## Limitations

LogXide uses **Rust-native handlers only** for maximum performance:

- **Rust handlers only**: `FileHandler`, `StreamHandler`, `RotatingFileHandler`, `HTTPHandler`, `OTLPHandler`
- **No custom Python handlers**: `logger.addHandler()` rejects Python `logging.Handler` subclasses
- **No subclassing**: `LogRecord`, `Logger` are Rust types (not subclassable)
- **No StringIO capture**: Use file-based logging for tests
- **No pytest caplog**: Not compatible with Rust native architecture

### Alternatives to LogRecord Subclassing

Instead of subclassing `LogRecord`, use these approaches:

| Use Case | Alternative |
|----------|-------------|
| Add custom fields | Use `extra` parameter: `logger.info("msg", extra={"user_id": 123})` |
| Add metadata to all logs | Use `global_context` in `HTTPHandler` |
| Transform log output | Use `transform_callback` in `HTTPHandler` |
| Dynamic context per batch | Use `context_provider` in `HTTPHandler` |

**Example - Adding custom fields:**

```python
from logxide import logging

logger = logging.getLogger('myapp')

# Use extra parameter (supports complex types: int, dict, list)
logger.info("User logged in", extra={
    "user_id": 12345,
    "ip": "192.168.1.1",
    "metadata": {"browser": "Chrome", "version": 120}
})
```

**Example - Global context for all logs:**

```python
from logxide import HTTPHandler

handler = HTTPHandler(
    url="https://logs.example.com",
    global_context={
        "application": "myapp",
        "environment": "production",
        "version": "1.2.3"
    }
)
```

**Example - Custom JSON transformation:**

```python
handler = HTTPHandler(
    url="https://logs.example.com",
    transform_callback=lambda records: {
        "logs": [{"msg": r["msg"], "level": r["levelname"]} for r in records],
        "meta": {"count": len(records)}
    }
)
```

**Example - OpenTelemetry OTLP (Protobuf):**

```python
from logxide import OTLPHandler

handler = OTLPHandler(
    url="http://localhost:4318/v1/logs",
    service_name="my-service"
)
```

## Compatibility

- **Python**: 3.12+ (3.14 supported)
- **Platforms**: macOS, Linux, Windows
- **Dependencies**: None (Rust compiled into native extension)

### Third-party Library Compatibility

| Library | Compatible | Notes |
|---------|------------|-------|
| Flask | ✅ | Works with `app.logger` |
| Django | ✅ | Works with Django logging |
| FastAPI | ✅ | Works with Uvicorn |
| pytest | ⚠️ | `caplog` not supported, use file-based testing |
| Sentry | ✅ | Auto-integration supported |
| structlog | ❌ | Requires custom handlers |
| infra_basement | ❌ | Requires LogRecord subclassing |

## Contributing

We welcome contributions! See our [development guide](docs/development.md) for details.

```bash
# Quick development setup
git clone https://github.com/Indosaram/logxide
cd logxide
pip install maturin
maturin develop
pytest tests/
```

## License

[Add your license information here]

---

**LogXide delivers high performance for applications that don't need full logging compatibility.**

*Built with Rust for high-performance Python applications.*
