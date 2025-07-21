# Welcome to LogXide

LogXide is a high-performance, Rust-powered, drop-in replacement for Python's standard logging module. It's designed to be fast, thread-safe, and easy to use, providing a familiar API for Python developers while leveraging the power of Rust for performance-critical logging operations.

## Documentation

### Getting Started
- **[Installation Guide](installation.md)** - Installation and setup instructions
- **[Usage Guide](usage.md)** - Complete usage examples and API guide

### Integrations
- **[Framework Integration](integration.md)** - Flask, Django, and FastAPI integration
- **[Sentry Integration](sentry.md)** - Automatic error tracking with Sentry

### Performance & Architecture
- **[Performance Benchmarks](benchmarks.md)** - Comprehensive performance analysis and comparisons
- **[Architecture](architecture.md)** - Technical architecture and design details

### Development
- **[Development Guide](development.md)** - Contributing and development setup
- **[API Reference](reference.md)** - Complete API documentation

## Key Features

- **고성능**: Rust와 Tokio 런타임으로 구동되는 비동기 로깅은 비블로킹 I/O를 제공하여 높은 성능을 자랑합니다.
- 🔄 **Drop-in Replacement**: Fully compatible with the `logging` module's API. You can switch to Logxide with minimal code changes.
- 🧵 **Thread-Safe**: Designed from the ground up for multi-threaded applications, with features to make thread-based logging easier.
- 📝 **Rich Formatting**: Supports all standard Python logging format specifiers, plus advanced features like padding and alignment.
- ⚡ **Async Processing**: Log messages are processed in the background, so your application's main thread isn't blocked.
- 🎯 **Level Filtering**: Hierarchical loggers with level filtering and inheritance, just like the standard library.
- 🔧 **Configurable**: Flexible configuration options to tailor logging to your needs.

## Installation

You can install Logxide via pip:

```bash
pip install logxide
```

## Quick Start

Using Logxide is as simple as replacing `import logging` with `from logxide import logging`. **No manual installation required** - LogXide automatically integrates when imported!

Here's a basic example to get you started:

```python
from logxide import logging  # Auto-installs LogXide - no setup needed!

def main():
    # Configure logxide with basic settings
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # 1. Root logger usage
    root_logger = logging.getLogger()
    root_logger.info("This is the root logger")

    # 2. Different log levels
    logger = logging.getLogger("example")
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")

    # 3. Logger hierarchy
    parent_logger = logging.getLogger("myapp")
    child_logger = logging.getLogger("myapp.database")
    grandchild_logger = logging.getLogger("myapp.database.connection")

    parent_logger.info("Parent logger message")
    child_logger.info("Child logger message")
    grandchild_logger.info("Grandchild logger message")

    # 4. String formatting
    logger.info("User %s logged in from %s", "alice", "192.168.1.100")
    logger.warning("High memory usage: %d%% (%d MB)", 85, 1024)
    logger.error("Connection timeout after %d seconds", 30)

    # Ensure all logs are processed before the program exits
    logging.flush()

if __name__ == "__main__":
    main()
```

This example demonstrates basic configuration, logging at different levels, using the logger hierarchy, and string formatting, all with an API that is identical to the standard `logging` module.
