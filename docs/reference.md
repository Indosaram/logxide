# API Reference

## Core API

### `logging` module

The primary interface, imported via `from logxide import logging`.

::: logxide.logging

### Configuration

- `logging.basicConfig(**kwargs)` — Configure root logger with handlers and formatters
- `logging.getLogger(name=None)` — Get or create a named logger
- `logging.flush()` — Ensure all pending log messages are processed
- `logging.set_thread_name(name)` — Set the thread name for logging
- `logging.clear_handlers()` — Remove all handlers from the root logger

### Log Levels

| Level | Value |
|-------|-------|
| `logging.DEBUG` | 10 |
| `logging.INFO` | 20 |
| `logging.WARNING` | 30 |
| `logging.ERROR` | 40 |
| `logging.CRITICAL` | 50 |

---

## Handlers

All handlers listed below are Rust-native implementations, accessed via `from logxide import <Handler>`.

### FileHandler

```python
# notest
from logxide import FileHandler

handler = FileHandler('app.log', mode='a')
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filename` | `str` | — | Path to the log file |
| `mode` | `str` | `'a'` | File open mode (`'a'` append, `'w'` overwrite) |
| `encoding` | `str \| None` | `None` | File encoding |
| `delay` | `bool` | `False` | Delay file creation until first emit |

**Advanced methods:**

| Method | Description |
|--------|-------------|
| `setFlushLevel(level)` | Set the flush level. Records at or above this level trigger immediate disk flush (default: `ERROR`). |
| `getFlushLevel()` | Returns the current flush level as `int`. |
| `setErrorCallback(callback)` | Set a `Callable(str)` to be called on write failures. |
| `flush()` | Flush the `BufWriter` buffer to disk (synchronous). |

### StreamHandler

```python
# notest
from logxide import StreamHandler

handler = StreamHandler(stream='stderr')  # 'stdout' or 'stderr'
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `stream` | `IO[str] \| None` | `None` (stderr) | `sys.stdout` or `sys.stderr` |

**Advanced methods:**

| Method | Description |
|--------|-------------|
| `setErrorCallback(callback)` | Set a `Callable(str)` for write failure handling. |

### RotatingFileHandler

```python
# notest
from logxide import RotatingFileHandler

