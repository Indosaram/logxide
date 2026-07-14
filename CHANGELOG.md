# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.2] - 2026-07-14

### Performance
- **Skip `str()` coercion when the log message is already a `str` (M3).** The hot
  path previously called `PyObject_Str` on every `logger.info(...)` even when the
  message was already a `str`; it now reads the UTF-8 directly for exact-`str`
  messages (guarded by an exact-type check so `str` subclasses and non-`str`
  objects still coerce via `str()` exactly as before).
- **Per-second `asctime` cache (M4).** For the default date format
  (`%Y-%m-%d %H:%M:%S`, no sub-second field), the formatted timestamp prefix is
  cached per thread per epoch-second — byte-identical output, but avoids
  re-running the chrono local-time conversion on every record. Custom `datefmt`
  (which may contain `%f`) is never cached and takes the exact original path.
- Least-noisy microbench scenarios improved with no regression anywhere
  (structured ~216K→~307K rec/s, `%`-args ~142K→~204K rec/s on the reference
  machine; machine-specific).
- **Deferred (M2):** a Rust-native caller-frame walk was evaluated and NOT done —
  low payoff now that caller-info is rarely enabled (post-0.2.1), and `PyFrame`/
  `f_lineno` C-API internals differ across CPython 3.12/3.13/3.14 (correctness
  risk). `populate_caller_info` is unchanged.

### Documentation
- **Corrected the "drop-in replacement" overstatement.** README, the package
  description, `logxide/__init__.py`, docs, and the blog drafts no longer claim a
  flat "drop-in replacement for Python's logging"; they now say **near-drop-in for
  common patterns** and link the compatibility notes documenting the differences
  (flush drains/waits, no `LogRecord`/`Logger` subclassing, custom `Formatter`
  subclasses fall back to a slower path, changed async-overflow default).
- Blog drafts: replaced the debunked `13.21×` / `1.9M rec/s` single-machine table
  with honest sink-verified ranges and the 3.12≈3.14 parity note.

### CI
- Added `.github/workflows/benchmark.yml` — a manual/weekly, environment-matched
  (clean, no `sentry-sdk`) benchmark run across Python 3.12 and 3.14 that uploads
  sink-verified results as artifacts, so the published numbers are reproducible
  rather than single-machine.

## [0.2.1] - 2026-07-14

### Fixed
- **Merely installing `sentry-sdk` no longer taxes every log call (~20%) — completes
  the P1-1 fix.** In 0.2.0, importing `sentry-sdk` (even with no DSN / no active
  client) pulled in `urllib3`, which registers a formatter-less
  `logging.NullHandler`. That handler hit 0.2.0's "conservative default = require
  caller-info when a foreign handler's formatter is not inspectable", flipping the
  process-global caller-frame flag on and running `sys._getframe().f_lineno` on
  every record. Root-caused by comparative profiling (the frame lookup was
  ~22–35% of hot-path CPU on CPython 3.14).
  - Foreign handlers now force caller-info **only** when their formatter demonstrably
    references a caller field (`%(pathname)s` / `%(filename)s` / `%(module)s` /
    `%(lineno)s` / `%(funcName)s`); a formatter-less or non-inspectable handler no
    longer forces it (performance-safe default).
  - A **configured** Sentry handler still activates caller-info explicitly (it
    forwards caller frames to Sentry), and formatters that genuinely use caller
    fields still populate `pathname`/`lineno`/`funcName` as before.
  - This also corrects a benchmarking pitfall: a 3.12-vs-3.14 comparison run with
    `sentry-sdk` present in only one environment showed a spurious ~20% "3.14
    regression". Environment-matched, CPython 3.12 and 3.14 throughput are at
    parity; there is no intrinsic 3.14 regression.

### Notes
- No API or wire-format changes. Behavior change is limited to when caller-frame
  introspection is auto-enabled. 345 tests pass (343 + a new caller-info-scope
  regression test).

## [0.2.0] - 2026-07-13

This release resolves the correctness and performance defects found in the
2026-07-13 bottleneck audit (`docs/performance-bottleneck-report-2026-07-13.md`).
It contains **behavior-breaking changes** (flush semantics and the async overflow
default). Because the project is still `0.x`, these ship in a minor bump; review
the BREAKING section before upgrading.

