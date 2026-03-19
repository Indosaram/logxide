# Framework Integration Overview

LogXide integrates with popular Python web frameworks. The integration pattern is simple: replace `import logging` with `from logxide import logging`.

## Quick Start

For all frameworks, the integration is identical:

```python
from logxide import logging

# Configure logging as you normally would
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Use standard logging throughout your application
logger = logging.getLogger(__name__)
```

## Framework Guides

- **[Flask Integration](flask.md)** — Basic setup, request logging middleware, SQLAlchemy
- **[Django Integration](django.md)** — Settings, middleware, views, management commands
- **[FastAPI Integration](fastapi.md)** — Basic setup, background tasks, SQLAlchemy
- **[Sentry Integration](sentry.md)** — Automatic error tracking with Sentry

## Best Practices

### 1. Structured Logging

Use structured formats for better observability:

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - '
           '[%(process)d:%(thread)d] - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
```

### 2. Logger Hierarchy

Organize loggers for granular control:

```python
app_logger = logging.getLogger('myapp')
db_logger = logging.getLogger('myapp.database')
auth_logger = logging.getLogger('myapp.auth')
api_logger = logging.getLogger('myapp.api')
```

### 3. Context Information

Include relevant context in log messages:

```python
logger.info(f'User {user_id} accessed {endpoint} from {ip_address}')
logger.info(f'Database query completed in {duration:.3f}s')
logger.info(f'[{transaction_id}] Processing payment for user {user_id}')
```

### 4. Proper Flush

Always flush before shutdown:

```python
# Before application shutdown
@app.on_event("shutdown")
async def shutdown_event():
    logging.flush()

# After critical operations
try:
    critical_operation()
    logger.info("Critical operation completed")
    logging.flush()
except Exception as e:
    logger.error(f"Critical operation failed: {e}")
    logging.flush()
    raise
```

## Troubleshooting

### Common Issues

1. **LogXide not capturing framework logs**
   - Ensure you use `from logxide import logging`
   - Check that the framework's logging configuration isn't overriding LogXide

2. **Missing log messages**
   - Call `logging.flush()` before application shutdown
   - Check if log levels are filtering out messages

3. **Performance not as expected**
   - Check log levels — debug logging can impact performance
   - Use `logging.flush()` only when necessary

### Debug Configuration

```python
from logxide import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable debug for specific components
logging.getLogger('werkzeug').setLevel(logging.DEBUG)  # Flask
logging.getLogger('django').setLevel(logging.DEBUG)    # Django
logging.getLogger('uvicorn').setLevel(logging.DEBUG)   # FastAPI
```
