# LogXide Usage Guide

This guide explains correct usage patterns and common mistakes.

## Quick Start

```python
# ✅ CORRECT - Import LogXide (automatic installation)
from logxide import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('myapp')
logger.info('Hello, LogXide!')
```

## Handler Usage

### File Logging

**❌ WRONG - Using Python standard library handler:**
```python
import logging as stdlib
from logxide import logging

logger = logging.getLogger('myapp')
handler = stdlib.FileHandler('app.log')  # ERROR: ValueError!
logger.addHandler(handler)
```

**✅ CORRECT - Using LogXide's Rust handler:**
```python
from logxide import logging, FileHandler

logger = logging.getLogger('myapp')
handler = FileHandler('app.log')  # LogXide's Rust handler
handler.setLevel(logging.INFO)
logger.addHandler(handler)
logger.info('This will be written to app.log')
```

**✅ CORRECT - Using basicConfig (recommended):**
```python
from logxide import logging

logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger('myapp')
logger.info('This will be written to app.log')
```

### Stream Logging

**❌ WRONG - StringIO capture doesn't work:**
```python
import io
from logxide import logging

stream = io.StringIO()
handler = logging.StreamHandler(stream)  # ERROR: Python object not supported
logger = logging.getLogger('myapp')
logger.addHandler(handler)
logger.info('This will NOT be captured by StringIO')
```

**✅ CORRECT - File-based testing:**
```python
import tempfile
from logxide import logging

with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.log') as f:
    logging.basicConfig(filename=f.name, level=logging.INFO, force=True)
    logger = logging.getLogger('myapp')
    logger.info('Test message')
    logging.flush()

    # Verify output
    with open(f.name) as log_file:
        content = log_file.read()
        assert 'Test message' in content
```

**✅ CORRECT - Console output:**
```python
from logxide import logging

# Default is stderr
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('myapp')
logger.info('This appears on console')

# Or use basicConfig with stream parameter
logging.basicConfig(stream="stdout", level=logging.INFO)
```

### Rotating File Handler

```python
from logxide import logging, RotatingFileHandler

logger = logging.getLogger('myapp')
handler = RotatingFileHandler(
    'app.log',
    max_bytes=10 * 1024 * 1024,  # 10MB
    backup_count=5
)
handler.setLevel(logging.INFO)
logger.addHandler(handler)
logger.info('Rotating file logging')
```

## Common Mistakes

### 1. Importing Wrong Logging Module

**❌ WRONG:**
```python
import logging  # This is standard library!
# LogXide is not activated
```

**✅ CORRECT:**
```python
from logxide import logging  # LogXide version
# LogXide is now installed and active
```

### 2. Adding Python Handlers

**❌ WRONG:**
```python
from logxide import logging
import logging as stdlib

logger = logging.getLogger('myapp')
logger.addHandler(stdlib.StreamHandler())  # ValueError!
logger.addHandler(stdlib.FileHandler('app.log'))  # ValueError!
```

**✅ CORRECT:**
```python
from logxide import logging, StreamHandler, FileHandler

logger = logging.getLogger('myapp')
logger.addHandler(StreamHandler())  # LogXide's Rust handler
logger.addHandler(FileHandler('app.log'))  # LogXide's Rust handler
```

### 3. pytest caplog Doesn't Work

**❌ WRONG:**
```python
import pytest
from logxide import logging

def test_logging(caplog):
    logger = logging.getLogger('test')
    logger.info('Test')
    assert 'Test' in caplog.text  # FAILS - no capture
```

**✅ CORRECT:**
```python
import tempfile
from logxide import logging

def test_logging():
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.log') as f:
        logging.basicConfig(filename=f.name, level=logging.INFO, force=True)
        logger = logging.getLogger('test')
        logger.info('Test')
        logging.flush()

        with open(f.name) as log_file:
            assert 'Test' in log_file.read()
```

### 4. Using Wrong Python Version

**❌ WRONG:**
```bash
# LogXide compiled for Python 3.14
python3.9 myapp.py  # Cryptic import error: symbol not found
```

**✅ CORRECT:**
```bash
# Reinstall with correct Python version
python3.14 -m pip install logxide

# Or use the correct interpreter
python3.14 myapp.py
```

LogXide now detects version mismatch and provides clear error message:
```
═════════════════════════════════════════════════════════════
❌ FATAL: Python Version Mismatch
═══════════════════════════════════════════════════════════════

LogXide was compiled for Python 3.14
but you are running Python 3.9

This will cause complete logging failures (0 bytes written, no output).
```

## Architecture Notes

LogXide uses **Rust-native handlers only** for performance:

| Feature | Implementation | Notes |
|----------|--------------|--------|
| File I/O | `BufWriter<File>` 64KB buffer + immediate flush | High reliability |
| Stream I/O | OS-level stdout/stderr | Bypasses Python redirects |
| Thread Safety | Mutex-protected handlers | Safe for concurrent logging |
| Python Handlers | Blocked for performance | Use Rust handlers instead |

## Troubleshooting

### Problem: "0 bytes written to log file"

**Cause**: Python version mismatch or wrong handler type

**Solution**:
```bash
# Check Python version
python --version

# Reinstall LogXide with correct version
python3.X -m pip install --force-reinstall logxide
```

### Problem: "No output on console"

**Cause**: Using `StringIO` or pytest caplog

**Solution**: Use file-based logging or check console redirection

### Problem: "ValueError: Only Rust native handlers are supported"

**Cause**: Trying to add Python stdlib handlers

**Solution**: Import handlers from logxide, not logging
```python
from logxide import FileHandler, StreamHandler, RotatingFileHandler
```

## Performance Tips

1. **Use `basicConfig()`** for simple setup - one global handler is optimal
2. **Batch log messages** - minimize handler calls in tight loops
3. **Avoid excessive formatting** - keep format strings simple
4. **Flush explicitly** - call `logging.flush()` before process exit

## Integration Examples

### Flask Integration

```python
from flask import Flask
from logxide import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/')
def home():
    logger = logging.getLogger(__name__)
    logger.info('Request received')
    return 'Hello'
```

### Django Integration

```python
import logging
from logxide import logging as logxide_logging

# Configure LogXide first
logxide_logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Then use Django's logging normally
logger = logging.getLogger('django')
logger.info('Django request')
```

### FastAPI Integration

```python
from fastapi import FastAPI
from logxide import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

@app.get("/")
def read_root():
    logger = logging.getLogger(__name__)
    logger.info('FastAPI request')
    return {"Hello": "World"}
```
