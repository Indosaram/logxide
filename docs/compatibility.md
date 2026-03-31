# Compatibility Overview

LogXide is a **high-performance logging library** with a familiar API inspired by Python's standard `logging` module. It delivers significant performance improvements through its Rust native core, prioritizing speed over perfect compatibility.

For common use cases, LogXide provides a highly compatible experience. Standard patterns like `getLogger()`, `basicConfig()`, `dictConfig`, and built-in handlers work with minimal or no code changes. However, LogXide is **not a drop-in replacement** for every stdlib logging scenario. Its Zero-GIL architecture means some advanced patterns, particularly those involving custom Python subclasses or deep monkeypatching, are not supported.

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
| Custom Python handlers | ⚠️ | Accepted but bypass Rust performance pipeline |
| Subclassing `LogRecord` or `Logger` | ❌ | Rust types, not subclassable |
| pytest `caplog` | ⚠️ | Use `caplog_logxide` fixture instead |
| StringIO capture | ❌ | Use file-based logging for tests |

---

## The Zero-GIL Architecture

LogXide's performance comes from its fundamental architectural differences:

**Standard library logging:** Creates a Python `LogRecord` object for every log call, then recursively bubbles it through all loggers while holding the GIL with `threading.RLock()`.

**LogXide:** Drops the GIL immediately and packs raw attributes into a natively dispatched Rust `Arc<LogRecord>`. Formatting, filtering, bubbling, and I/O all happen outside Python's GIL in Rust.

Because of this, any custom logic that overrides standard Python implementations, such as subclassed Formatters with custom `format()` methods, will not execute natively.

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

### 2. Synchronous Python Custom Handlers
If you create a new logging sink (e.g., `class MailLog(logging.Handler)`), LogXide cannot translate this into zero-cost Rust runtime behavior. Python handlers assigned to LogXide loggers still work but lose the Rust backend concurrency advantage.

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
4. **Check custom handlers:** Verify any custom Python handlers are acceptable (they will work but bypass Rust performance)
5. **Update tests:** Replace `caplog` with `caplog_logxide` and use file-based logging instead of StringIO

For detailed third-party library compatibility information, see the **[Third-Party Compatibility Guide](third-party-compatibility.md)**.
