# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.21] - 2026-06-15

### Security
- **Upgraded `pyo3` from 0.28.2 to 0.29.0** to address two newly disclosed advisories:
  - **RUSTSEC-2026-0176**: out-of-bounds read in `nth` / `nth_back` for `PyList` / `PyTuple` iterators.
  - **RUSTSEC-2026-0177**: missing `Sync` bound on `PyCFunction::new_closure` closures (not used by LogXide, but the workspace audit failed regardless).
  - Both advisories were published 2026-06-11, the day after the v0.1.20 release. v0.1.20 inherits the same upstream vulnerability surface; this release closes both.
- The pyo3 0.28 → 0.29 upgrade was source-compatible (zero LogXide changes required).
- `cargo audit` is now clean except for one allowed transitive `rand 0.8.5` advisory (RUSTSEC-2026-0097) reaching us via `opentelemetry-proto`'s tonic stack — unsoundness only manifests with a custom `rand::rng()` logger which LogXide does not configure.

### Verification
- 306/306 pytest cases still passing.
- Microbenchmark throughput unchanged from v0.1.20 (statistical noise band):
  - FileHandler info()+fmt: 1,324,414 ops/s
  - MemoryHandler info(): 504,175 ops/s
  - info() with `%s` args: 358,117 ops/s

## [0.1.20] - 2026-06-15

### Performance
- **Release profile tuning**: Added `[profile.release]` with `lto = "fat"`, `codegen-units = 1`, `panic = "abort"`, `strip = "symbols"`. Enables cross-crate inlining throughout the hot path.
- **Lock-free handler registry**: Replaced the global `parking_lot::RwLock<Vec<Arc<Handler>>>` with `arc_swap::ArcSwap<Vec<Arc<Handler>>>`. Reads on every record dispatch are now lock-free; registration uses copy-on-write through a `push_handler` helper.
- **Lock-free formatter slot**: Each handler now stores its formatter in `parking_lot::Mutex<Arc<dyn Formatter>>` with a `NoOpFormatter` sentinel as the default, eliminating the per-emit `Mutex<Option<...>>` branch.
- **Zero-allocation formatter hot path**: `PythonFormatter::format` now uses `itoa::Buffer` for integer fields and `write!` macros for padding, removing `to_string()` and `format!()` allocations from every record. Asctime is computed lazily only when `%(asctime)s` appears in the format string.
- **Thread-local formatter scratch buffer**: Reuses a per-thread `String` across calls (capacity is preserved between records). Includes a `try_borrow_mut()` reentrancy guard for recursive logging triggered by user-defined `__str__`.
- **`chrono::Utc::now()` in record creation**: Removes the per-record timezone lookup; the `created` field is timezone-independent epoch seconds. Local-time conversion happens lazily inside the formatter only when needed.
- **Cached thread/process IDs**: Thread ID is parsed from `ThreadId` Debug format once per thread via `thread_local!`. Process ID is cached via `OnceLock`. Eliminates per-record `format!()` + `parse::<u64>()` round-trip and `process::id()` syscall.
- **Const `LogLevel::as_str()`**: Returns `&'static str` (`"DEBUG"`, `"INFO"`, ...) for level names, replacing the self-defeating string interning cache.
- **Caller-info batched via Python helper**: New `_get_caller_info()` in `logxide.compat_functions` returns `(filename, funcName, lineno)` from a single `_getframe` call. Rust caches the helper in `OnceLock<Py<PyAny>>`, replacing 6+ `getattr` round-trips per record. Activated only when `CALLER_INFO_REQUIRED` is set by the format string.
- **`LogRecord.args` zero-copy storage**: Field type changed from `Option<String>` (JSON-encoded) to `Option<Arc<serde_json::Value>>`. Eliminates `serde_json::to_string` on write and `serde_json::from_str` on read for every record carrying `%`-args.
- **`parking_lot::Mutex` on hot-path locks**: Replaced `std::sync::Mutex` for `BufWriter`, formatter slot, and record buffer.

### Removed
- **Dead `regex` dependency**: removed `regex = "1.5"` from `Cargo.toml`. The formatter has used a single-pass parser since 0.1.19.
- **Dead `string_cache` module**: deleted `src/string_cache.rs`. The intern cache returned `Arc<str>` immediately followed by `.to_string()` at every call site, allocating regardless and defeating the cache.

