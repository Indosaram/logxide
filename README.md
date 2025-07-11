# LogXide

A high-performance, Rust-powered drop-in replacement for Python's logging module.

## Features

- 🚀 **High Performance**: Async logging powered by Rust and Tokio
- 🔄 **Drop-in Replacement**: Compatible with Python's logging module API
- 🧵 **Thread-Safe**: Full support for multi-threaded applications
- 📝 **Rich Formatting**: All Python logging format specifiers with advanced features
- ⚡ **Async Processing**: Non-blocking log message processing
- 🎯 **Level Filtering**: Hierarchical logger levels with inheritance
- 🔧 **Configurable**: Flexible configuration options

## Installation

### From PyPI (Recommended)

Install LogXide from PyPI using pip:

```bash
pip install logxide
```

### Quick Start

```python
import logxide
logxide.install()  # Make logxide the default logging module

# Now use logging as normal
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("Hello from LogXide!")
```

### Development Setup

For development or building from source:

1. Install `maturin` to build the Python package:

```bash
uv venv
source .venv/bin/activate
uv pip install maturin
```

2. Build and install the package:

```bash
maturin develop
```

## Usage

LogXide can be used as a direct replacement for Python's logging module:

```python
from logxide import logging

# Configure logging (just like Python's logging)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create and use loggers
logger = logging.getLogger('myapp')
logger.info('Hello from LogXide!')
logger.warning('This is a warning')
logger.error('This is an error')
```

### Advanced Formatting

LogXide supports all Python logging format specifiers plus advanced features:

```python
# Multi-threaded format with padding
logging.basicConfig(
    format='[%(asctime)s] %(threadName)-10s | %(name)-15s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)

# JSON-like structured logging
logging.basicConfig(
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S'
)

# Production format with process and thread IDs
logging.basicConfig(
    format='%(asctime)s [%(process)d:%(thread)d] %(levelname)s %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
```

### Thread Support

LogXide provides enhanced thread support:

```python
import threading
from logxide import logging

def worker(worker_id):
    # Set thread name for better logging
    logging.set_thread_name(f'Worker-{worker_id}')

    logger = logging.getLogger(f'worker.{worker_id}')
    logger.info(f'Worker {worker_id} starting')
    # ... do work ...
    logger.info(f'Worker {worker_id} finished')

# Configure format to show thread names
logging.basicConfig(
    format='%(threadName)-10s | %(name)s | %(message)s'
)

# Start workers
threads = []
for i in range(3):
    t = threading.Thread(target=worker, args=[i])
    threads.append(t)
    t.start()

for t in threads:
    t.join()
```

### Flush Support

Ensure all log messages are processed:

```python
logger.info('Important message')
logging.flush()  # Wait for all async logging to complete
```

## Supported Format Specifiers

LogXide supports all Python logging format specifiers:

| Specifier | Description |
|-----------|-------------|
| `%(asctime)s` | Timestamp |
| `%(name)s` | Logger name |
| `%(levelname)s` | Log level (INFO, WARNING, etc.) |
| `%(levelno)d` | Log level number |
| `%(message)s` | Log message |
| `%(thread)d` | Thread ID |
| `%(threadName)s` | Thread name |
| `%(process)d` | Process ID |
| `%(msecs)d` | Milliseconds |
| `%(pathname)s` | Full pathname |
| `%(filename)s` | Filename |
| `%(module)s` | Module name |
| `%(lineno)d` | Line number |
| `%(funcName)s` | Function name |

### Advanced Formatting Features

- **Padding**: `%(levelname)-8s` (left-align, 8 chars)
- **Zero padding**: `%(msecs)03d` (3 digits with leading zeros)
- **Custom date format**: `datefmt='%Y-%m-%d %H:%M:%S'`

## Testing

LogXide includes a comprehensive test suite:

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=logxide --cov-report=term-missing

# Run specific test categories
pytest tests/ -m unit           # Unit tests only
pytest tests/ -m integration    # Integration tests only
pytest tests/ -m threading      # Threading tests only
pytest tests/ -m "not slow"     # Exclude slow tests

# Parallel execution for faster testing
pytest tests/ -n auto
```

### Test Categories

- **Unit Tests**: Basic functionality, API compatibility
- **Integration Tests**: Real-world scenarios, drop-in replacement testing
- **Threading Tests**: Multi-threaded logging, thread safety
- **Formatting Tests**: Format specifiers, padding, date formatting
- **Performance Tests**: High-throughput scenarios, stress testing

## Examples

Check out the `examples/` directory for comprehensive usage examples:

- `examples/minimal_dropin.py`: Complete formatting demonstration
- `examples/format_*.py`: Individual format examples

Run the main example to see all formatting options:

```bash
python examples/minimal_dropin.py
```

## Performance

LogXide is designed for high-performance logging:

- **Async Processing**: Non-blocking log message handling
- **Rust Backend**: Native performance for formatting and I/O
- **Thread-Safe**: Efficient concurrent logging
- **Memory Efficient**: Minimal allocation overhead

Run benchmarks:

```bash
python benchmark.py
```

## Development

### Building from Source

```bash
# Install development dependencies
uv pip install maturin pytest pytest-cov

# Build in development mode
maturin develop

# Build release version
maturin build --release
```

### Running Tests

```bash
# Install test dependencies
uv pip install pytest pytest-cov pytest-xdist

# Run test suite
pytest tests/ -v

# Generate coverage report
pytest tests/ --cov=logxide --cov-report=html
```

### Project Structure

```
logxide/
├── src/                    # Rust source code
│   ├── lib.rs             # Python bindings
│   ├── core.rs            # Core logging types
│   ├── handler.rs         # Log handlers
│   ├── formatter.rs       # Format processing
│   └── ...
├── logxide/               # Python package
│   └── __init__.py        # Python API
├── tests/                 # Test suite
│   ├── test_basic_logging.py
│   ├── test_integration.py
│   └── README.md
├── examples/              # Usage examples
└── benchmark/             # Performance benchmarks
```

## API Compatibility

LogXide aims for 100% compatibility with Python's logging module:

- ✅ Logger creation and hierarchy
- ✅ Log levels and filtering
- ✅ Format specifiers and date formatting
- ✅ Basic configuration
- ✅ Thread safety
- ✅ Flush functionality

## License

[Add your license information here]

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `pytest tests/`
5. Submit a pull request

## Roadmap

- [ ] Handler customization support
- [ ] Filter support
- [ ] Configuration file support
- [ ] Structured logging enhancements
- [ ] Performance optimizations

## Requirements

- Python 3.9+
- Rust 1.70+ (for building from source only)

## Project Status

LogXide is currently in **beta** status. The core functionality is stable and ready for production use, but some advanced features are still being developed.

### What's Working
- ✅ Drop-in replacement for Python logging
- ✅ All Python logging format specifiers
- ✅ Async processing for high performance
- ✅ Thread-safe logging
- ✅ Hierarchical loggers
- ✅ Level filtering and inheritance
- ✅ Custom handlers and formatters
- ✅ Comprehensive test suite

### Coming Soon
- 🔄 Configuration file support (YAML/JSON)
- 🔄 More built-in handlers (file, network, etc.)
- 🔄 Advanced filtering capabilities
- 🔄 Structured logging enhancements
- 🔄 Performance monitoring tools

## PyPI Package

LogXide is available on PyPI: https://pypi.org/project/logxide/

Package information:
- **Package name**: `logxide`
- **Current version**: 0.1.0
- **License**: MIT
- **Python versions**: 3.9, 3.10, 3.11, 3.12, 3.13
- **Platforms**: Windows, macOS, Linux
