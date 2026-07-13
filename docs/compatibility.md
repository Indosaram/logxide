# Compatibility Overview

LogXide is a **high-performance logging library** with a familiar API inspired by Python's standard `logging` module. It delivers significant performance improvements through its Rust native core, prioritizing speed over perfect compatibility.

For common use cases, LogXide provides a highly compatible experience. Standard patterns like `getLogger()`, `basicConfig()`, `dictConfig`, and built-in handlers work with minimal or no code changes. However, LogXide is **not a drop-in replacement** for every stdlib logging scenario. Its Rust core means some advanced patterns, particularly those involving custom Python subclasses or deep monkeypatching, are not supported.

This document provides a high-level compatibility overview. For detailed comparisons against specific logging libraries, see the deep-dive guides below.

---

## Quick Compatibility Summary

| Feature | Status | Notes |
|---------|--------|-------|
| Basic logging API (`getLogger`, `info`, `debug`, etc.) | ✅ | Familiar stdlib-like API |
| `basicConfig()` | ✅ | Direct mapping to LogXide handlers |
| `dictConfig()` | ✅ | Use `logxide.config.dictConfig` for Django/FastAPI |
| Standard formatters (`%`-style, `{}`-style) | ✅ | Processed natively in Rust |
| FileHandler, StreamHandler, RotatingFileHandler | ✅ | Rust-native implementations |
| Custom Python formatters (subclassed `Formatter`) | ❌ | Format strings work; custom `format()` methods don't |
| Custom Python handlers | ⚠️ | Accepted; a foreign Python handler runs once on the Python side (no fast-path GIL release) |
| Subclassing `LogRecord` or `Logger` | ❌ | Rust types, not subclassable |
| pytest `caplog` | ⚠️ | Use `caplog_logxide` fixture instead |
| StringIO capture | ❌ | Use file-based logging for tests |

---

## The GIL and What Actually Runs in Rust

LogXide's performance comes from moving the log pipeline into a Rust core. How much of that runs without the GIL depends on the path a record takes:

**Standard library logging:** Creates a Python `LogRecord` object for every log call, then recursively bubbles it through all loggers while holding the GIL with `threading.RLock()`.

**LogXide fast path:** When a record hits no Python filter, no Python handler, and no caller-info field, LogXide extracts the record's fields under the GIL and then releases it for the Rust dispatch. On that path, Rust-native handlers format and write without holding the GIL.

**When the GIL is still held:** A `%`-args call (for example `logger.info("hi %s", name)`) re-acquires the GIL inside `emit()` to run the `%` formatting, so args-bearing logs do not fully parallelize yet. Any Python handler or Python filter also runs under the GIL, as does caller-info collection when the format string needs it.

Because of this scoping, do not expect linear producer scaling across threads on current CPython GIL builds: the fast path shares a handler mutex and the sink I/O is serialized, so adding producer threads does not multiply throughput. Free-threaded CPython builds need separate verification.

Any custom logic that overrides standard Python implementations, such as subclassed Formatters with custom `format()` methods, will not execute natively.

---

## Supported Patterns ✅

- **Basic Configuration:** `logging.basicConfig()` maps directly to LogXide
- **Structural Configuration:** `logxide.config.dictConfig` translates Python dictionary configurations (Django, FastAPI) to native Rust objects
- **Logger Hierarchy:** Dot-delimited logger names (e.g., `app.db.sql`) bubble matching Python's resolution logic
- **Standard Formatting:** `%`-style and `{}`-style placeholders, including `{asctime}`, map to Rust's Chrono formats
- **Standard Handlers:** StreamHandler, FileHandler, RotatingFileHandler behavior replicated in Rust
- **Exception Logging:** `exc_info=True` correctly fetches and logs stack traces
- **Third-party Interception:** `logxide.intercept_stdlib()` captures logs from libraries using standard logging

## Unsupported Patterns ❌

### 1. Custom Python Formatters
LogXide maps the format pattern string directly into Rust. If you subclass `logging.Formatter` to mutate records in a custom `format(self, record)` method, this method will not be called because no pure-Python `LogRecord` is materialized.

*Alternative:* Use JSON templates via `logxide.HTTPHandler` or transform output at the application edge.

### 2. Custom Python Handlers
If you create a custom Python handler (e.g., `class MailLog(logging.Handler)`), LogXide accepts it via `addHandler()` and routes it through its Python dispatch path, so its `.handle()` method runs once with a Python `LogRecord`. It runs synchronously on the Python side and does not benefit from the fast-path GIL release. As of 0.2.0, a Rust-backed handler (e.g. `logxide.FileHandler`) attached to one logger is dispatched exactly once and never leaks records to unrelated loggers; earlier releases could double-emit or misroute such records.

### 3. Standard Library Unit Tests
LogXide fails CPython's `test_logging.py` unit tests. These tests validate locking behavior, internal `.handlers` array mutability, and `.disabled` states using memory assertions that conflict with Rust's encapsulated states and RwLocks.

---

## Detailed Comparison Guides

For side-by-side comparisons with specific logging libraries, including benchmark data and migration guidance:

| Comparison | Description |
|------------|-------------|
| **[LogXide vs stdlib](comparison-stdlib.md)** | Handler-by-handler performance vs Python's `logging` module, feature matrix, and migration path for standard use cases |
| **[LogXide vs Loguru](comparison.md)** | Architecture differences, performance benchmarks, feature trade-offs, and when to choose each |
| **[LogXide vs Structlog](comparison-structlog.md)** | Structured logging capabilities, processor pipelines, context binding, and performance comparison |
| **[LogXide vs Picologging](comparison-picologging.md)** | Rust vs Cython implementation, Python 3.13+ compatibility, and feature ecosystem comparison |

---

## Migration Checklist

When migrating an application to LogXide:

1. **Initialize early:** Import and initialize LogXide before framework initialization (Django/Flask/FastAPI)
2. **Intercept stdlib:** Call `logxide.intercept_stdlib()` to capture logs from third-party dependencies
3. **Use structural config:** Prefer `logxide.config.dictConfig` over custom instantiation
4. **Check custom handlers:** Verify any custom Python handlers are acceptable. They are accepted via `addHandler()` and run once on the Python side (synchronously, without the fast-path GIL release). Rust-backed handlers run once on the Rust path.
5. **Update tests:** Replace `caplog` with `caplog_logxide` and use file-based logging instead of StringIO

For detailed third-party library compatibility information, see the **[Third-Party Compatibility Guide](third-party-compatibility.md)**.
