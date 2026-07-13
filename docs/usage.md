# Usage Guide

## Quick Start

```python
from logxide import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('myapp')
logger.info('Hello from LogXide!')
```

## Basic Usage

LogXide provides a familiar API similar to Python's logging module:

```python
from logxide import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('myapp')
logger.info('Hello from LogXide!')
logger.warning('This is a warning')
logger.error('This is an error')
```

## Handler Usage

### Using basicConfig (Recommended)

```python
from logxide import logging

# Console output (default: stderr)
logging.basicConfig(level=logging.INFO)

# File output
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Using addHandler

LogXide's Rust native handlers give the best throughput, but `addHandler()` also accepts standard Python `logging.Handler` subclasses, which run once on the Python side (without the fast-path GIL release):

```python
from logxide import logging, FileHandler, StreamHandler, RotatingFileHandler

logger = logging.getLogger('myapp')

# File handler
handler = FileHandler('app.log')
handler.setLevel(logging.INFO)
logger.addHandler(handler)

# Rotating file handler
rotating = RotatingFileHandler(
    'app.log',
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5
)
logger.addHandler(rotating)

# Stream handler (stdout/stderr)
stream = StreamHandler()
logger.addHandler(stream)
```

!!! note "How handlers are routed (0.2.0)"
    A Rust-backed handler attached to one logger is dispatched **exactly once** and never leaks records to unrelated loggers — the double-emit and cross-logger misrouting from earlier releases are fixed. Handlers route by backend kind:

    - **Structured sinks** (`HTTPHandler`, `OTLPHandler`) serialize the record in Rust (JSON / protobuf), preserving `extra` fields.
    - **Text-sink wrappers** (`FileHandler`, `StreamHandler`, `RotatingFileHandler`, `MemoryHandler`) format the line via their Python `emit()` override, which is what makes formatted output and pytest capture work.
    - **Foreign Python handlers** (your own `logging.Handler` subclass, Sentry, etc.) run once on the Python side, without the fast-path GIL release.

### HTTP and OTLP Handlers

```python
from logxide import HTTPHandler, OTLPHandler

# HTTP log shipping
http_handler = HTTPHandler(
    url="https://logs.example.com",
    global_context={"app": "myapp", "env": "production"}
)

# OpenTelemetry OTLP
otlp_handler = OTLPHandler(
    url="http://localhost:4318/v1/logs",
    service_name="my-service"
)
```

## ⚠️ Common Mistakes

### 1. Mixing Python stdlib handlers with Rust handlers

```python
from logxide import logging, FileHandler
import logging as stdlib

logger = logging.getLogger('myapp')

# ⚠️ Accepted, but a foreign Python handler runs on the Python side (no fast-path GIL release)
logger.addHandler(stdlib.FileHandler('app.log'))  # runs once, synchronously in Python

# ✅ PREFERRED — Use LogXide handlers for the fast path
logger.addHandler(FileHandler('app.log'))
```

### 2. StringIO capture doesn't work

```python
# ❌ WRONG — Rust writes directly to OS stdout/stderr
import io
stream = io.StringIO()
handler = logging.StreamHandler(stream)  # Won't capture

# ✅ CORRECT — Use file-based testing
import tempfile
with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.log') as f:
    logging.basicConfig(filename=f.name, level=logging.INFO, force=True)
    logger.info('Test message')
    logging.flush()
    with open(f.name) as log_file:
        assert 'Test message' in log_file.read()
```

### 3. pytest caplog — Use `caplog_logxide` instead

```python
# ❌ caplog fixture is not compatible with LogXide
def test_with_caplog(caplog):
    ...  # Won't capture LogXide output

# ✅ Use caplog_logxide fixture
def test_logging(caplog_logxide):
    logger = logging.getLogger('test')
    logger.info('Test message')
    assert 'Test message' in caplog_logxide.text
    assert ('test', 20, 'Test message') in caplog_logxide.record_tuples
