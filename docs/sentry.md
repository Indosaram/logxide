# Sentry Integration

LogXide provides seamless integration with [Sentry](https://sentry.io) for automatic error tracking and monitoring. When Sentry is configured in your application, LogXide automatically detects it and sends WARNING, ERROR, and CRITICAL level logs to Sentry.

## Installation

To use Sentry integration, install LogXide with the sentry extra:

```bash
pip install logxide[sentry]
```

## Quick Start

### Automatic Integration (Recommended)

LogXide automatically detects and integrates with Sentry when you configure it:

```python
# 1. Configure Sentry as usual
import sentry_sdk
sentry_sdk.init(
    dsn="https://your-dsn@sentry.io/project-id",
    environment="production",
    traces_sample_rate=1.0,
)

# 2. Use LogXide - Sentry integration is automatic!
from logxide import logging

logger = logging.getLogger(__name__)

# These will automatically go to Sentry
logger.warning("This warning will appear in Sentry")
logger.error("This error will be tracked in Sentry")
logger.critical("Critical issues are sent to Sentry")

# These won't go to Sentry (below WARNING level)
logger.info("Info messages are not sent to Sentry")
logger.debug("Debug messages are not sent to Sentry")
```

That's it! No additional configuration needed.

### Manual Handler Configuration

For more control, you can manually configure the Sentry handler:

```python
from logxide import logging, SentryHandler

# Create a logger
logger = logging.getLogger('myapp')

# Create and configure Sentry handler
sentry_handler = SentryHandler(
    level=logging.ERROR,  # Only send ERROR and above
    with_breadcrumbs=False  # Disable breadcrumbs
)

# Add handler to logger
logger.addHandler(sentry_handler)
```

## Features

### Automatic Level Filtering

By default, LogXide sends only WARNING level and above to Sentry to avoid noise:

- **DEBUG** ❌ Not sent to Sentry
- **INFO** ❌ Not sent to Sentry
- **WARNING** ✅ Sent to Sentry
- **ERROR** ✅ Sent to Sentry
- **CRITICAL** ✅ Sent to Sentry

### Exception Tracking

Exceptions are automatically captured with full stack traces:

```python
logger = logging.getLogger(__name__)

try:
    1 / 0
except ZeroDivisionError:
    # This sends the exception to Sentry with stack trace
    logger.exception("Division by zero occurred")
```

### Rich Context

LogXide automatically includes rich context in Sentry events:

```python
# Context is automatically included
logger.error("Database connection failed", extra={
    "database": "production",
    "host": "db.example.com",
    "retry_count": 3
})
```

The following context is automatically captured:
- Logger name
- Thread and process information
- Source code location (file, line, function)
- Timestamp
- Custom extra data

### Structured Logging with Sentry

Use Sentry's scope for additional context:

```python
import sentry_sdk

# Add user context
with sentry_sdk.configure_scope() as scope:
    scope.user = {"id": "123", "username": "alice"}
    logger.error("User action failed")  # Includes user context

# Add custom tags
with sentry_sdk.configure_scope() as scope:
    scope.set_tag("module", "payment")
    scope.set_tag("action", "process_order")
    logger.error("Payment processing failed")

# Add breadcrumbs for debugging
sentry_sdk.add_breadcrumb(
    message="User clicked checkout",
    category="ui",
    level="info"
)
logger.error("Checkout failed")  # Breadcrumb trail included
```

## Configuration Options

### Control Sentry Integration

You can explicitly control Sentry integration:

```python
from logxide import logging

# Force enable Sentry (even if not configured)
logging.basicConfig(handlers=[SentryHandler()])

# Disable Sentry integration
import logxide
logxide.install(sentry=False)  # Explicit disable

# Check if Sentry is available
from logxide import SentryHandler
if SentryHandler and SentryHandler().is_available:
    print("Sentry is configured and ready")
```

### Environment Variables

LogXide respects standard Sentry environment variables:

```bash
export SENTRY_DSN="https://your-dsn@sentry.io/project-id"
export SENTRY_ENVIRONMENT="production"
export SENTRY_RELEASE="myapp@1.0.0"
```

### Custom Filtering

Create custom filters to control what goes to Sentry:

```python
class SensitiveDataFilter(logging.Filter):
    def filter(self, record):
        # Don't send logs containing sensitive data to Sentry
        if hasattr(record, 'msg') and 'password' in str(record.msg).lower():
            return False
        return True

# Apply filter to Sentry handler
sentry_handler = SentryHandler()
sentry_handler.addFilter(SensitiveDataFilter())
logger.addHandler(sentry_handler)
```

## Best Practices

### 1. Use Appropriate Log Levels

```python
# Good practices
logger.debug("Detailed debug info")  # Development only
logger.info("User logged in")  # Normal operations
logger.warning("API rate limit approaching")  # Warnings to Sentry
logger.error("Failed to process payment")  # Errors to Sentry
logger.critical("Database connection lost")  # Critical to Sentry
```

### 2. Include Helpful Context

```python
# Include relevant context
logger.error("Order processing failed", extra={
    "order_id": order.id,
    "user_id": user.id,
    "payment_method": order.payment_method,
    "error_code": "PAYMENT_DECLINED"
})
```

### 3. Use Exception Logging

```python
try:
    process_order(order)
except ProcessingError as e:
    # Use exception() to include stack trace
    logger.exception("Order processing failed: %s", e, extra={
        "order_id": order.id
    })
```

### 4. Group Related Errors

```python
# Use consistent messages for grouping in Sentry
logger.error("Database query timeout", extra={
    "query": str(query),
    "duration": query_time,
    "table": "orders"
})
```

## Performance Considerations

### Asynchronous Sending

LogXide and Sentry both use asynchronous sending to avoid blocking:

```python
# This returns immediately
logger.error("Error message")  # Sent async to Sentry

# Force synchronous flush if needed
import sentry_sdk
sentry_sdk.flush()  # Wait for all events to be sent
```

### Rate Limiting

Sentry has built-in rate limiting. For high-volume applications:

```python
# Configure sampling
sentry_sdk.init(
    dsn="...",
    sample_rate=0.25,  # Send 25% of events
    traces_sample_rate=0.1,  # 10% of performance data
)
```

### Disable in Development

```python
import os

# Only enable Sentry in production
if os.getenv("ENVIRONMENT") == "production":
    sentry_sdk.init(dsn="...")

from logxide import logging  # Auto-detects Sentry config
```

## Troubleshooting

### Sentry Not Receiving Events

1. **Check Sentry Configuration**:
   ```python
   import sentry_sdk
   print(sentry_sdk.Hub.current.client)  # Should not be None
   ```

2. **Verify Handler is Active**:
   ```python
   from logxide import SentryHandler
   handler = SentryHandler()
   print(handler.is_available)  # Should be True
   ```

3. **Check Log Levels**:
   ```python
   # Make sure level is WARNING or above
   logger.setLevel(logging.WARNING)
   ```

4. **Force Flush**:
   ```python
   # Ensure events are sent before exit
   logging.flush()
   sentry_sdk.flush(timeout=2.0)
   ```

### Testing Sentry Integration

```python
# Test script
import sentry_sdk
sentry_sdk.init(dsn="your-dsn")

from logxide import logging
logger = logging.getLogger("test")

# Test different levels
logger.warning("Test warning")
logger.error("Test error")

try:
    raise ValueError("Test exception")
except ValueError:
    logger.exception("Test exception logging")

# Ensure delivery
logging.flush()
sentry_sdk.flush(timeout=2.0)
print("Check your Sentry dashboard!")
```

## Integration with Frameworks

### Flask

```python
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn="your-dsn",
    integrations=[FlaskIntegration()]
)

from flask import Flask
from logxide import logging

app = Flask(__name__)
logger = logging.getLogger(__name__)

@app.errorhandler(500)
def handle_error(error):
    logger.error("Internal server error", exc_info=error)
    return "Internal Server Error", 500
```

### Django

```python
# settings.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn="your-dsn",
    integrations=[DjangoIntegration()]
)

# Use LogXide in your views
from logxide import logging
logger = logging.getLogger(__name__)

def my_view(request):
    logger.info("View accessed")  # Not sent to Sentry
    logger.error("View error")  # Sent to Sentry
```

### FastAPI

```python
import sentry_sdk
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

sentry_sdk.init(dsn="your-dsn")

from fastapi import FastAPI
from logxide import logging

app = FastAPI()
app.add_middleware(SentryAsgiMiddleware)

logger = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def exception_handler(request, exc):
    logger.exception("Unhandled exception", exc_info=exc)
    return {"error": "Internal server error"}
```

## Advanced Usage

### Custom Event Processors

```python
def process_event(event, hint):
    # Modify event before sending to Sentry
    if 'user' in event:
        # Anonymize user data
        event['user']['id'] = hash(event['user'].get('id', ''))
    return event

sentry_sdk.init(
    dsn="your-dsn",
    before_send=process_event
)
```

### Performance Monitoring

```python
import sentry_sdk

# Enable performance monitoring
sentry_sdk.init(
    dsn="your-dsn",
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

# LogXide will include timing information
with sentry_sdk.start_transaction(op="process", name="order_processing"):
    logger.info("Processing order")
    # ... processing logic ...
    logger.info("Order processed")
```

## Security Considerations

### Filtering Sensitive Data

```python
# Don't log sensitive information
logger.error("Login failed for user", extra={
    "username": user.username,
    # Don't include: "password": user.password
})

# Use Sentry's data scrubbing
sentry_sdk.init(
    dsn="your-dsn",
    send_default_pii=False,  # Don't send personally identifiable info
)
```

### Compliance

For GDPR and privacy compliance:

```python
sentry_sdk.init(
    dsn="your-dsn",
    attach_stacktrace=False,  # Don't attach stack traces
    send_default_pii=False,  # Don't send PII
    request_bodies="never",  # Never send request bodies
)
```

## Summary

LogXide's Sentry integration provides:

- 🚀 **Zero-configuration** automatic integration
- 🎯 **Smart filtering** of log levels
- 📊 **Rich context** capture
- 🔒 **Security-conscious** defaults
- ⚡ **High performance** with async sending
- 🛠️ **Full control** when needed

Just install, configure Sentry as usual, and LogXide handles the rest!
