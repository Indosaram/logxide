# LogXide 🚀

**High-Performance Rust-Powered Logging for Python**

LogXide is a drop-in replacement for Python's standard logging module, delivering **4x faster** performance than Picologging and **10x faster** than standard logging through its async Rust implementation.

## 🏆 Performance Benchmarks

### Python 3.12.6 - Complete Comparison (with Picologging)

#### FileHandler Performance
| Rank | Library | Messages/sec | Relative Performance | Speedup vs Baseline |
|------|---------|-------------|---------------------|---------------------|
| 🥇 | **LogXide** | **1,812,360** | **1.00x** | **11.2x faster** |
| 🥈 | Structlog | 1,169,416 | 0.65x | 7.2x faster |
| 🥉 | Picologging | 446,114 | 0.25x | 2.8x faster |
| 4th | Python logging | 162,202 | 0.09x | 1.0x (baseline) |
| 5th | Logbook | 122,780 | 0.07x | 0.8x |
| 6th | Loguru | 114,804 | 0.06x | 0.7x |

#### StreamHandler Performance
| Rank | Library | Messages/sec | Relative Performance | Speedup vs Baseline |
|------|---------|-------------|---------------------|---------------------|
| 🥇 | **LogXide** | **1,874,053** | **1.00x** | **10.2x faster** |
| 🥈 | Structlog | 1,182,965 | 0.63x | 6.4x faster |
| 🥉 | Picologging | 802,598 | 0.43x | 4.4x faster |
| 4th | Python logging | 184,000 | 0.10x | 1.0x (baseline) |
| 5th | Logbook | 147,733 | 0.08x | 0.8x |
| 6th | Loguru | 134,015 | 0.07x | 0.7x |

#### RotatingFileHandler Performance
| Rank | Library | Messages/sec | Relative Performance | Speedup vs Baseline |
|------|---------|-------------|---------------------|---------------------|
| 🥇 | **LogXide** | **1,747,599** | **1.00x** | **16.9x faster** |
| 🥈 | Picologging | 435,633 | 0.25x | 4.2x faster |
| 3rd | Python logging | 103,097 | 0.06x | 1.0x (baseline) |
| 4th | Loguru | 94,641 | 0.05x | 0.9x |

### Python 3.13.3 - Modern Python Comparison (Picologging unavailable)

#### FileHandler Performance
| Rank | Library | Messages/sec | Relative Performance | Speedup vs Baseline |
|------|---------|-------------|---------------------|---------------------|
| 🥇 | **LogXide** | **1,783,794** | **1.00x** | **10.0x faster** |
| 🥈 | Structlog | 1,308,972 | 0.73x | 7.3x faster |
| 3rd | Python logging | 178,438 | 0.10x | 1.0x (baseline) |
| 4th | Logbook | 145,150 | 0.08x | 0.8x |
| 5th | Loguru | 134,083 | 0.08x | 0.8x |

#### StreamHandler Performance
| Rank | Library | Messages/sec | Relative Performance | Speedup vs Baseline |
|------|---------|-------------|---------------------|---------------------|
| 🥇 | **LogXide** | **1,827,908** | **1.00x** | **8.7x faster** |
| 🥈 | Structlog | 1,332,231 | 0.73x | 6.3x faster |
| 3rd | Python logging | 210,304 | 0.12x | 1.0x (baseline) |
| 4th | Logbook | 184,026 | 0.10x | 0.9x |
| 5th | Loguru | 162,295 | 0.09x | 0.8x |

#### RotatingFileHandler Performance
| Rank | Library | Messages/sec | Relative Performance | Speedup vs Baseline |
|------|---------|-------------|---------------------|---------------------|
| 🥇 | **LogXide** | **1,679,731** | **1.00x** | **13.6x faster** |
| 2nd | Python logging | 123,291 | 0.07x | 1.0x (baseline) |
| 3rd | Loguru | 112,158 | 0.07x | 0.9x |

*Note: Picologging unavailable in Python 3.13+*

## 🎯 Key Performance Highlights