```

## Advanced Formatting

### Multi-threaded Format with Padding
```python
logging.basicConfig(
    format='[%(asctime)s] %(threadName)-10s | %(name)-15s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
```

### JSON-like Structured Logging
```python
logging.basicConfig(
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
```

### Production Format
```python
logging.basicConfig(
    format='%(asctime)s [%(process)d:%(thread)d] %(levelname)s %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
```

## Thread Support

```python
import threading
from logxide import logging

def worker(worker_id):
    logging.set_thread_name(f'Worker-{worker_id}')
    logger = logging.getLogger(f'worker.{worker_id}')
    logger.info(f'Worker {worker_id} starting')
    logger.info(f'Worker {worker_id} finished')

logging.basicConfig(
    format='%(threadName)-10s | %(name)s | %(message)s'
)

threads = [threading.Thread(target=worker, args=[i]) for i in range(3)]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

## Supported Format Specifiers

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
| `%(pathname)s` | Full pathname (Triggers caller frame introspection) |
| `%(filename)s` | Filename (Triggers caller frame introspection) |
| `%(module)s` | Module name (Triggers caller frame introspection) |
| `%(lineno)d` | Line number (Triggers caller frame introspection) |
| `%(funcName)s` | Function name (Triggers caller frame introspection) |

!!! note "Caller-Info Frame Introspection"
    Using any of the caller-info fields (`%(pathname)s`, `%(filename)s`, `%(module)s`, `%(lineno)d`, `%(funcName)s`) requires CPython stack frame inspection.
    - **Automatic Activation**: LogXide dynamically detects these placeholders and enables optimized CPython frame extraction.
    - **Compatibility Layer**: When using standard library formatters via the `compat_handlers.py` path, caller-info context is automatically enabled and routed to the native backend via the `activate_caller_info` mechanism.

!!! note "Tuple and List Serialization"
    To maintain uniform structured representation, passing Python `tuple` or `list` structures inside `extra` dictionaries or `global_context` will automatically serialize them as JSON arrays (e.g., `(1, 2, 3)` becomes `[1, 2, 3]`) inside native HTTP and structured output pipelines.

### Advanced Formatting Features

- **Padding**: `%(levelname)-8s` (left-align, 8 chars)
- **Zero padding**: `%(msecs)03d` (3 digits with leading zeros)
- **Custom date format**: `datefmt='%Y-%m-%d %H:%M:%S'`

## Flush Support

Ensure all log messages are processed before program exit:

```python
logger.info('Important message')
logging.flush()  # Drain the async queue and wait for the sink to acknowledge
```

As of 0.2.0, `flush()` is a **drain-and-wait** operation (its return type is still `None`):

- It drains the async queue to empty, then waits — bounded by the handler's flush timeout — until the sink has acknowledged the enqueued records before returning.
- For synchronous `FileHandler` / `RotatingFileHandler`, it flushes the Rust `BufWriter` to disk.

!!! note "Handler-specific flush behavior"
    - **FileHandler / RotatingFileHandler**: `flush()` flushes the `BufWriter` buffer to disk (synchronous)
    - **StreamHandler**: `flush()` drains the background queue and waits for the worker to write everything
    - **HTTPHandler / OTLPHandler**: `flush()` drains the batch queue and waits (up to the flush timeout) for the sink to acknowledge delivery

!!! note "Shutdown"
    `close()` / `shutdown()` on an async handler first drains the queue (like `flush()`), then joins the background worker thread, so no records are silently abandoned on teardown.

### Async delivery metrics and overflow policy

Async handlers (`HTTPHandler`, `OTLPHandler`) expose an explicit, payload-free delivery accounting via `get_metrics()`:

```python
# notest
from logxide import HTTPHandler

handler = HTTPHandler(url="https://logs.example.com", overflow="block")
# ... emit records ...
handler.flush()
m = handler.get_metrics()
# m == {"emitted": ..., "sink_acknowledged": ..., "queue_dropped": ...,
#       "delivery_failed": ..., "in_flight": ...}
```

After a successful drain, `sink_acknowledged + queue_dropped + delivery_failed == emitted` and `in_flight == 0`.

The `overflow` constructor argument controls what happens when the queue saturates:

| `overflow` | Behavior |
|------------|----------|
| `"block"` (default) | Durable: the producer waits for queue space, so no records are dropped (`queue_dropped` stays 0) |
| `"drop_oldest"` | Under saturation, evict the oldest queued record to make room; dropped records are counted in `queue_dropped` |
| `"drop_newest"` | Under saturation, drop the incoming record; counted in `queue_dropped` |

Choose `"block"` when durability matters and `"drop_oldest"`/`"drop_newest"` when you would rather shed load than back-pressure the producer. Either way, `get_metrics()` tells you exactly how many records were delivered versus dropped.

## Examples

Check out the `examples/` directory for comprehensive usage examples:

```bash
python examples/minimal_dropin.py
```