### Fixed
- **Rust-backed handlers no longer double-emit or leak across loggers (P0-1).** A
  Rust-backed handler was kept in a global keep-alive list that was *also* used as
  the Python dispatch list, so a public handler emitted the owner's record twice
  and unrelated loggers received each other's records; cost scaled O(N) with every
  registered handler (100 handlers → 107x on an unrelated logger). Handler dispatch
  is now routed by backend kind and scoped per logger: structured sinks
  (`HTTPHandler`/`OTLPHandler`) and direct Rust handlers dispatch exactly once via
  their Rust `Arc`; text-sink wrappers (`FileHandler`/`StreamHandler`/
  `RotatingFileHandler`/`MemoryHandler`) and foreign Python handlers dispatch once
  via Python. An owner's single `emit` now delivers exactly one record and unrelated
  loggers receive zero. Keep-alive and dispatch are no longer conflated.
- **`clear_handlers()`/`removeHandler()`/`close()` now fully tear down routing and
  background workers (P0-1).** Clearing/removing a handler drops its `Arc`, and for
  async handlers drains and **joins** the worker thread; previously the global
  keep-alive list retained handlers and worker threads leaked. `PyLogger.removeHandler`
  (previously missing) is implemented.
- **Async queue overflow is now a real, observable policy (P0-2).** `StreamHandler`,
  `HTTPHandler`, and `OTLPHandler` previously ignored `try_send`/`send_timeout(5ms)`
  results and dropped records silently. They now implement the selected
  `OverflowStrategy` and expose payload-free counters via `get_metrics()`
  (`emitted`, `sink_acknowledged`, `queue_dropped`, `delivery_failed`, `in_flight`);
  after a drain, `sink_acknowledged + queue_dropped + delivery_failed == emitted`.
- **`flush()` now drains the queue and waits for sink acknowledgement (P0-2).** The
  worker previously received only one more record on a flush signal before
  signalling completion, so `flush()` did not guarantee delivery. It now drains the
  queue to empty and waits (bounded by a flush timeout) before returning.
- **Direct `HTTPHandler.flush()` no longer deadlocks against the GIL (P0-2).** The
  default HTTP JSON serialization ran inside `Python::attach`, so a GIL-holding
  `flush()` blocked the worker for the full 5s timeout. Default serialization is now
  pure-Rust and runs **outside** the GIL; `flush()`/`shutdown()` release the GIL
  while waiting. The GIL is entered only when a `transform_callback`/
  `context_provider`/`error_callback` is actually configured.
- **Installing (but not configuring) the Sentry SDK no longer forces process-global
  caller-frame collection (P1-1).** Caller-info requirement is now derived from the
  handlers/formatters actually in use and is recomputed when handlers are removed,
  instead of a one-way global flag. This removes the ~2.1x per-log penalty observed
  when `sentry-sdk` was merely importable.
  - **Correction (see 0.2.1):** this fix was **incomplete** in 0.2.0. Importing
    `sentry-sdk` pulls in `urllib3`, which registers a formatter-less
    `logging.NullHandler`; 0.2.0's "conservative default" still forced caller-info
    for such handlers, so the ~20% tax persisted whenever `sentry-sdk` was installed.
    Fully fixed in 0.2.1.

### Performance
- **Enabled logs with no destination do far less work (P1-2).** The Python
  `LogRecord` mirror is now built lazily only when a Python handler will actually be
  dispatched, and unrelated no-handler loggers no longer pay record-construction or
  method-lookup cost.
- **GIL-released producer fast path (P2).** When a log has no Python filters, no
  Python-dispatch handlers, and no caller-info requirement, record creation and Rust
  handler dispatch run inside `py.detach()` (GIL released), allowing genuine
  parallel emission. Logs using `%`-args still re-acquire the GIL for `msg % args`
  formatting and will not fully parallelize until a later release; the shared
  File/Rotating/Memory handler mutex is the next contention point on GIL builds.
- **Formatters parse their format string once (P1-3).** `PythonFormatter` now builds
  a token plan at construction instead of re-parsing the format string on every
  record, and `ColorFormatter` reuses a pre-built inner formatter instead of
  allocating one per call. Output is byte-identical.
