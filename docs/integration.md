# Web Framework Integration Guide

This guide covers integrating LogXide with popular Python web frameworks: Flask, Django, and FastAPI. LogXide serves as a drop-in replacement for Python's standard logging module, providing superior performance through its Rust-powered async architecture.

## Table of Contents

- [Quick Start](#quick-start)
- [Flask Integration](#flask-integration)
- [Django Integration](#django-integration)
- [FastAPI Integration](#fastapi-integration)
- [Sentry Integration](#sentry-integration)
- [Performance Considerations](#performance-considerations)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Quick Start

For all frameworks, the integration pattern is identical and **ultra-simple**:

1. Replace `import logging` with `from logxide import logging`
2. Configure logging as you normally would
3. Use standard logging throughout your application

```python
from logxide import logging  # Auto-installs LogXide - no setup needed!

# Now import your framework and use logging normally
# LogXide is already integrated!
```

## Flask Integration

### Basic Setup

```python
from logxide import logging  # Auto-installs LogXide

from flask import Flask, request, jsonify

app = Flask(__name__)

# Configure logging with structured format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@app.route('/')
def hello():
    logger.info('Hello endpoint accessed')
    return jsonify({'message': 'Hello from Flask with LogXide!'})

if __name__ == '__main__':
    app.run(debug=True)
```

### Request Logging Middleware

Create middleware to log all incoming requests:

```python
from logxide import logging  # Auto-installs LogXide

from flask import Flask, request, g
import time

app = Flask(__name__)

# Configure detailed logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(thread)d] - %(message)s'
)

access_logger = logging.getLogger('flask.access')
error_logger = logging.getLogger('flask.error')

@app.before_request
def log_request_info():
    """Log incoming request details."""
    g.start_time = time.time()
    access_logger.info(
        f'{request.method} {request.url} - '
        f'User-Agent: {request.headers.get("User-Agent", "Unknown")}'
    )

@app.after_request
def log_request_completion(response):
    """Log request completion with timing."""
    duration = time.time() - g.start_time
    access_logger.info(
        f'{request.method} {request.url} - '
        f'Status: {response.status_code} - '
        f'Duration: {duration:.3f}s'
    )
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    """Log unhandled exceptions."""
    error_logger.exception(f'Unhandled exception: {str(e)}')
    return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/users/<int:user_id>')
def get_user(user_id):
    logger = logging.getLogger('api.users')
    logger.info(f'Fetching user {user_id}')

    # Simulate some processing
    if user_id == 404:
        logger.warning(f'User {user_id} not found')
        return jsonify({'error': 'User not found'}), 404

    logger.info(f'Successfully retrieved user {user_id}')
    return jsonify({'user_id': user_id, 'name': f'User {user_id}'})
```

### Flask-SQLAlchemy Integration

```python
from logxide import logging  # Auto-installs LogXide

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable SQLAlchemy logging through LogXide
sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
sqlalchemy_logger.setLevel(logging.INFO)

app_logger = logging.getLogger('app')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)

@app.route('/users', methods=['POST'])
def create_user():
    app_logger.info('Creating new user')

    user = User(username='testuser')
    db.session.add(user)
    db.session.commit()

    app_logger.info(f'User created with ID: {user.id}')
    return {'user_id': user.id, 'username': user.username}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
```

## Django Integration

### Settings Configuration

Add LogXide configuration to your Django settings:

```python
# settings.py
from logxide import logging  # Auto-installs LogXide

# ... other Django settings ...

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} - {name} - {levelname} - {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'django.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'myapp': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
```

### Custom Middleware

Create custom middleware for request logging:

```python
# middleware.py
import logging
import time
from django.utils.deprecation import MiddlewareMixin

class LogXideRequestMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('django.request')
        super().__init__(get_response)

    def process_request(self, request):
        """Log incoming request."""
        request._start_time = time.time()
        self.logger.info(
            f'{request.method} {request.path} - '
            f'User: {getattr(request.user, "username", "anonymous")} - '
            f'IP: {self.get_client_ip(request)}'
        )

    def process_response(self, request, response):
        """Log request completion."""
        duration = time.time() - getattr(request, '_start_time', time.time())
        self.logger.info(
            f'{request.method} {request.path} - '
            f'Status: {response.status_code} - '
            f'Duration: {duration:.3f}s'
        )
        return response

    def get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
```

### Views and Models

```python
# views.py
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import User

logger = logging.getLogger('myapp.views')

@csrf_exempt
@require_http_methods(["GET", "POST"])
def user_list(request):
    if request.method == 'GET':
        logger.info('Fetching user list')
        users = User.objects.all()
        logger.info(f'Found {users.count()} users')

        return JsonResponse({
            'users': [{'id': u.id, 'username': u.username} for u in users]
        })

    elif request.method == 'POST':
        logger.info('Creating new user')

        try:
            import json
            data = json.loads(request.body)
            user = User.objects.create(username=data['username'])

            logger.info(f'User created: {user.username} (ID: {user.id})')
            return JsonResponse({'user_id': user.id, 'username': user.username})

        except Exception as e:
            logger.error(f'Error creating user: {str(e)}')
            return JsonResponse({'error': 'Failed to create user'}, status=400)

# models.py
import logging
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger('myapp.models')

class User(models.Model):
    username = models.CharField(max_length=150, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username

@receiver(post_save, sender=User)
def log_user_created(sender, instance, created, **kwargs):
    """Log user creation via Django signals."""
    if created:
        logger.info(f'New user created: {instance.username}')
```

### Management Commands

```python
# management/commands/log_demo.py
import logging
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Demonstrate LogXide logging in Django management command'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=100)

    def handle(self, *args, **options):
        logger = logging.getLogger('django.management')

        count = options['count']
        logger.info(f'Starting log demo with {count} messages')

        for i in range(count):
            logger.info(f'Demo message {i + 1}/{count}')

        # Ensure all logs are processed
        logging.flush()

        self.stdout.write(
            self.style.SUCCESS(f'Successfully logged {count} messages')
        )
```

## FastAPI Integration

### Basic Setup

```python
from logxide import logging  # Auto-installs LogXide

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import time

app = FastAPI(title="LogXide FastAPI Integration")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class UserCreate(BaseModel):
    username: str

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests."""
    start_time = time.time()

    logger.info(f'{request.method} {request.url.path} - Client: {request.client.host}')

    response = await call_next(request)

    duration = time.time() - start_time
    logger.info(
        f'{request.method} {request.url.path} - '
        f'Status: {response.status_code} - '
        f'Duration: {duration:.3f}s'
    )

    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Log unhandled exceptions."""
    logger.exception(f'Unhandled exception on {request.method} {request.url.path}: {str(exc)}')
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )

@app.get("/")
async def root():
    """Root endpoint."""
    logger.info("Root endpoint accessed")
    return {"message": "FastAPI with LogXide", "status": "running"}

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """Get user by ID."""
    logger.info(f'Fetching user {user_id}')

    if user_id == 404:
        logger.warning(f'User {user_id} not found')
        raise HTTPException(status_code=404, detail="User not found")

    logger.info(f'Successfully retrieved user {user_id}')
    return {"user_id": user_id, "username": f"user_{user_id}"}

@app.post("/users")
async def create_user(user: UserCreate):
    """Create a new user."""
    logger.info(f'Creating user: {user.username}')

    # Simulate processing
    user_id = hash(user.username) % 10000

    logger.info(f'User created: {user.username} (ID: {user_id})')
    return {"user_id": user_id, "username": user.username}
```

### Background Tasks with Logging

```python
from logxide import logging  # Auto-installs LogXide

from fastapi import FastAPI, BackgroundTasks
import asyncio

app = FastAPI()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(thread)d] - %(message)s'
)

task_logger = logging.getLogger('background_tasks')

async def process_data(task_id: str, data: dict):
    """Background task with logging."""
    task_logger.info(f'Starting background task {task_id}')

    try:
        # Simulate processing
        await asyncio.sleep(2)

        task_logger.info(f'Processing data for task {task_id}: {len(data)} items')

        # Simulate some work
        for i in range(10):
            task_logger.debug(f'Task {task_id} - Processing item {i}')
            await asyncio.sleep(0.1)

        task_logger.info(f'Task {task_id} completed successfully')

    except Exception as e:
        task_logger.error(f'Task {task_id} failed: {str(e)}')
        raise

@app.post("/process")
async def start_processing(background_tasks: BackgroundTasks):
    """Start background processing."""
    task_id = "task_123"
    data = {"items": list(range(100))}

    background_tasks.add_task(process_data, task_id, data)

    logger.info(f'Queued background task {task_id}')
    return {"task_id": task_id, "status": "queued"}
```

### Database Integration (SQLAlchemy)

```python
from logxide import logging  # Auto-installs LogXide

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable SQLAlchemy logging through LogXide
sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
sqlalchemy_logger.setLevel(logging.INFO)

app_logger = logging.getLogger('fastapi.app')

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)

Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/users/")
async def create_user(username: str, db: Session = Depends(get_db)):
    """Create user with database logging."""
    app_logger.info(f'Creating user: {username}')

    db_user = User(username=username)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    app_logger.info(f'User created: {username} (ID: {db_user.id})')
    return {"user_id": db_user.id, "username": db_user.username}

@app.get("/users/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user with database logging."""
    app_logger.info(f'Fetching user {user_id}')

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        app_logger.warning(f'User {user_id} not found')
        raise HTTPException(status_code=404, detail="User not found")

    app_logger.info(f'Successfully retrieved user {user_id}')
    return {"user_id": user.id, "username": user.username}
```

## Sentry Integration

LogXide provides automatic integration with Sentry for error tracking and monitoring. When Sentry is configured in your application, LogXide automatically detects it and sends WARNING, ERROR, and CRITICAL level logs to Sentry.

### Quick Setup

```python
# 1. Configure Sentry (once in your app)
import sentry_sdk
sentry_sdk.init(
    dsn="https://your-dsn@sentry.io/project-id",
    environment="production",
)

# 2. Use LogXide normally - Sentry integration is automatic!
from logxide import logging

logger = logging.getLogger(__name__)

# These automatically go to Sentry
logger.warning("This warning appears in Sentry")
logger.error("This error is tracked in Sentry")
```

### Framework-Specific Examples

**Flask with Sentry:**
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
    logger.exception("Internal server error", exc_info=error)
    return "Internal Server Error", 500
```

**Django with Sentry:**
```python
# settings.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn="your-dsn",
    integrations=[DjangoIntegration()]
)

# In your views
from logxide import logging
logger = logging.getLogger(__name__)

def my_view(request):
    try:
        process_request(request)
    except Exception as e:
        logger.exception("Request processing failed")
        raise
```

**FastAPI with Sentry:**
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

For complete Sentry integration documentation, see the [Sentry Integration Guide](sentry.md).

## Performance Considerations

### Async Logging Benefits

LogXide's async architecture provides significant performance benefits for web applications:

```python
from logxide import logging  # Auto-installs LogXide
import time
import asyncio

# Configure high-performance logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def performance_test():
    """Demonstrate high-performance logging."""
    logger = logging.getLogger('performance')

    # Log many messages without blocking
    start_time = time.time()

    for i in range(10000):
        logger.info(f'High-volume message {i}')

    # Async logging doesn't block here
    immediate_time = time.time()

    # Wait for all logs to be processed
    logging.flush()

    final_time = time.time()

    print(f"Time to queue 10,000 messages: {immediate_time - start_time:.3f}s")
    print(f"Time to process all messages: {final_time - start_time:.3f}s")
    print(f"Messages per second: {10000 / (final_time - start_time):.0f}")

if __name__ == "__main__":
    asyncio.run(performance_test())
```

### Memory Efficiency

LogXide manages memory efficiently in high-load scenarios:

```python
from logxide import logging  # Auto-installs LogXide
import psutil
import os

def memory_usage_test():
    """Test memory usage with high-volume logging."""
    logger = logging.getLogger('memory_test')

    process = psutil.Process(os.getpid())

    # Baseline memory
    baseline_mb = process.memory_info().rss / 1024 / 1024
    print(f"Baseline memory: {baseline_mb:.1f} MB")

    # Log many messages
    for i in range(100000):
        logger.info(f'Memory test message {i} - ' + 'x' * 100)

    # Memory after logging
    after_logging_mb = process.memory_info().rss / 1024 / 1024
    print(f"Memory after logging: {after_logging_mb:.1f} MB")

    # Flush and check final memory
    logging.flush()
    final_mb = process.memory_info().rss / 1024 / 1024
    print(f"Final memory: {final_mb:.1f} MB")

    print(f"Memory increase: {final_mb - baseline_mb:.1f} MB")

if __name__ == "__main__":
    memory_usage_test()
```

## Best Practices

### 1. Simple Import Pattern

Always use the LogXide import pattern - it's automatic:

```python
# ✅ Correct - Simple and automatic
from logxide import logging

from flask import Flask
# or
from django.conf import settings
# or
from fastapi import FastAPI

# ❌ Don't do this - install() is called automatically
import logging  # Standard logging without LogXide
```

### 2. Structured Logging

Use structured logging formats for better observability:

```python
# Production-ready format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - '
           '[%(process)d:%(thread)d] - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
```

### 3. Logger Hierarchy

Organize loggers in a hierarchy for better control:

```python
# Application loggers
app_logger = logging.getLogger('myapp')
db_logger = logging.getLogger('myapp.database')
auth_logger = logging.getLogger('myapp.auth')
api_logger = logging.getLogger('myapp.api')

# Third-party loggers
sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
requests_logger = logging.getLogger('urllib3.connectionpool')
```

### 4. Context Information

Include relevant context in log messages:

```python
# Include request context
logger.info(f'User {user_id} accessed {endpoint} from {ip_address}')

# Include timing information
logger.info(f'Database query completed in {duration:.3f}s')

# Include transaction IDs
logger.info(f'[{transaction_id}] Processing payment for user {user_id}')
```

### 5. Proper Flush Usage

Use `logging.flush()` at appropriate times:

```python
# Before application shutdown
@app.on_event("shutdown")
async def shutdown_event():
    logging.flush()

# After critical operations
try:
    critical_operation()
    logger.info("Critical operation completed")
    logging.flush()  # Ensure logs are written
except Exception as e:
    logger.error(f"Critical operation failed: {e}")
    logging.flush()
    raise
```

## Troubleshooting

### Common Issues

1. **LogXide not capturing framework logs**
   - Ensure you use `from logxide import logging` (auto-installs LogXide)
   - Check that the framework's logging configuration isn't overriding LogXide

2. **Performance not as expected**
   - Verify you're using async-compatible patterns
   - Check log levels - debug logging can impact performance
   - Use `logging.flush()` only when necessary

3. **Missing log messages**
   - Call `logging.flush()` before application shutdown
   - Check if log levels are filtering out messages
   - Verify handlers are configured correctly

### Debug Configuration

Enable debug logging to troubleshoot issues:

```python
from logxide import logging  # Auto-installs LogXide

# Enable debug logging for LogXide itself
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable debug for specific components
logging.getLogger('logxide').setLevel(logging.DEBUG)
logging.getLogger('werkzeug').setLevel(logging.DEBUG)  # Flask
logging.getLogger('django').setLevel(logging.DEBUG)    # Django
logging.getLogger('uvicorn').setLevel(logging.DEBUG)   # FastAPI
```

### Performance Monitoring

Monitor LogXide performance in production:

```python
import logging
import time
from functools import wraps

def log_performance(func):
    """Decorator to log function performance."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger('performance')
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f'{func.__name__} completed in {duration:.3f}s')
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f'{func.__name__} failed after {duration:.3f}s: {str(e)}')
            raise

    return wrapper

# Usage
@log_performance
def database_query():
    # Your database operation here
    pass
```

## Conclusion

LogXide provides seamless integration with Flask, Django, and FastAPI while delivering superior performance through its Rust-powered async architecture. By following the patterns and best practices outlined in this guide, you can leverage LogXide's capabilities to build high-performance web applications with comprehensive logging.

Key takeaways:
- Use `from logxide import logging` (auto-installs LogXide)
- Leverage structured logging for better observability
- Take advantage of async logging for high-performance applications
- Use proper logger hierarchies and context information
- Monitor performance and flush logs appropriately

For more examples and advanced usage, check the `examples/` directory in the LogXide repository.
