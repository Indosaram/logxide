# LogXide

**High-Performance Rust-Powered Logging for Python**

LogXide is a drop-in replacement for Python's standard logging module, delivering exceptional performance through its async Rust implementation.

## Key Features

- **High Performance**: Rust-powered async logging with exceptional throughput
- **Drop-in Replacement**: Full compatibility with Python's logging module API
- **Thread-Safe**: Complete support for multi-threaded applications
- **Async Processing**: Non-blocking log message processing with Tokio runtime
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

LogXide delivers exceptional performance through its Rust-powered async architecture. See our [comprehensive benchmarks](docs/benchmarks.md) for detailed performance analysis.

**Key highlights:**
- **10-50x faster** than other libraries in I/O-heavy scenarios
- **Async architecture** prevents blocking on log operations
- **Concurrent handler execution** for maximum throughput

## Compatibility

- **Python**: 3.12+ (3.13+ recommended)
- **Platforms**: macOS, Linux, Windows
- **API**: 100% compatible with Python's `logging` module
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
