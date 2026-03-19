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

LogXide supports `addHandler()` with its **Rust native handlers only**:

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
    max_bytes=10 * 1024 * 1024,  # 10MB
    backup_count=5
)
logger.addHandler(rotating)

# Stream handler (stdout/stderr)
stream = StreamHandler()
logger.addHandler(stream)
```

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

### 1. Using Python stdlib handlers

```python
# ❌ WRONG — Python handlers are rejected
import logging as stdlib
logger.addHandler(stdlib.FileHandler('app.log'))  # ValueError!

# ✅ CORRECT — Use LogXide handlers
from logxide import FileHandler
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
| `%(pathname)s` | Full pathname |
| `%(filename)s` | Filename |
| `%(module)s` | Module name |
| `%(lineno)d` | Line number |
| `%(funcName)s` | Function name |

### Advanced Formatting Features

- **Padding**: `%(levelname)-8s` (left-align, 8 chars)
- **Zero padding**: `%(msecs)03d` (3 digits with leading zeros)
- **Custom date format**: `datefmt='%Y-%m-%d %H:%M:%S'`

## Flush Support

Ensure all log messages are processed before program exit:

```python
logger.info('Important message')
logging.flush()  # Wait for all logging to complete
```

!!! note "Handler-specific flush behavior"
    - **FileHandler / RotatingFileHandler**: `flush()` flushes the `BufWriter` buffer to disk (synchronous)
    - **StreamHandler**: `flush()` signals the background thread to drain all queued messages, then waits for completion
    - **HTTPHandler / OTLPHandler**: `flush()` triggers immediate batch send and waits for completion

## Examples

Check out the `examples/` directory for comprehensive usage examples:

```bash
python examples/minimal_dropin.py
```
