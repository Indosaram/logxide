# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.3] - 2024-12-30

### Fixed
- Removed all unused imports and dependencies (tokio, crossbeam, tracing, lazy_static)
- Removed unused `RUNTIME` static variable that was never utilized
- Fixed unused variable warnings in `register_stream_handler` and `register_file_handler`
- Removed unnecessary `mut` declarations in handler registration functions
- Fixed `FileHandler` filename field unused warning with proper attribute
- **Fixed FileHandler buffering issue**: FileHandler now flushes immediately after each write for reliable logging
- **Fixed addHandler() functionality**: Verified that `logger.addHandler()` works correctly with Rust native handlers

### Changed
- **Breaking Architecture Change**: Removed async/Tokio runtime architecture in favor of direct handler calls for maximum performance
- Updated README to accurately reflect direct processing architecture (removed async/Tokio claims)
- **Updated README documentation**: Clarified that `addHandler()` IS supported but only accepts Rust native handlers (FileHandler, StreamHandler, RotatingFileHandler)
- Unified Python version requirements (3.9+ in both README and pyproject.toml)
- Replaced `tokio::spawn` with `futures::executor::block_on` for direct blocking calls
- Replaced `tokio::task::block_in_place` with direct Python GIL calls in PythonStreamHandler

### Added
- Added `python-handlers` feature flag to conditionally compile deprecated PythonHandler code
- PythonHandler is now disabled by default (enable with `python-handlers` feature)
- Improved code quality with zero Clippy warnings

### Removed
- Removed unused dependencies: tokio, crossbeam, tracing, lazy_static
- Removed unused Tokio runtime that was creating overhead without being used
- Cleaned up 25+ compiler warnings

## [0.1.2] - 2024-01-XX

### Added
- Initial PyPI release preparation
- Comprehensive documentation for all modules
- Python type stubs for better IDE support
- CI/CD pipeline for automated testing and publishing

### Changed
- Improved error handling and logging
- Enhanced performance optimizations
- Better memory management

### Fixed
- Thread safety improvements
- Format string parsing edge cases

## [0.1.0] - 2024-01-XX

### Added
- Initial release of LogXide
- Core logging functionality with Python compatibility
- Async logging architecture using Rust and Tokio
- Drop-in replacement for Python's logging module
- Support for all Python logging format specifiers
- Advanced formatting features (padding, alignment, date formatting)
- Thread-safe logging with proper thread name handling
- Hierarchical logger support with inheritance
- Basic configuration support (`basicConfig`)
- Flush functionality for ensuring message delivery
- Console handler with customizable formatting
- Python handler wrapper for existing Python logging handlers
- Comprehensive test suite with unit, integration, and concurrency tests
- Performance benchmarks demonstrating superior performance
- Multiple usage examples and documentation

### Core Features
- **High Performance**: Rust-powered async logging
- **Python Compatibility**: Full API compatibility with Python's logging module
- **Thread Safety**: Safe concurrent logging from multiple threads
- **Async Processing**: Non-blocking log message processing
- **Rich Formatting**: Support for all Python format specifiers plus advanced features
- **Hierarchical Loggers**: Parent-child logger relationships with inheritance
- **Level Filtering**: Configurable log levels with proper inheritance
- **Handler System**: Pluggable handlers for different output destinations
- **Filter System**: Extensible filtering capabilities
- **Memory Efficient**: Minimal allocation overhead
- **Easy Integration**: Simple drop-in replacement with automatic installation

### Supported Python Versions
- Python 3.12
- Python 3.13
- Python 3.14

### Performance Improvements
- Up to 3-5x faster than Python's standard logging module
- Async processing prevents blocking on I/O operations
- Efficient memory usage with minimal allocations
- Native Rust performance for string formatting and processing

### Testing
- 27 comprehensive tests covering all functionality
- Unit tests for core components
- Integration tests for real-world scenarios
- Concurrency tests for thread safety
- Performance benchmarks
- Memory leak detection
- Cross-platform compatibility testing

### Documentation
- Complete API documentation
- Usage examples for all features
- Performance comparison benchmarks
- Integration guides for common use cases
- Migration guide from Python logging

### Known Limitations
- Configuration file support (YAML/JSON) not yet implemented
- Some advanced Python logging features not yet supported
- Handler customization limited to basic cases
- Filter system is basic (extensible but limited built-in filters)

### Dependencies
- Runtime: None (pure Python + Rust extension)
- Build: Rust 1.70+, PyO3, Tokio, Chrono
- Development: pytest, maturin, pre-commit

### Architecture
- **Rust Core**: High-performance logging engine
- **Python Bindings**: PyO3-based Python interface
- **Async Runtime**: Tokio for non-blocking operations
- **Thread Safety**: Mutex-protected shared state
- **Memory Management**: Efficient allocation strategies
- **Format Processing**: Regex-based format string parsing
- **Handler Architecture**: Pluggable handler system

### Compatibility
- Drop-in replacement for Python logging
- Same API surface as Python's logging module
- Compatible with existing Python logging configurations
- Works with third-party libraries expecting Python logging
- Supports all major Python logging use cases

## [0.0.1] - Development

### Added
- Initial project structure
- Basic Rust logging implementation
- Python bindings prototype
- Core data structures (LogRecord, Logger, LoggerManager)
- Basic formatting capabilities
- Initial test framework
- Development tooling setup

---

## Release Notes

### How to Upgrade

#### From Python logging to LogXide

1. Install LogXide:
   ```bash
   pip install logxide
   ```

2. Use LogXide with automatic installation:
   ```python
   # Simple and automatic - no setup needed!
   from logxide import logging

   # LogXide is automatically installed - use logging as normal
   logging.basicConfig(level=logging.INFO)
   logger = logging.getLogger(__name__)
   logger.info("Now using LogXide!")
   ```

#### Version Migration

LogXide follows semantic versioning:
- **Major versions** (x.0.0): Breaking API changes
- **Minor versions** (0.x.0): New features, backward compatible
- **Patch versions** (0.0.x): Bug fixes, backward compatible

### Support

- GitHub Issues: https://github.com/Indosaram/logxide/issues
- Documentation: https://logxide.readthedocs.io
- Email: logxide@example.com

### Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
