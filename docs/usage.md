# Usage Guide

## Quick Start

```python
import logxide
logxide.install()  # Make logxide the default logging module

# Now use logging as normal
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("Hello from LogXide!")
```

## Basic Usage

LogXide can be used as a direct replacement for Python's logging module:

```python
from logxide import logging

# Configure logging (just like Python's logging)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create and use loggers
logger = logging.getLogger('myapp')
logger.info('Hello from LogXide!')
logger.warning('This is a warning')
logger.error('This is an error')
```

## Advanced Formatting

LogXide supports all Python logging format specifiers plus advanced features:

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

### Production Format with Process and Thread IDs
```python
logging.basicConfig(
    format='%(asctime)s [%(process)d:%(thread)d] %(levelname)s %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
```

## Thread Support

LogXide provides enhanced thread support:

```python
import threading
from logxide import logging

def worker(worker_id):
    # Set thread name for better logging
    logging.set_thread_name(f'Worker-{worker_id}')

    logger = logging.getLogger(f'worker.{worker_id}')
    logger.info(f'Worker {worker_id} starting')
    # ... do work ...
    logger.info(f'Worker {worker_id} finished')

# Configure format to show thread names
logging.basicConfig(
    format='%(threadName)-10s | %(name)s | %(message)s'
)

# Start workers
threads = []
for i in range(3):
    t = threading.Thread(target=worker, args=[i])
    threads.append(t)
    t.start()

for t in threads:
    t.join()
```

## Flush Support

Ensure all log messages are processed:

```python
logger.info('Important message')
logging.flush()  # Wait for all async logging to complete
```

## Supported Format Specifiers

LogXide supports all Python logging format specifiers:

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

## Examples

Check out the `examples/` directory for comprehensive usage examples:

- `examples/minimal_dropin.py`: Complete formatting demonstration
- `examples/format_*.py`: Individual format examples

Run the main example to see all formatting options:

```bash
python examples/minimal_dropin.py
```

## API Compatibility

LogXide aims for 100% compatibility with Python's logging module:

- ✅ Logger creation and hierarchy
- ✅ Log levels and filtering
- ✅ Format specifiers and date formatting
- ✅ Basic configuration
- ✅ Thread safety
- ✅ Flush functionality