handler = RotatingFileHandler(
    'app.log',
    maxBytes=10_485_760,  # 10 MB
    backupCount=5
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filename` | `str` | — | Path to the log file |
| `mode` | `str` | `'a'` | File open mode |
| `maxBytes` | `int` | `0` | Max file size before rotation (0 = no rotation) |
| `backupCount` | `int` | `0` | Number of backup files to keep |

**Advanced methods:**

| Method | Description |
|--------|-------------|
| `setFlushLevel(level)` | Set the flush level (default: `ERROR`). |
| `getFlushLevel()` | Returns the current flush level as `int`. |
| `setErrorCallback(callback)` | Set a `Callable(str)` for write failure handling. |
| `flush()` | Flush the `BufWriter` buffer to disk (synchronous). |

### HTTPHandler

High-performance HTTP handler with batching and background transmission.

```python
# notest
from logxide import HTTPHandler

handler = HTTPHandler(
    url="https://logs.example.com",
    headers={"Authorization": "Bearer token"},
    capacity=10000,
    batch_size=1000,
    flush_interval=30,
    global_context={"app": "myapp", "env": "production"},
    transform_callback=None,
    context_provider=None,
    error_callback=None,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | — | HTTP endpoint URL |
| `headers` | `dict[str, str] \| None` | `None` | HTTP headers (e.g., auth tokens) |
| `capacity` | `int` | `10000` | Max buffer capacity |
| `batch_size` | `int` | `1000` | Records per batch |
| `flush_interval` | `int` | `30` | Seconds between auto-flush |
| `global_context` | `dict \| None` | `None` | Static fields added to every record |
| `transform_callback` | `Callable \| None` | `None` | `fn(records) -> transformed` for custom JSON |
| `context_provider` | `Callable \| None` | `None` | `fn() -> dict` for dynamic context per batch |
| `error_callback` | `Callable \| None` | `None` | `fn(error_msg)` for HTTP failure handling |

**Advanced methods:**

| Method | Description |
|--------|-------------|
| `setFlushLevel(level)` | Records at or above this level trigger immediate batch send (default: `ERROR`). |
| `getFlushLevel()` | Returns the current flush level. |
| `flush()` | Triggers immediate batch send and waits for completion. |
| `close()` | Shuts down the background thread and flushes remaining records. |

### OTLPHandler

High-performance OpenTelemetry OTLP handler for log export.

```python
# notest
from logxide import OTLPHandler

handler = OTLPHandler(
    url="http://localhost:4318/v1/logs",
    service_name="my-service",
    headers={"Authorization": "Bearer token"},
    capacity=10000,
    batch_size=1000,
    flush_interval=30,
    error_callback=None,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | — | OTLP endpoint URL |
| `service_name` | `str` | `"unknown_service"` | Service name for OTLP resource |
| `headers` | `dict[str, str] \| None` | `None` | HTTP headers |
| `capacity` | `int` | `10000` | Max buffer capacity |
| `batch_size` | `int` | `1000` | Records per batch |
| `flush_interval` | `int` | `30` | Seconds between auto-flush |
| `error_callback` | `Callable \| None` | `None` | `fn(error_msg)` for failure handling |

**Advanced methods:**

| Method | Description |
|--------|-------------|
| `flush()` | Triggers immediate batch send and waits for completion. |
| `close()` | Shuts down the background thread and flushes remaining records. |

### MemoryHandler

In-memory handler for testing and log capture. Stores records in Rust-native memory for maximum performance.

```python
from logxide import MemoryHandler

handler = MemoryHandler()
logger.addHandler(handler)

logger.info("test message")

# Access captured records
handler.records          # List of LogRecord objects
handler.text             # "INFO test_logger test message\n..."
handler.record_tuples    # [("test_logger", 20, "test message")]
handler.clear()          # Clear all captured records
```

| Property / Method | Type | Description |
|-------------------|------|-------------|
| `.records` | `list[LogRecord]` | All captured log records |
| `.text` | `str` | All messages joined with newlines (caplog-compatible) |
| `.record_tuples` | `list[tuple[str, int, str]]` | `(logger_name, level, message)` tuples (caplog-compatible) |
| `.clear()` | — | Clear all captured records |

### SentryHandler

```python
from logxide.sentry_integration import SentryHandler  # notest

handler = SentryHandler(
    level=logging.WARNING,
    with_breadcrumbs=True
)
```

Requires `pip install logxide[sentry]` or `uv add logxide[sentry]`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `level` | `int` | `WARNING` | Minimum level to send to Sentry |
| `with_breadcrumbs` | `bool` | `True` | Add breadcrumbs for lower-level logs |

### NullHandler

```python
from logxide import NullHandler

handler = NullHandler()  # Discards all log records
```

---

## Formatters

### Formatter (PercentStyle — default)

```python
# notest
from logxide import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### StrFormatStyle

```python
# notest
logging.basicConfig(
    format='{asctime} - {name} - {levelname} - {message}',
    style='{'
)
```

### StringTemplateStyle

```python
# notest
logging.basicConfig(
    format='$asctime - $name - $levelname - $message',
    style='$'
)
```

### ColorFormatter

Rust-native ANSI color formatter for terminal output. Automatically applies level-based colors.

```python
# notest
from logxide import ColorFormatter

formatter = ColorFormatter(
    fmt="%(ansi_level_color)s%(levelname)s%(ansi_reset_color)s - %(message)s",
    datefmt=None,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `fmt` | `str` | `"%(ansi_level_color)s%(levelname)s%(ansi_reset_color)s - %(message)s"` | Format string |
| `datefmt` | `str \| None` | `None` | strftime format for `%(asctime)s` |

**Additional format placeholders:**

| Placeholder | Description |
|-------------|-------------|
| `%(ansi_level_color)s` | ANSI escape code for the current log level color |
| `%(ansi_reset_color)s` | ANSI reset code to end coloring |

**Color mapping:**

| Level | Color |
|-------|-------|
| DEBUG | Cyan |
| INFO | Green |
| WARNING | Yellow |
| ERROR | Red |
| CRITICAL | Red (bold) |

---

## Testing Utilities

### LogCaptureFixture

```python
from logxide.testing import LogCaptureFixture
from logxide import logging

fixture = LogCaptureFixture()
fixture.set_level(logging.DEBUG)

logger = logging.getLogger("test")
logger.addHandler(fixture.handler)
logger.info("Hello!")

assert "Hello!" in fixture.text
assert ("test", 20, "Hello!") in fixture.record_tuples

fixture.clear()
```

| Property / Method | Type | Description |
|-------------------|------|-------------|
| `.handler` | `MemoryHandler` | Underlying memory handler |
| `.records` | `list` | All captured log records |
| `.text` | `str` | All messages as newline-separated string |
| `.record_tuples` | `list[tuple]` | `(logger_name, level, message)` tuples |
| `.messages` | `list[str]` | Message strings only |
| `.set_level(level)` | — | Set minimum capture level |
| `.at_level(level)` | context manager | Temporarily set capture level |
| `.clear()` | — | Clear all captured records |

### capture_logs

Context manager for one-off log capture without pytest fixtures.

```python
from logxide import logging
from logxide.testing import capture_logs

logger = logging.getLogger("test")

with capture_logs(logging.INFO) as captured:
    logger.addHandler(captured.handler)
    logger.info("test message")

assert "test message" in captured.text
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `level` | `int` | `10` (DEBUG) | Minimum log level to capture |

### pytest Plugin (`caplog_logxide`)

LogXide provides a built-in pytest plugin (auto-registered via entry point) that overrides the `caplog` fixture:

```python
# No setup required — automatically available when logxide is installed

def test_example(caplog):
    logger = logging.getLogger("test")
    logger.addHandler(caplog.handler)
    logger.info("Hello!")

    assert "Hello!" in caplog.text
    assert ("test", 20, "Hello!") in caplog.record_tuples
```

---

## Compatibility Functions

These functions maintain API compatibility with Python's standard `logging` module. Import from `logxide` directly or via `from logxide import logging`.

| Function | Signature | Description |
|----------|-----------|-------------|
| `addLevelName` | `(level: int, levelName: str)` | Register a custom level name |
| `getLevelName` | `(level: int \| str) -> str \| int` | Get level name from number or vice versa |
| `getLevelNamesMapping` | `() -> dict[str, int]` | Return copy of level name → number mapping |
| `disable` | `(level: int)` | Disable all logging below the specified level |
| `captureWarnings` | `(capture: bool)` | Redirect `warnings` module output to logging |
| `makeLogRecord` | `(dict_: dict) -> LogRecord` | Create a LogRecord from a dictionary |
| `getLogRecordFactory` | `() -> Callable \| None` | Get current log record factory |
| `setLogRecordFactory` | `(factory: Callable)` | Set custom log record factory |
| `getLoggerClass` | `() -> type[PyLogger]` | Get the logger class |
| `setLoggerClass` | `(klass: type)` | Set custom logger class (stub) |
| `getHandlerByName` | `(name: str) -> Handler \| None` | Get a registered handler by name |
| `getHandlerNames` | `() -> list[str]` | List all registered handler names |

---

## Utility Functions

### `register_python_handler`

Register a custom Python callable as a log handler in the Rust pipeline.

```python
# notest
from logxide import logging

def my_handler(record):
    print(f"Custom: {record.getMessage()}")

logging.register_python_handler(my_handler)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `handler` | `Callable` | A callable that accepts a `LogRecord` |

### `uninstall`

Restore the standard `logging` module, removing all LogXide monkey-patches.

```python
# notest
from logxide import uninstall

uninstall()  # Restores logging.getLogger and logging.basicConfig to stdlib originals
```

### `clear_handlers`

Remove all handlers from the LogXide root logger.

```python
# notest
from logxide import logging

logging.clear_handlers()
```
