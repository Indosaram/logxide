# Welcome to LogXide

LogXide is a high-performance logging library for Python, delivering exceptional performance through its native Rust implementation. It provides a familiar logging API but prioritizes **performance over full compatibility**.

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

- **High Performance**: Rust-powered logging with exceptional throughput
- **Familiar API**: Similar to Python's logging module (not a drop-in replacement)
- **Thread-Safe**: Complete support for multi-threaded applications
- **Direct Processing**: Efficient log message processing with native Rust handlers (file I/O synchronous, stream/HTTP/OTLP non-blocking)
- **Rich Formatting**: All Python logging format specifiers with advanced features
- **Level Filtering**: Hierarchical logger levels with inheritance
- **Sentry Integration**: Automatic error tracking with Sentry (optional)

## ⚠️ Important: Not a Drop-in Replacement

LogXide is **NOT** a drop-in replacement for Python's logging module. Key limitations:

- **Rust handlers only**: `addHandler()` accepts only LogXide's Rust handlers
- **No custom Python handlers**: `logging.Handler` subclasses are rejected
- **No subclassing**: `LogRecord` and `Logger` are Rust types
- **No pytest caplog**: Use `caplog_logxide` fixture instead

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
