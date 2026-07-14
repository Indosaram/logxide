# Welcome to LogXide

LogXide is a high-performance logging library for Python, delivering **several-fold the throughput of stdlib `logging` (roughly 5–11× on file logging, scenario- and machine-dependent, sink-verified)** through its native Rust implementation. CPython 3.12 and 3.14 come out at parity, so there is no version-specific penalty. It is API-compatible with Python's standard `logging` module for the common patterns (`getLogger`, `basicConfig`, `dictConfig`, format strings) — drop in `from logxide import logging` and most code keeps working unchanged.

## Documentation

### Getting Started
- **[Installation Guide](installation.md)** - Installation and setup instructions
- **[Usage Guide](usage.md)** - Complete usage examples and API guide

### Integrations
- **[Framework Integration](integrations/index.md)** - Flask, Django, and FastAPI integration
- **[Sentry Integration](integrations/sentry.md)** - Automatic error tracking with Sentry

### Performance & Architecture
- **[Performance Benchmarks](benchmarks.md)** - Comprehensive performance analysis and comparisons
- **[Architecture](architecture.md)** - Technical architecture and design details

### Development
- **[Development Guide](development.md)** - Contributing and development setup
- **[API Reference](reference.md)** - Complete API documentation

## Key Features

- **High Performance**: Rust-powered logging with several-fold the throughput of stdlib (roughly 5–11× on file logging; sink-verified, machine-specific, and at parity across Python 3.12 and 3.14)
- **Familiar API**: stdlib-compatible for the common patterns; one-line migration from `import logging`
- **Thread-Safe**: Complete support for multi-threaded applications via Rust `parking_lot::Mutex` + `arc_swap::ArcSwap`
- **Direct Processing**: Efficient log message processing with native Rust handlers (file I/O synchronous, stream/HTTP/OTLP non-blocking)
- **Rich Formatting**: All Python logging format specifiers with advanced features
- **Level Filtering**: Hierarchical logger levels with inheritance
- **Sentry Integration**: Automatic error tracking when a Sentry SDK is already configured (optional)
- **Native OpenTelemetry**: Built-in OTLP handler for shipping logs to any OTLP-compatible backend

## ⚠️ Compatibility Caveats

LogXide prioritizes performance over full stdlib compatibility. Before adopting, note:

- **Custom Python handlers via `addHandler()`** — Accepted; a foreign Python handler runs once on the Python side (no fast-path GIL release). Rust-backed handlers are dispatched once and no longer double-emit or leak to unrelated loggers (fixed in 0.2.0)
- **Subclassing** — `LogRecord` and `Logger` are Rust types and cannot be subclassed
- **pytest** — Use the bundled `caplog_logxide` fixture instead of stdlib `caplog`

For the complete compatibility matrix, see [Compatibility](compatibility.md).

## Installation

=== "pip"

    ```bash
    pip install logxide

    # With Sentry integration
    pip install logxide[sentry]
    ```

=== "uv"

    ```bash
    uv add logxide

    # With Sentry integration
    uv add logxide[sentry]
    ```

## Quick Start

```python
from logxide import logging

def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Root logger usage
    root_logger = logging.getLogger()
    root_logger.info("This is the root logger")

    # Different log levels
    logger = logging.getLogger("example")
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")

    # Logger hierarchy
    parent_logger = logging.getLogger("myapp")
    child_logger = logging.getLogger("myapp.database")

    parent_logger.info("Parent logger message")
    child_logger.info("Child logger message")

    # String formatting
    logger.info("User %s logged in from %s", "alice", "192.168.1.100")
    logger.warning("High memory usage: %d%% (%d MB)", 85, 1024)

    # Ensure all logs are processed before the program exits
    logging.flush()

if __name__ == "__main__":
    main()
```
