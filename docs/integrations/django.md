# Django Integration

## Settings Configuration

Add LogXide configuration to your Django settings:

```python
# settings.py
from logxide import logging

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

## Custom Middleware

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

## Views and Models

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

## Management Commands

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

## Sentry with Django

See the [Sentry Integration Guide](sentry.md) for detailed Sentry setup. Quick example:

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
