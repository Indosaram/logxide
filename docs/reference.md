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

### Log Levels

| Level | Value |
|-------|-------|
| `logging.DEBUG` | 10 |
| `logging.INFO` | 20 |
| `logging.WARNING` | 30 |
| `logging.ERROR` | 40 |
| `logging.CRITICAL` | 50 |

## Handlers

All handlers are Rust-native implementations. Python `logging.Handler` subclasses are **not supported**.

### FileHandler

```python
# notest
from logxide import FileHandler

handler = FileHandler('app.log', mode='a')
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
```

### StreamHandler

```python
# notest
from logxide import StreamHandler

handler = StreamHandler(stream='stderr')  # 'stdout' or 'stderr'
```

### RotatingFileHandler

```python
# notest
from logxide import RotatingFileHandler

handler = RotatingFileHandler(
    'app.log',
    maxBytes=0,        # 0 = no rotation
    backupCount=0      # Number of backup files to keep
)
```

### HTTPHandler

```python
# notest
from logxide import HTTPHandler

handler = HTTPHandler(
    url="https://logs.example.com",
    batch_size=100,
    flush_interval=5.0,
    global_context={"app": "myapp"},
    transform_callback=None,
    context_provider=None
)
```

### OTLPHandler

```python
# notest
from logxide import OTLPHandler

handler = OTLPHandler(
    url="http://localhost:4318/v1/logs",
    service_name="my-service",
)
```

### SentryHandler

```python
from logxide.sentry_integration import SentryHandler  # notest

handler = SentryHandler(
    level=logging.WARNING,
    with_breadcrumbs=True
)
```

Requires `pip install logxide[sentry]` or `uv add logxide[sentry]`.

### NullHandler

```python
from logxide import NullHandler

handler = NullHandler()  # Discards all log records
```

## Formatters

### PercentStyle (default)

```python
format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
```

### StrFormatStyle

```python
format='{asctime} - {name} - {levelname} - {message}'
style='{'
```

### StringTemplateStyle

```python
format='$asctime - $name - $levelname - $message'
style='$'
```
