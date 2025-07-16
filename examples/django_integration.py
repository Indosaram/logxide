#!/usr/bin/env python3
"""
Django Integration Example with LogXide

This example demonstrates comprehensive Django integration with LogXide,
showcasing settings configuration, middleware, views, models, and
management commands.

To run this example:
1. pip install django
2. python django_integration.py migrate
3. python django_integration.py runserver
"""

import os
import sys

import django
from django.conf import settings
from django.core.management import execute_from_command_line

# Install LogXide before any Django imports
from logxide import logging

# Django settings configuration
if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY="django-insecure-example-key-for-demo-only",
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": "django_logxide_demo.db",
            }
        },
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
        ],
        MIDDLEWARE=[
            "django.middleware.security.SecurityMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
        ],
        ROOT_URLCONF=__name__,
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [],
                "APP_DIRS": True,
                "OPTIONS": {
                    "context_processors": [
                        "django.template.context_processors.debug",
                        "django.template.context_processors.request",
                        "django.contrib.auth.context_processors.auth",
                        "django.contrib.messages.context_processors.messages",
                    ],
                },
            }
        ],
        USE_TZ=True,
        # LogXide logging configuration
        LOGGING={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "verbose": {
                    "format": "{asctime} - {name} - {levelname} - [{process}:{thread}] - {message}",
                    "style": "{",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
                "simple": {
                    "format": "{levelname} - {name} - {message}",
                    "style": "{",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "verbose",
                },
                "file": {
                    "class": "logging.FileHandler",
                    "filename": "django_logxide.log",
                    "formatter": "verbose",
                },
            },
            "loggers": {
                "django": {
                    "handlers": ["console", "file"],
                    "level": "INFO",
                    "propagate": True,
                },
                "django.request": {
                    "handlers": ["console", "file"],
                    "level": "INFO",
                    "propagate": False,
                },
                "myapp": {
                    "handlers": ["console", "file"],
                    "level": "INFO",
                    "propagate": True,
                },
            },
            "root": {
                "handlers": ["console", "file"],
                "level": "INFO",
            },
        },
    )

# Initialize Django
django.setup()

# Now we can import Django components
import json
import time
from functools import wraps

from django.contrib.auth.models import User as AuthUser
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.urls import path
from django.utils.decorators import method_decorator
from django.utils.deprecation import MiddlewareMixin
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

# Create loggers
app_logger = logging.getLogger("myapp")
request_logger = logging.getLogger("myapp.requests")
db_logger = logging.getLogger("myapp.database")
performance_logger = logging.getLogger("myapp.performance")


# Models
class User(models.Model):
    username = models.CharField(max_length=150, unique=True)
    email = models.CharField(max_length=254)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "django_integration"

    def __str__(self):
        return self.username

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
        }


class ApiLog(models.Model):
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=200)
    status_code = models.IntegerField()
    duration = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "django_integration"
        ordering = ["-timestamp"]


# Middleware
class LogXideRequestMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request):
        """Log incoming request."""
        request._start_time = time.time()
        request._client_ip = self.get_client_ip(request)

        request_logger.info(
            f"{request.method} {request.path} - "
            f"User: {getattr(request.user, 'username', 'anonymous')} - "
            f"IP: {request._client_ip}"
        )

    def process_response(self, request, response):
        """Log request completion and store metrics."""
        duration = time.time() - getattr(request, "_start_time", time.time())

        request_logger.info(
            f"{request.method} {request.path} - "
            f"Status: {response.status_code} - "
            f"Duration: {duration:.3f}s"
        )

        # Store API metrics (async operation won't block response)
        try:
            ApiLog.objects.create(
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                duration=duration,
            )
            db_logger.debug(f"API metrics logged for {request.method} {request.path}")
        except Exception as e:
            db_logger.error(f"Failed to log API metrics: {str(e)}")

        return response

    def process_exception(self, request, exception):
        """Log unhandled exceptions."""
        request_logger.exception(
            f"Unhandled exception on {request.method} {request.path}: {str(exception)}"
        )
        return None

    def get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return request.META.get("REMOTE_ADDR")


# Add middleware to settings
settings.MIDDLEWARE.insert(0, f"{__name__}.LogXideRequestMiddleware")


