# Welcome to Logxide

Logxide is a high-performance, Rust-powered, drop-in replacement for Python's standard logging module. It's designed to be fast, thread-safe, and easy to use, providing a familiar API for Python developers while leveraging the power of Rust for performance-critical logging operations.

## Key Features

- 🚀 **High Performance**: Asynchronous logging powered by Rust and the Tokio runtime for non-blocking I/O.
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

Using Logxide is as simple as replacing `import logging` with `from logxide import logging`.

Here's a basic example to get you started:

```python
from logxide import logging

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
