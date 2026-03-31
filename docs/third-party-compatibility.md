# Third-Party Library Compatibility Guide

LogXide automatically intercepts logging from third-party libraries. This guide documents compatibility status, configuration requirements, and known limitations for popular Python libraries.

---

## Status Legend

| Icon | Meaning |
|------|---------|
| ✅ **Tested** | Verified with examples and/or integration tests |
| ✅ **Expected** | Uses standard logging patterns; no known issues |
| ⚠️ **Partial** | Works with specific configuration or has limitations |
| ⚠️ **Limited** | Works for basic use cases but significant features are unsupported |
| ⚠️ **Untested** | Expected to work based on architecture analysis, but not verified |
| ❌ **Incompatible** | Fundamental architectural conflict |

---

## Quick Reference Matrix

| Library | Status | Logger Names | Notes |
|---------|--------|--------------|-------|
| **Flask** | ✅ Tested | `flask.app`, `werkzeug` | [Details](#flask) |
| **Django** | ✅ Tested | `django.*` | [Details](#django) |
| **FastAPI** | ✅ Tested | `fastapi` | [Details](#fastapi--uvicorn) |
| **Sentry** | ✅ Tested | Native integration | [Details](#sentry) |
| **SQLAlchemy** | ✅ Tested | `sqlalchemy.engine`, `sqlalchemy.pool` | [Details](#sqlalchemy) |
| **Flask-SQLAlchemy** | ✅ Tested | `sqlalchemy.engine` | [Details](#sqlalchemy) |
| **requests / urllib3** | ✅ Tested | `urllib3.connectionpool`, `urllib3.connection` | [Details](#requests--urllib3) |
| **httpx** | ✅ Expected | `httpx`, `httpcore` | [Details](#httpx) |
| **Uvicorn** | ✅ Tested | `uvicorn`, `uvicorn.error`, `uvicorn.access` | [Details](#fastapi--uvicorn) |
| **Gunicorn** | ✅ Expected | `gunicorn.error`, `gunicorn.access` | [Details](#gunicorn) |
| **Hypercorn** | ✅ Expected | `hypercorn.*` | Standard logging usage |
| **boto3 / botocore** | ✅ Expected | `boto3`, `botocore.*` | [Details](#boto3--botocore) |
| **aiohttp** | ✅ Expected | `aiohttp`, `aiohttp.server`, `aiohttp.access` | [Details](#aiohttp) |
| **Celery** | ⚠️ Partial | `celery.*` | [Details](#celery) |
| **pytest** | ⚠️ Partial | N/A | [Details](#pytest) |
| **unittest** | ⚠️ Limited | N/A | [Details](#unittest) |
| **python-json-logger** | ⚠️ Limited | N/A | [Details](#python-json-logger) |
| **Scrapy** | ⚠️ Untested | `scrapy.*` | [Details](#scrapy) |
| **structlog** | ❌ Incompatible | N/A | [Details](#structlog) |
| **Pandas / NumPy** | ✅ Expected | `pandas.*` | Minimal logging |

---

## How LogXide Intercepts Third-Party Logging

When you import logxide (outside of pytest), it performs two key actions:

1. **Patches `logging.getLogger()`** — Every call to `logging.getLogger(name)` returns a stdlib Logger whose logging methods (`debug`, `info`, `warning`, `error`, `critical`, `exception`, `log`) are replaced with logxide equivalents. This means any library that uses `import logging; logger = logging.getLogger(__name__)` automatically routes through logxide's Rust backend.

2. **Replaces `sys.modules["logging"]`** — The `logging` module in `sys.modules` is replaced with a `_LoggingModule` instance that mirrors the stdlib API but delegates to logxide internally.

!!! tip "Import Order Matters"
    Always import logxide **before** initializing your framework or third-party libraries. This ensures all loggers created during initialization are intercepted.

    ```python
    # Correct order
    from logxide import logging      # 1. Import logxide first
    from flask import Flask          # 2. Then import framework
    app = Flask(__name__)            # 3. Then initialize
    ```

!!! warning "Handler Migration on Import"
    When logxide is imported, it calls `_migrate_existing_loggers()` which **clears all handlers** from existing stdlib loggers and sets `propagate = True`. This means any handlers that third-party libraries attached to their loggers during import will be removed. This is by design (to route everything through logxide's Rust pipeline), but it means libraries that configure handlers at import time will lose that configuration. Import logxide first to avoid this issue.

### What Works Automatically

Any library that only uses:

- `logging.getLogger(name)` to get loggers
- `.debug()`, `.info()`, `.warning()`, `.error()`, `.critical()`, `.exception()` to emit logs
- `logging.basicConfig()` for configuration
- `setLevel()` on loggers
- `addHandler()` with Rust-compatible handlers
- `addFilter()` with `logging.Filter` instances
- `isEnabledFor()` level checks

### What Breaks

Libraries that:

- **Subclass `logging.Logger`** — Rust type, not subclassable
- **Subclass `logging.LogRecord`** — Rust type, not subclassable
- **Override `logging.Formatter.format()`** — On the Rust code path (primary), custom `format()` methods are not called because Rust handles formatting directly. However, if a Python handler is attached, its formatter's `format()` method **will** be called on the Python LogRecord passed to that handler.
- **Use Python `logging.Handler` subclasses** — They are accepted and their `.handle()` method is called with a Python LogRecord, but log processing also goes through the Rust pipeline independently. This means logs are processed twice (Rust + Python handler), not "bypassed."
- **Use `StringIO` stream capture** — Not supported (Rust writes directly)
- **Rely on `caplog` in pytest** — Must use `caplog_logxide` instead

!!! warning "Custom Python Handlers"
    Python `logging.Handler` subclasses are accepted via `addHandler()`. LogXide stores them separately and calls their `.handle()` method with a Python LogRecord object after the Rust pipeline processes the log. This means both Rust handlers and Python handlers fire for each log event. For maximum performance, use Rust-native handlers: `FileHandler`, `StreamHandler`, `RotatingFileHandler`, `HTTPHandler`, `OTLPHandler`.

### Alternative: Explicit Stdlib Interception

If you need to capture logs from libraries that were imported before logxide, use `intercept_stdlib()`:

```python
from logxide import logging
from logxide.interceptor import intercept_stdlib

# Redirect ALL existing stdlib loggers to logxide
intercept_stdlib()
```

This replaces the root logger's handlers with an `InterceptHandler` that forwards all stdlib log records to logxide.

---

## Web Frameworks

### Flask

**Status:** ✅ Tested | **Integration doc:** [Flask Integration](integrations/flask.md) | **Example:** `examples/flask_integration.py`

Flask uses `app.logger`, which internally calls `logging.getLogger('flask.app')`. Werkzeug (Flask's WSGI server) logs to the `werkzeug` logger. Both are automatically intercepted.

```python
from logxide import logging
from flask import Flask

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@app.route('/')
def hello():
    logger.info('Hello endpoint accessed')
    return {'message': 'Hello from Flask!'}
```

**What works:**

- `app.logger` — automatically routed through logxide
- Werkzeug request/response logging
- Flask-SQLAlchemy SQL query logging (see [SQLAlchemy](#sqlalchemy))
- Sentry integration with `FlaskIntegration()` (see [Sentry](#sentry))
- Request logging middleware via `@app.before_request` / `@app.after_request`
- Error handling with `@app.errorhandler` and `logger.exception()`

**Full documentation:** [Flask Integration](integrations/flask.md)

---

### Django

**Status:** ✅ Tested | **Integration doc:** [Django Integration](integrations/django.md) | **Example:** `examples/django_integration.py`

Django uses the `LOGGING` dictionary configuration in `settings.py`, processed via `logging.config.dictConfig()`. LogXide's module replacement ensures this works.

```python
# manage.py or wsgi.py — import logxide early
from logxide import logging

import os
from django.core.wsgi import get_wsgi_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myapp.settings')
application = get_wsgi_application()
```

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} - {name} - {levelname} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

**What works:**

- `dictConfig`-based `LOGGING` setting
- Django request logging (`django.request`)
- Django SQL logging (`django.db.backends`)
- Signal-based logging in models
- Management command logging
- Sentry integration with `DjangoIntegration()`

**Known caveats:**

- Django's `AdminEmailHandler` is a custom `logging.Handler` subclass. It executes but is called separately from the Rust pipeline.
- Django's built-in `Filter` subclasses (`RequireDebugFalse`, `RequireDebugTrue`) work because logxide supports `logging.Filter`.
- Import logxide in `manage.py` or `wsgi.py` before `django.setup()` is called.
- **`dictConfig` handler resolution:** Django's `LOGGING` dict uses `logging.config.dictConfig()`, which resolves handler class names (e.g., `'logging.StreamHandler'`) against the real stdlib `logging` module. Handlers created this way are Python stdlib handlers, not logxide's Rust handlers. They will still be called (logxide accepts Python handlers), but won't benefit from the Rust performance pipeline. For Rust-native file logging, use logxide's `basicConfig(filename=...)` instead of `dictConfig` file handlers.

**Full documentation:** [Django Integration](integrations/django.md)

---

### FastAPI / Uvicorn

**Status:** ✅ Tested | **Integration doc:** [FastAPI Integration](integrations/fastapi.md) | **Examples:** `examples/fastapi_demo.py`, `examples/fastapi_advanced.py`

FastAPI uses stdlib logging directly. Uvicorn creates loggers at `uvicorn`, `uvicorn.error`, and `uvicorn.access`. All are automatically intercepted.

```python
from logxide import logging
from fastapi import FastAPI

app = FastAPI()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"status": "ok"}
```

**What works:**

- FastAPI endpoint logging
- Uvicorn access and error logging (`uvicorn.access`, `uvicorn.error`)
- Background task logging
- SQLAlchemy integration via FastAPI `Depends`
- ASGI middleware logging
- Sentry integration with `SentryAsgiMiddleware`

!!! tip "Uvicorn Log Configuration"
    When using logxide, you can let logxide handle all formatting and just set log levels:
    ```bash
    uvicorn app:app --log-level info
    ```

**Full documentation:** [FastAPI Integration](integrations/fastapi.md)

---

## HTTP Client Libraries

### requests / urllib3

**Status:** ✅ Tested | **Example:** `examples/third_party_integration.py`

`requests` uses `urllib3` internally, which logs to `urllib3.connectionpool`, `urllib3.connection`, etc. using standard `logging.getLogger(__name__)`. All automatically intercepted.

```python
from logxide import logging
import requests

# Enable urllib3 debug logging to see connection details
logging.getLogger('urllib3').setLevel(logging.DEBUG)

response = requests.get('https://example.com')
# urllib3 connection logs automatically captured by logxide
```

**What works:**

- Connection pool logging (`urllib3.connectionpool`)
- SSL/TLS handshake logging
- Retry logic logging
- Request/response debug logging
- `NullHandler` compatibility (requests adds `NullHandler` at import time)

---

### httpx

**Status:** ✅ Expected

httpx is a development dependency in logxide's test suite. It uses standard `logging.getLogger(__name__)` patterns, logging to `httpx` and `httpcore`.

```python
from logxide import logging
import httpx

logging.getLogger('httpx').setLevel(logging.DEBUG)

async with httpx.AsyncClient() as client:
    response = await client.get('https://example.com')
```

---

### aiohttp

**Status:** ✅ Expected

aiohttp logs to `aiohttp`, `aiohttp.server`, `aiohttp.access`, and `aiohttp.web` using standard `logging.getLogger(__name__)`. Expected to work automatically.

---

## Database Libraries

### SQLAlchemy

**Status:** ✅ Tested | **Example:** `examples/third_party_integration.py`

SQLAlchemy logs SQL statements through `sqlalchemy.engine` and connection pool events through `sqlalchemy.pool`. Uses standard `logging.getLogger(name)` via its internal `InstanceLogger` wrapper.

```python
from logxide import logging
from sqlalchemy import create_engine, text

# Enable SQL query logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

engine = create_engine('sqlite:///:memory:', echo=True)

with engine.connect() as conn:
    conn.execute(text("SELECT 1"))
    # SQL statement logged through logxide
```

**What works:**

- SQL statement logging (`sqlalchemy.engine`)
- Connection pool logging (`sqlalchemy.pool`)
- `echo=True` parameter on `create_engine()`
- `isEnabledFor()` level checks (used internally by SQLAlchemy for performance)
- Flask-SQLAlchemy and FastAPI + SQLAlchemy patterns
- Alembic migration logging (expected)

!!! note "SQLAlchemy Performance"
    SQLAlchemy calls `logger.isEnabledFor(level)` before formatting SQL statements to avoid overhead. LogXide supports this method, so SQL logging only incurs formatting cost when the appropriate log level is enabled.

---

## ASGI / WSGI Servers

### Gunicorn

**Status:** ✅ Expected

Gunicorn uses `logging.getLogger("gunicorn.error")` and `logging.getLogger("gunicorn.access")` for its logging. Both are automatically intercepted.

```python
# gunicorn.conf.py
from logxide import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

**Caveats:**

- Gunicorn's `--log-config` INI-style config file uses `logging.config.fileConfig()`. This works through the module replacement, but you may prefer logxide's `basicConfig()` instead.
- Gunicorn forks worker processes. Each worker reconfigures logging independently. Import logxide in the gunicorn config file to ensure all workers are patched.
- Gunicorn's custom `Logger` class (`gunicorn.glogging.Logger`) uses standard `logging.getLogger()` internally.

---

## Task Queues & Workers

### Celery

**Status:** ⚠️ Partial (Requires Configuration)

Celery has aggressive logging management. By default, it **hijacks the root logger** — removing all existing handlers and installing its own. This conflicts with logxide's configuration.

```python
from logxide import logging
from celery import Celery
from celery.signals import setup_logging

app = Celery('myapp')

@setup_logging.connect
def configure_logging(**kwargs):
    """Prevent Celery from hijacking the root logger."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
```

**What works:**

- Basic task logging via `celery.utils.log.get_task_logger()`
- Worker lifecycle logging
- Logger hierarchy for celery namespaces

**What requires configuration:**

- **Root logger hijacking** — Set `worker_hijack_root_logger = False` in Celery config, or use the `setup_logging` signal (shown above) to prevent Celery from overwriting logxide's handlers.
- **TaskFormatter** — Celery's `TaskFormatter` is a `logging.Formatter` subclass that accesses extra attributes (`task_id`, `task_name`) on LogRecord. On the Rust code path, this formatter is not called. It would only work if Celery attaches its own Python handler, in which case it receives a Python LogRecord alongside the Rust pipeline output.

!!! warning "Celery Root Logger Hijacking"
    Without configuration, Celery removes all root logger handlers on worker startup. Use the `setup_logging` signal or set `worker_hijack_root_logger = False` to prevent this.

---

## Cloud SDKs

### boto3 / botocore

**Status:** ✅ Expected

boto3 and botocore use standard `logging.getLogger(__name__)` throughout. Logger names include `boto3`, `botocore`, `botocore.endpoint`, `botocore.hooks`, `botocore.credentials`, and `botocore.retryhandler`.

```python
from logxide import logging
import boto3

# Silence verbose botocore logging
logging.getLogger('botocore').setLevel(logging.WARNING)

# Or enable debug for troubleshooting
logging.getLogger('botocore.endpoint').setLevel(logging.DEBUG)
```

!!! warning "Wire Logging Security"
    `botocore.endpoint` at DEBUG level logs full HTTP requests and responses, which may include AWS credentials or sensitive data. Keep this logger at WARNING or above in production.

---

## Error Tracking & Monitoring

### Sentry

**Status:** ✅ Tested (Native Integration) | **Integration doc:** [Sentry Integration](integrations/sentry.md) | **Example:** `examples/sentry_integration.py`

LogXide includes a dedicated `SentryHandler` with zero-configuration auto-detection. When `sentry_sdk` is initialized, logxide automatically sends WARNING+ logs to Sentry.

```bash
pip install logxide[sentry]
```

```python
import sentry_sdk
sentry_sdk.init(dsn="https://your-dsn@sentry.io/project-id")

from logxide import logging

logger = logging.getLogger(__name__)
logger.warning("Sent to Sentry automatically")
logger.error("Errors tracked with full context")
```

**Features:**

- Automatic detection of Sentry SDK configuration
- Level filtering (WARNING and above sent to Sentry)
- Exception capture with full stack traces via `logger.exception()`
- Rich context from `extra` parameter
- Breadcrumb support
- Framework integrations: `FlaskIntegration`, `DjangoIntegration`, `SentryAsgiMiddleware`
- Manual `SentryHandler` configuration for fine-grained control

**Full documentation:** [Sentry Integration](integrations/sentry.md)

---

### Datadog / New Relic / Other APMs

**Status:** ⚠️ Untested

Most APM tools hook into Python's stdlib logging module. Since logxide replaces `sys.modules["logging"]`, these tools should detect logxide's `_LoggingModule` as the logging module. However, APMs that:

- Monkey-patch `logging.Logger` class methods directly may conflict
- Install custom `logging.Handler` subclasses will work but bypass Rust performance
- Rely on `LogRecord` internal attributes may have issues with logxide's Rust `LogRecord`

If you use these tools with logxide, please report your results.

---

## Structured Logging Libraries

### structlog

**Status:** ❌ Not Compatible

structlog is fundamentally incompatible with logxide due to deep architectural differences:

1. **Custom Logger subclass** — structlog's `_FixedFindCallerLogger` extends `logging.Logger` to fix stack frame detection. LogXide's Logger is a Rust type that cannot be subclassed.

2. **ProcessorFormatter** — structlog's `ProcessorFormatter` extends `logging.Formatter` with a custom `format()` method that processes both structlog and stdlib records. On logxide's primary Rust code path, this custom `format()` is not called because Rust handles formatting. Even if a Python handler is attached, structlog's processor pipeline expects full control over the formatting chain, which conflicts with logxide's dual-pipeline architecture.

3. **Processor pipeline** — structlog wraps log records through a chain of Python processors before emission. This pipeline requires Python-side LogRecord manipulation that is incompatible with logxide's Rust pipeline.

**Alternative:** Use logxide's `HTTPHandler` with `transform_callback` for structured JSON output, or use logxide's format strings for structured log formatting:

```python
from logxide import HTTPHandler

handler = HTTPHandler(
    url="https://logs.example.com",
    transform_callback=lambda records: [
        {"event": r["msg"], "level": r["levelname"], "timestamp": r["asctime"]}
        for r in records
    ]
)
```

---

### python-json-logger

**Status:** ⚠️ Limited

`python-json-logger` provides `JsonFormatter`, a `logging.Formatter` subclass with a custom `format()` method. On logxide's primary Rust code path, the custom `format()` is not called. The formatter would only work if attached to a Python handler (which receives a separate Python LogRecord), but the Rust pipeline still formats and outputs independently.

**Workaround:** Use logxide's `HTTPHandler` with `transform_callback` for JSON-formatted log output:

```python
from logxide import HTTPHandler

handler = HTTPHandler(
    url="https://logs.example.com",
    transform_callback=lambda records: {
        "logs": [
            {"msg": r["msg"], "level": r["levelname"], "logger": r["name"]}
            for r in records
        ]
    }
)
```

---

## Testing

### pytest

**Status:** ⚠️ Partial | **Testing doc:** [Testing Guide](testing.md)

LogXide intentionally **skips** `sys.modules` replacement when pytest is detected to avoid breaking pytest internals. This means the standard `caplog` fixture does not capture logxide output.

**Use `caplog_logxide` instead:**

```python
def test_logging(caplog_logxide):
    from logxide import logging

    logger = logging.getLogger('test')
    logger.info('test message')

    assert 'test message' in caplog_logxide.text
```

**What works:**

- `caplog_logxide` fixture for log capture
- Logger creation and configuration in tests
- Handler and filter testing

**What doesn't work:**

- Standard `caplog` fixture (does not capture logxide output)
- `StringIO` stream capture (logxide writes through Rust, not Python streams)

---

### unittest

**Status:** ⚠️ Limited

`unittest` does not provide built-in log capture equivalent to pytest's `caplog`. For log-based assertions, use file-based logging:

!!! note "`logging.flush()` is LogXide-specific"
    The `logging.flush()` call used below is a logxide extension — it does not exist in stdlib `logging`. If your code needs to be portable between logxide and stdlib, guard the call: `if hasattr(logging, 'flush'): logging.flush()`

```python
import unittest
import tempfile
import os
from logxide import logging

class TestMyApp(unittest.TestCase):
    def test_logging_output(self):
        with tempfile.NamedTemporaryFile(
            mode='r', suffix='.log', delete=False
        ) as f:
            logging.basicConfig(filename=f.name, level=logging.INFO)
            logger = logging.getLogger('test')
            logger.info('test message')
            logging.flush()

            f.seek(0)
            content = f.read()
            self.assertIn('test message', content)
            os.unlink(f.name)
```

---

## Other Popular Libraries

### Scrapy

**Status:** ⚠️ Untested

Scrapy bridges Twisted's logging system (`twisted.python.log`) with Python's stdlib logging. This adds complexity:

- Scrapy installs a Twisted log observer that forwards to stdlib logging
- Each spider has its own logger via `self.logger`
- The `LOG_LEVEL` setting affects all logging globally

LogXide should intercept the stdlib side of Scrapy's logging, but the Twisted bridge layer has not been tested.

---

### Pandas / NumPy / SciPy

**Status:** ✅ Expected

These libraries use minimal logging. When they do log (typically warnings about deprecated features or data issues), they use standard `logging.getLogger(__name__)` or Python's `warnings` module. No compatibility concerns.

---

## Compatibility Decision Tree

Use this to determine if your third-party library will work with logxide:

```
Does the library use logging.getLogger() for loggers?
|
+-- YES --> Does it only call .debug()/.info()/.warning()/.error()/.critical()?
|   |
|   +-- YES --> Full compatibility (auto-intercepted)
|   |
|   +-- NO --> Does it subclass logging.Logger?
|       |
|       +-- YES --> Not compatible (Rust type, not subclassable)
|       |
|       +-- NO --> Does it use custom logging.Formatter subclass?
|           |
|           +-- YES --> Formatter's format() bypasses Rust pipeline
|           |
|               +-- NO --> Does it use custom logging.Handler subclass?
|               |
|               +-- YES --> Works (called alongside Rust pipeline), may cause duplicate output
|               |
|               +-- NO --> Full compatibility
|
+-- NO --> Does it use its own logging system?
    |
    +-- YES --> Not intercepted by logxide (separate system)
    |
    +-- NO --> Probably doesn't log --> No issues
```

---

## Troubleshooting

### Library logs not appearing

1. **Check import order** — LogXide must be imported before the library
2. **Check logger level** — The logger may default to WARNING
3. **Try `intercept_stdlib()`** — Captures loggers created before logxide was imported

```python
from logxide import logging
from logxide.interceptor import intercept_stdlib

intercept_stdlib()  # Capture all existing loggers
```

### Conflicting logging configurations

Some libraries call `logging.basicConfig()` on import. LogXide's patched `basicConfig()` handles this, but if you experience issues:

```python
# Import logxide FIRST, always
from logxide import logging
import problematic_library  # Its basicConfig() call is intercepted
```

### Custom handlers causing duplicate output

Python `logging.Handler` subclasses are called **in addition to** the Rust pipeline, not instead of it. This means each log event is processed twice — once by Rust handlers and once by your Python handler. If you see duplicate output, this is likely the cause.

To use only the Rust pipeline, replace Python handlers with Rust-native equivalents:

| Python Handler | LogXide Equivalent |
|----------------|-------------------|
| `logging.FileHandler` | `logxide.FileHandler` |
| `logging.StreamHandler` | `logxide.StreamHandler` |
| `logging.handlers.RotatingFileHandler` | `logxide.RotatingFileHandler` |
| Custom HTTP handler | `logxide.HTTPHandler` |
| Custom OTLP handler | `logxide.OTLPHandler` |

---

## Reporting Compatibility

If you test logxide with a library not listed here, please report your findings:

- **What worked** and what didn't
- **Library version** and **Python version** tested
- Any **configuration** needed

File an issue at the [logxide repository](https://github.com/Indosaram/logxide/issues) with the label `compatibility`.