- **🏆 4.0x faster than Picologging** - Beats the fastest Cython-based logging library
- **🏆 1.5x faster than Structlog** - Outperforms the leading structured logging library
- **🏆 #1 in ALL handler types** - FileHandler, StreamHandler, and RotatingFileHandler
- **🏆 17x faster than Python logging** - Massive improvement over standard library (RotatingFileHandler)
- **🚀 1.7M+ messages/sec** - Exceptional throughput for high-performance applications
- **⚡ Async architecture** - Non-blocking message processing with Tokio runtime
- **🔧 Drop-in replacement** - Full compatibility with Python's logging API

## 🛠️ Architecture

LogXide leverages Rust's performance and safety with Python's ease of use:

- **Async Message Processing**: Non-blocking with 1024-capacity channels
- **Tokio Runtime**: Dedicated thread pool for log processing
- **PyO3 Integration**: Zero-copy data transfer between Python and Rust
- **Concurrent Handlers**: Parallel execution for maximum throughput
- **Memory Efficient**: Rust's ownership system prevents memory leaks

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

## 🔬 Benchmark Methodology

**Test Environment:**
- Platform: macOS 15.5 ARM64 (Apple Silicon)
- Python: 3.12.6 and 3.13.3
- Test: 10,000 messages, 3 runs with averages
- Handlers: FileHandler and StreamHandler with full formatting
- Methodology: End-to-end logging including message formatting and I/O

**Run Benchmarks Yourself:**

```bash
# Python 3.12 (with Picologging)
python3.12 benchmark/basic_handlers_benchmark.py

# Python 3.13 (without Picologging due to compatibility)
python3.13 benchmark/basic_handlers_benchmark.py

# Direct LogXide vs Picologging comparison
python3.12 test_comparison.py
```

## ⚡ Technical Performance Details

### Message Processing Flow
1. **Python Call** → LogXide PyLogger methods
2. **Record Creation** → Rust LogRecord with full metadata
3. **Async Channel** → Non-blocking `try_send()` to Tokio runtime
4. **Concurrent Processing** → Multiple handlers execute in parallel
5. **Output** → Formatted messages to files/streams/handlers

### Performance Optimizations
- **Zero-allocation message passing** in common cases
- **Batch processing** of log records in async runtime
- **Lock-free channels** for Python→Rust communication
- **Efficient string formatting** with Rust's formatter
- **Memory pool reuse** for log record objects

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

## 🎯 Use Cases

**High-Performance Applications:**
- Web servers handling thousands of requests/second
- Data processing pipelines with heavy logging
- Real-time analytics systems
- Microservices with high logging volume
- Game servers and real-time applications

**Drop-in Upgrades:**
- Existing applications using Python logging
- Third-party libraries (requests, SQLAlchemy, FastAPI, etc.)
- Legacy codebases needing performance boosts
- Applications transitioning to Python 3.13+

## 📈 Roadmap

- [x] RotatingFileHandler implementation ✅
- [ ] Additional file handlers (TimedRotatingFileHandler, WatchedFileHandler)
- [ ] Custom formatter performance optimizations
- [ ] Structured logging (JSON) support
- [ ] AsyncIO integration improvements
- [ ] Memory usage optimizations
- [ ] Cross-platform performance tuning
- [ ] Configuration file support (YAML/JSON)
- [ ] Advanced filtering capabilities

## 📊 Compatibility

- **Python**: 3.12+ (3.13+ recommended)
- **Platforms**: macOS, Linux, Windows
- **API**: Full compatibility with Python's `logging` module
- **Dependencies**: None (Rust compiled into native extension)

## ⚡ Why LogXide?

**Performance**: 4x faster than Picologging, 10x faster than standard logging

**Reliability**: Rust's memory safety prevents crashes and leaks

**Compatibility**: Drop-in replacement - no code changes required

**Modern**: Async architecture ready for Python 3.13+ and beyond

**Proven**: Comprehensive benchmarks against all major logging libraries

---

**LogXide delivers the performance you need without sacrificing the Python logging API you know.**

*Built with 🦀 Rust and ❤️ for high-performance Python applications.*