- **Text-sink handler wrappers now dispatch through the native Rust path by
  default (performance-first).** `logxide.handlers.FileHandler`/`StreamHandler`/
  `RotatingFileHandler` previously did a Rust→Python→Rust round trip per record
  (~55K rec/s). They now emit directly through their Rust `_inner` on the
  GIL-released fast path, translating a plain `%`-style `logging.Formatter`
  (fmt + datefmt, `%` style) into the Rust formatter. Sink-verified durable
  throughput rises to ~740K–960K rec/s (FILE), ~5–10× the stdlib `logging`
  baseline on the same machine. A handler falls back to the Python path only when
  a custom `Formatter` subclass, a `{`/`$` style, or a handler-level Python filter
  is configured — so `dictConfig`, `caplog`, and custom formatters still work.

### Added
- `get_metrics()` on `HTTPHandler`/`OTLPHandler` (Rust and public wrappers) returning
  `{emitted, sink_acknowledged, queue_dropped, delivery_failed, in_flight}`.
- `overflow=` constructor argument on `HTTPHandler`/`OTLPHandler`
  (`"block"` (default) | `"drop_oldest"` | `"drop_newest"`).

### Changed (BREAKING)
- **`flush()` now blocks until the queue drains and the sink acknowledges** (bounded
  by a flush timeout), rather than returning best-effort immediately. The return type
  is unchanged (`None`), but `logging.shutdown()`/`flush()` may take longer under a
  slow sink. Use `get_metrics()` for explicit accounting.
- **Default async overflow strategy is now `block` (durable).** Under sink saturation
  `HTTPHandler`/`OTLPHandler` apply backpressure instead of silently dropping. Choose
  `overflow="drop_oldest"`/`"drop_newest"` for the previous lossy-but-non-blocking
  behavior; drops are then reported in `get_metrics()["queue_dropped"]`.
- **Handler-level Python filters attached to structured sinks (`HTTPHandler`/
  `OTLPHandler`) are not applied**, because these dispatch via the Rust `Arc` path.
  Filter on the logger instead. (Known limitation, documented.)
- **`__version__` corrected to match the packaged version.** Runtime
  `logxide.__version__` previously reported `0.1.19` while the package was `0.1.22`;
  both are now `0.2.0`.

### Benchmarks / Docs
- The benchmark harness was rewritten to fix credibility defects (per-scenario
  subprocess isolation so stdlib/structlog are not measured inside a logxide-patched
  process; a stream sink that stays open; verified sink-delivery counts; a real
  `RotatingFileHandler` with rotation verification; separate durable-throughput and
  producer p50/p95/p99 latency reporting; async drop/failure/in-flight accounting).
- Documentation was corrected to stop presenting the previously-unverified
  cross-library throughput tables as fact, to accurately scope the GIL-release
  behavior, and to document the new flush/overflow/metrics contracts and Sentry
  auto-detection semantics.

## [0.1.22] - 2026-06-15

### Changed
- **Python 3.15 support claim corrected (docs-only release)**. Previous releases (since v0.1.18) advertised "Python 3.15 fully tested and supported", but direct verification on Python 3.15.0a2 and 3.15.0a7 shows that the compiled extension fails to import at runtime with `ImportError: symbol not found in flat namespace '_PyType_FromSlots'`. The compiled binary references a CPython internal symbol that current 3.15 alpha builds do not export. Build succeeds; runtime `dlopen` fails.
  - **README.md**: Compatibility section now lists 3.12 / 3.13 / 3.14 only and explicitly documents the 3.15 upstream `pyo3` ↔ Python 3.15-alpha ABI mismatch.
  - **pyproject.toml**: removed `Programming Language :: Python :: 3.15` classifier.
  - **`.github/workflows/ci.yml`**: removed `3.15-dev` from the test matrix and dropped the `continue-on-error` workaround. The matrix now reflects what we actually support.
  - LogXide will re-enable 3.15 once a `pyo3` release ships with a 3.15-compatible ABI.
- No source code changes. No behavior changes for 3.12 / 3.13 / 3.14.

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
