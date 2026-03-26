# Testing Guide

LogXide provides testing utilities to capture and assert on log output, similar to pytest's `caplog` fixture.

## Quick Start (pytest)

LogXide includes a built-in pytest plugin that provides a `caplog` fixture automatically:

```python
from logxide import logging

def test_logging(caplog):
    logger = logging.getLogger("test")
    logger.addHandler(caplog.handler)
    logger.info("Hello!")

    assert "Hello!" in caplog.text
    assert ("test", 20, "Hello!") in caplog.record_tuples
```

!!! note "Auto-registration"
    The `caplog` fixture is auto-registered via `pyproject.toml` entry point when `logxide` is installed. No `conftest.py` setup required.

## LogCaptureFixture

For more control, use `LogCaptureFixture` directly:

```python
import pytest
from logxide import logging
from logxide.testing import LogCaptureFixture

@pytest.fixture
def caplog_logxide():
    fixture = LogCaptureFixture()
    fixture.set_level(logging.DEBUG)
    yield fixture
    fixture.clear()

def test_example(caplog_logxide):
    logger = logging.getLogger("test")
    logger.addHandler(caplog_logxide.handler)
    logger.info("Hello!")

    assert "Hello!" in caplog_logxide.text
    assert ("test", 20, "Hello!") in caplog_logxide.record_tuples
    assert caplog_logxide.messages == ["Hello!"]
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `.handler` | `MemoryHandler` | The underlying Rust-backed memory handler |
| `.records` | `list[LogRecord]` | All captured log records |
| `.text` | `str` | All messages as newline-separated string |
| `.record_tuples` | `list[tuple[str, int, str]]` | `(logger_name, level, message)` tuples |
| `.messages` | `list[str]` | Message strings only |

### Methods

| Method | Description |
|--------|-------------|
| `set_level(level)` | Set minimum capture level (int or str) |
| `at_level(level)` | Context manager to temporarily change capture level |
| `clear()` | Clear all captured records |

## capture_logs Context Manager

For tests that don't use pytest fixtures, use the `capture_logs` context manager:

```python
from logxide import logging
from logxide.testing import capture_logs

def test_without_fixture():
    logger = logging.getLogger("test")

    with capture_logs(logging.INFO) as captured:
        logger.addHandler(captured.handler)
        logger.info("test message")

    assert "test message" in captured.text
```

## MemoryHandler

Underneath both `LogCaptureFixture` and `capture_logs`, the `MemoryHandler` stores log records in Rust-native memory:

```python
from logxide import MemoryHandler, logging

logger = logging.getLogger("test")
handler = MemoryHandler()
logger.addHandler(handler)

logger.info("Hello!")

handler.records         # [LogRecord(...)]
handler.text            # "INFO test Hello!\n"
handler.record_tuples   # [("test", 20, "Hello!")]
handler.clear()         # Reset for next test
```

!!! tip "Performance"
    `MemoryHandler` stores records in Rust's `Vec<LogRecord>` behind a `Mutex`, making it significantly faster than Python-based alternatives for high-volume capture.