### Wire format
- **HTTP/OTLP `args` field**: Now serialized as the actual JSON value (e.g. `"args": ["alice", 42]`) rather than as a JSON-encoded string (`"args": "[\"alice\", 42]"`). Receivers that decoded the field as a string will see structured data; receivers that already JSON-decoded the entire payload will see no escape change. No tests in this repository depended on the previous escaped-string form.

### Benchmarks
LogXide self-throughput (Python 3.14, macOS arm64, FileHandler + `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"` formatter, 200K iter × 5 runs):

| Scenario              | v0.1.19 baseline | Unreleased | Gain    |
| :-------------------- | ---------------: | ---------: | :------ |
| FileHandler info()    |          720,099 |  1,357,691 | **+88.5%** |
| MemoryHandler info()  |          394,227 |    513,373 | +30.2%  |
| Filtered debug NOOP   |          24.3M   |    28.2M   | +15.9%  |
| info() with `%s` args |          280,473 |    357,320 | +27.4%  |
| FileHandler 4 threads |          299,841 |    388,971 | +29.8%  |

Versus Python stdlib `logging` (subprocess, 100K iter × 3 runs, FileHandler):

| Scenario   | logxide   | stdlib    | speedup    |
| :--------- | --------: | --------: | :--------- |
| simple     | 1,228,811 |   182,533 | **6.73×** |
| structured | 1,064,164 |   177,366 | **6.00×** |
| args       |   750,129 |   176,633 | **4.25×** |

## [0.1.19] - 2026-05-27

### Performance
- **Message cache dead state removal (Step 1)**: Removed dead string-caching states and redundant message-text cache checks from the string cache flow.
- **Canonical `py_to_json_value` single helper path (Step 2)**: Consolidated Python-to-JSON parameter mapping (including `PyTuple`/`PyList` to JSON array conversion) into a single `py_to_json_value` helper in `src/py_logger.rs`.
- **Direct ANSI color support in `RustFormatter` (Step 3)**: Added native handling of `%(ansi_level_color)s` and `%(ansi_reset_color)s` placeholders inside `RustFormatter` (and by extension `Formatter`), so terminal coloring no longer requires the `ColorFormatter` wrapper on the hot path.
- **Single-pass formatter parser**: Replaced the previous regex-based formatter field parsing on the hot path with a single-pass O(N) parser. The `regex` crate is no longer used inside the active formatting path.

### Changed
- **Compat handler caller-info activation (Step 4)**: When formatters configured through `logxide/compat_handlers.py` reference caller-info placeholders (such as `%(funcName)s`, `%(pathname)s`, `%(lineno)d`), the `activate_caller_info` layer is connected dynamically so that stack-frame introspection only runs when needed.

### Added
- Regression suite (`tests/test_optimizations.py`) covering the Step 1–4 changes.

## [0.1.18] - 2026-05-27

### Added
- **Official Python 3.15 Support**: Fully verified and integrated Python 3.15 support.
- Added native PyO3 `emit()` method overrides to core Rust handler classes (`PyFileHandler`, `PyStreamHandler`, `PyRotatingFileHandler`, `PyHTTPHandler`, `PyOTLPHandler`, `PyMemoryHandler`) to enable standard-to-native record passing.
- Added comprehensive comparison and compatibility pages (stdlib, structlog, picologging) to MkDocs navigation.
- Documented missing API items (MemoryHandler, ColorFormatter, testing guide, FastLoggerWrapper).

### Fixed
- **Rust Mutex & Python GIL Deadlock Fix**: Resolved a critical cross-deadlock in logger `emit`, `flush`, `handle`, and `filter` paths.
- **Resolved 14 Pre-Existing Test Failures**:
  - Implemented `_prepare_record_for_rust(record)` in `logxide/handlers.py` to fix compatibility with `logging.config.dictConfig` (resolving 2 config test failures).
  - Resolved `OTLPHandler` positional constructor argument mismatch by utilizing explicit keyword parameters.
  - Rectified documentation code block syntax errors by wrapping asynchronous snippets in executable definitions.
  - Adjusted `capture_logs()` context manager example assertions to reside inside the context blocks, ensuring records are tested prior to context teardown/clearing.
- Fixed HTTP server deadlocks and Sentry thread leaks in unit test suites.
- Resolved Windows encoding issues and Clippy warnings for Rust 1.88.0.

### Performance
- Cached formatter field regular expressions to reduce parsing overhead during formatting.

### Security
- Upgraded `rustls-webpki` to address RUSTSEC-2026-0049 vulnerability.

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