# Decorators
def log_performance(func):
    """Decorator to log function performance."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            performance_logger.info(f"{func.__name__} completed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            performance_logger.error(
                f"{func.__name__} failed after {duration:.3f}s: {str(e)}"
            )
            raise

    return wrapper


# Views
def index(request):
    """Root endpoint."""
    app_logger.info("Index page accessed")
    return JsonResponse(
        {
            "message": "Django + LogXide Integration Demo",
            "endpoints": [
                "/",
                "/users/",
                "/users/<id>/",
                "/health/",
                "/metrics/",
                "/performance-test/",
                "/error-test/",
            ],
        }
    )


@csrf_exempt
@log_performance
def users_list(request):
    """Handle user operations."""
    if request.method == "GET":
        app_logger.info("Fetching all users")

        users = User.objects.all()
        app_logger.info(f"Found {users.count()} users")

        return JsonResponse(
            {"users": [user.to_dict() for user in users], "count": users.count()}
        )

    elif request.method == "POST":
        app_logger.info("Creating new user")

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            app_logger.warning("Invalid JSON in request body")
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        if "username" not in data or "email" not in data:
            app_logger.warning("Missing required fields in user creation")
            return JsonResponse(
                {"error": "Username and email are required"}, status=400
            )

        try:
            user = User.objects.create(username=data["username"], email=data["email"])

            app_logger.info(f"User created: {user.username} (ID: {user.id})")
            return JsonResponse(user.to_dict(), status=201)

        except Exception as e:
            app_logger.error(f"Failed to create user: {str(e)}")
            return JsonResponse({"error": "Failed to create user"}, status=500)


@log_performance
def user_detail(request, user_id):
    """Get user by ID."""
    app_logger.info(f"Fetching user {user_id}")

    try:
        user = User.objects.get(id=user_id)
        app_logger.info(f"Successfully retrieved user {user_id}")
        return JsonResponse(user.to_dict())
    except User.DoesNotExist:
        app_logger.warning(f"User {user_id} not found")
        return JsonResponse({"error": "User not found"}, status=404)


def health_check(request):
    """Health check endpoint."""
    app_logger.info("Health check requested")

    # Check database connection
    try:
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_logger.error(f"Database health check failed: {str(e)}")
        db_status = "unhealthy"

    return JsonResponse(
        {
            "status": "healthy" if db_status == "healthy" else "degraded",
            "database": db_status,
            "logging": "logxide",
        }
    )


def metrics(request):
    """Get API usage metrics."""
    app_logger.info("Metrics requested")

    try:
        # Recent API calls
        recent_calls = ApiLog.objects.all()[:100]

        # Calculate average response time
        from django.db.models import Avg

        avg_duration = (
            ApiLog.objects.aggregate(avg_duration=Avg("duration"))["avg_duration"] or 0
        )

        # Count by status code
        from django.db.models import Count

        status_counts = ApiLog.objects.values("status_code").annotate(
            count=Count("status_code")
        )

        metrics_data = {
            "total_requests": ApiLog.objects.count(),
            "average_response_time": round(avg_duration, 3),
            "status_code_distribution": {
                str(item["status_code"]): item["count"] for item in status_counts
            },
            "recent_calls": [
                {
                    "method": call.method,
                    "path": call.path,
                    "status": call.status_code,
                    "duration": call.duration,
                    "timestamp": call.timestamp.isoformat(),
                }
                for call in recent_calls[:10]  # Show only last 10
            ],
        }

        app_logger.info(
            f"Metrics retrieved: {metrics_data['total_requests']} total requests"
        )
        return JsonResponse(metrics_data)

    except Exception as e:
        app_logger.error(f"Failed to retrieve metrics: {str(e)}")
        return JsonResponse({"error": "Failed to retrieve metrics"}, status=500)


def performance_test(request):
    """Test logging performance."""
    count = int(request.GET.get("count", 1000))
    app_logger.info(f"Starting performance test with {count} log messages")

    start_time = time.time()

    # Generate many log messages
    for i in range(count):
        performance_logger.debug(f"Performance test message {i + 1}/{count}")

    # Time to queue all messages
    queue_time = time.time() - start_time

    # Flush logs and measure total time
    logging.flush()
    total_time = time.time() - start_time

    app_logger.info(
        f"Performance test completed: {count} messages in {total_time:.3f}s "
        f"({count / total_time:.0f} msg/sec)"
    )

    return JsonResponse(
        {
            "messages": count,
            "queue_time": f"{queue_time:.3f}s",
            "total_time": f"{total_time:.3f}s",
            "messages_per_second": round(count / total_time, 2),
        }
    )


def error_test(request):
    """Test error handling and logging."""
    error_type = request.GET.get("type", "general")

    app_logger.warning(f"Error test requested: {error_type}")

    if error_type == "division":
        result = 10 / 0  # ZeroDivisionError
    elif error_type == "key":
        data = {}
        value = data["nonexistent_key"]  # KeyError
    elif error_type == "database":
        # Force a database error
        User.objects.get(id=99999)  # DoesNotExist
    else:
        raise ValueError(f"Test error: {error_type}")


# URL patterns
urlpatterns = [
    path("", index, name="index"),
    path("users/", users_list, name="users_list"),
    path("users/<int:user_id>/", user_detail, name="user_detail"),
    path("health/", health_check, name="health"),
    path("metrics/", metrics, name="metrics"),
    path("performance-test/", performance_test, name="performance_test"),
    path("error-test/", error_test, name="error_test"),
]


# Management Commands
class Command(BaseCommand):
    help = "Django LogXide integration demo commands"

    def add_arguments(self, parser):
        parser.add_argument(
            "--init-data",
            action="store_true",
            help="Initialize database with sample data",
        )
        parser.add_argument(
            "--test-logging",
            action="store_true",
            help="Test LogXide logging performance",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=10000,
            help="Number of log messages for testing",
        )

    def handle(self, *args, **options):
        if options["init_data"]:
            self.init_sample_data()
        elif options["test_logging"]:
            self.test_logging_performance(options["count"])
        else:
            self.stdout.write("Use --init-data or --test-logging")

    def init_sample_data(self):
        """Initialize database with sample data."""
        sample_users = [
            {"username": "alice", "email": "alice@example.com"},
            {"username": "bob", "email": "bob@example.com"},
            {"username": "charlie", "email": "charlie@example.com"},
        ]

        for user_data in sample_users:
            user, created = User.objects.get_or_create(
                username=user_data["username"], defaults={"email": user_data["email"]}
            )
            if created:
                app_logger.info(f"Created sample user: {user.username}")

        self.stdout.write(self.style.SUCCESS("Sample data initialized"))

    def test_logging_performance(self, count):
        """Test LogXide logging performance."""
        self.stdout.write(
            f"Testing LogXide logging performance with {count} messages..."
        )

        start_time = time.time()

        for i in range(count):
            app_logger.info(f"Test message {i + 1}")

        queue_time = time.time() - start_time

        logging.flush()
        total_time = time.time() - start_time

        self.stdout.write(f"Queued {count} messages in {queue_time:.3f}s")
        self.stdout.write(f"Total processing time: {total_time:.3f}s")
        self.stdout.write(f"Messages per second: {count / total_time:.0f}")


# Main execution
if __name__ == "__main__":
    # Create tables
    from django.core.management.commands.migrate import Command as MigrateCommand

    try:
        # Create tables
        call_command("migrate", verbosity=0)

        # Initialize sample data
        sample_users = [
            {"username": "alice", "email": "alice@example.com"},
            {"username": "bob", "email": "bob@example.com"},
            {"username": "charlie", "email": "charlie@example.com"},
        ]

        for user_data in sample_users:
            user, created = User.objects.get_or_create(
                username=user_data["username"], defaults={"email": user_data["email"]}
            )
            if created:
                app_logger.info(f"Created sample user: {user.username}")

        app_logger.info("Django application with LogXide initialized")

        # Run the Django development server
        execute_from_command_line(
            ["django_integration.py", "runserver", "0.0.0.0:8000"]
        )

    except KeyboardInterrupt:
        app_logger.info("Application shutting down")
        logging.flush()
    except Exception as e:
        app_logger.error(f"Application error: {str(e)}")
        logging.flush()
        raise
    finally:
        logging.flush()
