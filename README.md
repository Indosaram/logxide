# LogXide

**High-Performance Rust-Powered Logging for Python**

LogXide is a drop-in replacement for Python's standard logging module, delivering exceptional performance through its native Rust implementation.

## Key Features

- **High Performance**: Rust-powered logging with exceptional throughput
- **Drop-in Replacement**: Full compatibility with Python's logging module API
- **Thread-Safe**: Complete support for multi-threaded applications
- **Direct Processing**: Efficient log message processing with native Rust handlers
- **Rich Formatting**: All Python logging format specifiers with advanced features
- **Level Filtering**: Hierarchical logger levels with inheritance
- **Sentry Integration**: Automatic error tracking with Sentry (optional)

## Quick Start

```python
# Simple and automatic - no setup needed!
from logxide import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('myapp')
logger.info('Hello from LogXide!')
```

That's it! LogXide automatically installs itself when imported. No manual setup required.

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

## Important Limitations

LogXide uses **Rust-native handlers only** for maximum performance. This means:

- **Rust handlers only**: `logger.addHandler()` only accepts Rust native handlers (FileHandler, StreamHandler, RotatingFileHandler)
- **No Python handlers**: Custom Python logging.Handler subclasses are not supported
- **No StringIO capture**: Use file-based logging for tests
- **No pytest caplog**: Not compatible with Rust native architecture
- **Use `basicConfig()`**: Recommended for simple configuration
- **Use `addHandler()`**: For advanced handler configuration with Rust handlers
- **File-based testing**: Write to files instead of capturing streams

**Example - The LogXide way:**

```python
# Option 1: Use basicConfig() for simple configuration
import tempfile
from logxide import logging

# For production - stdout/stderr
logging.basicConfig(level=logging.INFO)

# For testing - file output
with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
    logging.basicConfig(filename=f.name, level=logging.DEBUG, force=True)
    logger = logging.getLogger('test')
    logger.info("Test message")
    
    # Read and verify
    with open(f.name) as log_file:
        assert "Test message" in log_file.read()

# Option 2: Use addHandler() with Rust native handlers
from logxide import logging, FileHandler, StreamHandler

logger = logging.getLogger('myapp')
logger.setLevel(logging.INFO)

# Add Rust native handlers
file_handler = FileHandler('app.log')
stream_handler = StreamHandler()

logger.addHandler(file_handler)
logger.addHandler(stream_handler)
```

**What NOT to do:**

```python
# Wrong - Custom Python handlers not supported
import logging as stdlib_logging

class MyCustomHandler(stdlib_logging.Handler):
    def emit(self, record):
        print(record.msg)

handler = MyCustomHandler()
logger.addHandler(handler)  # Raises ValueError

# Wrong - StringIO capture doesn't work with stdlib handlers
import io
stream = io.StringIO()
handler = stdlib_logging.StreamHandler(stream)
logger.addHandler(handler)  # Raises ValueError - not a Rust handler
```

## Compatibility

- **Python**: 3.12+ (3.14 supported)
- **Platforms**: macOS, Linux, Windows
- **API**: Core logging API compatible (see limitations above)
- **Dependencies**: None (Rust compiled into native extension)

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

**LogXide delivers the performance you need without sacrificing the Python logging API you know.**

*Built with Rust for high-performance Python applications.*
