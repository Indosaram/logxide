#!/usr/bin/env python3
"""
Sentry Integration Example with LogXide

This example demonstrates how LogXide automatically integrates with Sentry
to send WARNING, ERROR, and CRITICAL level logs to Sentry for error tracking.

To run this example:
1. Install dependencies: pip install logxide[sentry]
2. Set your Sentry DSN: export SENTRY_DSN="your-sentry-dsn-here"
3. Run: python sentry_integration.py

Features demonstrated:
- Automatic Sentry detection and integration
- Log level filtering (WARNING and above)
- Exception capture with stack traces
- Structured logging with extra context
- Manual Sentry handler configuration
- Integration with different frameworks
"""

import os
import sys
import time
from typing import Any

# Check if Sentry SDK is available
try:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration

    HAS_SENTRY_SDK = True
except ImportError:
    HAS_SENTRY_SDK = False
    print("⚠️  sentry-sdk is not installed.")
    print("   Install it with: pip install logxide[sentry]")
    print("   Exiting example.")
    sys.exit(1)

# Get Sentry DSN from environment or use a demo DSN
SENTRY_DSN = os.getenv("SENTRY_DSN")

if not SENTRY_DSN:
    print("⚠️  No SENTRY_DSN environment variable found.")
    print(
        "   Set SENTRY_DSN to your actual Sentry project DSN to see events in Sentry."
    )
    print("   Running example without Sentry to demonstrate LogXide functionality.")
    print()
    # Don't configure Sentry if no valid DSN
    SENTRY_CONFIGURED = False
else:
    print(f"✅ Using Sentry DSN: {SENTRY_DSN[:20]}...")
    SENTRY_CONFIGURED = True

# Configure Sentry only if we have a valid DSN
if SENTRY_CONFIGURED:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment="demo",
        release="sentry-integration-example@1.0.0",
        traces_sample_rate=1.0,
        # Don't use Sentry's logging integration since LogXide handles it
        integrations=[],
        # Add some global context
        before_send=lambda event, hint: event,  # You can modify events here
    )

# Import LogXide AFTER Sentry is configured
from logxide import logging

# LogXide will automatically detect Sentry and add a SentryHandler!

# Configure basic logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(process)d:%(thread)d] - %(message)s",
)

# Create loggers for different parts of the application
app_logger = logging.getLogger("myapp")
db_logger = logging.getLogger("myapp.database")
api_logger = logging.getLogger("myapp.api")
auth_logger = logging.getLogger("myapp.auth")


def demo_basic_logging():
    """Demonstrate basic logging with automatic Sentry integration."""
    print("=== Basic Logging Demo ===")

    # These won't go to Sentry (below WARNING level)
    app_logger.debug("Debug message - won't appear in Sentry")
    app_logger.info("Info message - won't appear in Sentry")

    # These WILL go to Sentry (WARNING level and above)
    app_logger.warning("This is a warning that will appear in Sentry")
    app_logger.error("This is an error that will appear in Sentry")
    app_logger.critical("This is critical and will appear in Sentry")

    print("✓ Basic logging messages sent (check Sentry for WARNING/ERROR/CRITICAL)")
    print()


def demo_exception_handling():
    """Demonstrate exception logging with Sentry integration."""
    print("=== Exception Handling Demo ===")

    try:
        # This will cause a ZeroDivisionError
        result = 10 / 0
    except Exception as e:
        # LogXide will automatically send this exception to Sentry
        app_logger.exception("An error occurred during calculation")

    try:
        # This will cause a KeyError
        data = {"name": "Alice"}
        value = data["age"]  # Key doesn't exist
    except Exception as e:
        # Another exception with additional context
        app_logger.error("Failed to access user data: %s", str(e), exc_info=True)

    print("✓ Exceptions sent to Sentry with full stack traces")
    print()


def demo_structured_logging():
    """Demonstrate structured logging with extra context."""
    print("=== Structured Logging Demo ===")

    # Add user context to Sentry
    with sentry_sdk.configure_scope() as scope:
        scope.user = {"id": "123", "username": "alice", "email": "alice@example.com"}
        scope.set_tag("component", "user_management")

        # These logs will include the user context
        auth_logger.warning("Failed login attempt for user")
        auth_logger.error("Account locked due to multiple failed attempts")

    # Database operation with custom context
    operation_id = "db_op_456"
    with sentry_sdk.configure_scope() as scope:
        scope.set_extra("operation_id", operation_id)
        scope.set_extra("table", "users")
        scope.set_tag("database", "postgresql")

        db_logger.error("Database connection timeout during user query")

    print("✓ Structured logs with user and operation context sent to Sentry")
    print()


def demo_api_error_tracking():
    """Demonstrate API error tracking simulation."""
    print("=== API Error Tracking Demo ===")

    # Simulate different API endpoints with errors
    endpoints = [
        {"path": "/api/users/123", "method": "GET", "status": 404},
        {"path": "/api/orders", "method": "POST", "status": 500},
        {"path": "/api/payments/process", "method": "POST", "status": 503},
    ]

    for endpoint in endpoints:
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("endpoint", endpoint["path"])
            scope.set_tag("method", endpoint["method"])
            scope.set_extra("status_code", endpoint["status"])

            if endpoint["status"] >= 500:
                api_logger.error(
                    f"Server error on {endpoint['method']} {endpoint['path']}: {endpoint['status']}"
                )
            elif endpoint["status"] >= 400:
                api_logger.warning(
                    f"Client error on {endpoint['method']} {endpoint['path']}: {endpoint['status']}"
                )

    print("✓ API errors with endpoint context sent to Sentry")
    print()


def demo_performance_monitoring():
    """Demonstrate performance monitoring with logging."""
    print("=== Performance Monitoring Demo ===")

    # Simulate slow operations
    operations = [
        {"name": "database_query", "duration": 2.5},
        {"name": "external_api_call", "duration": 5.2},
        {"name": "file_processing", "duration": 8.7},
    ]

    for op in operations:
        start_time = time.time()

        # Simulate the operation
        time.sleep(0.1)  # Small delay for demo

        duration = op["duration"]  # Use predefined duration for demo

        with sentry_sdk.configure_scope() as scope:
            scope.set_extra("operation", op["name"])
            scope.set_extra("duration_seconds", duration)

            if duration > 5.0:
                app_logger.error(
                    f"Operation '{op['name']}' is extremely slow: {duration:.1f}s"
                )
            elif duration > 2.0:
                app_logger.warning(f"Operation '{op['name']}' is slow: {duration:.1f}s")

    print("✓ Performance issues logged to Sentry")
    print()


def demo_manual_sentry_handler():
    """Demonstrate manual Sentry handler configuration."""
    print("=== Manual Sentry Handler Demo ===")

    # Create a custom logger with manual Sentry configuration
    custom_logger = logging.getLogger("myapp.custom")

    # Import and add Sentry handler manually
    from logxide import SentryHandler

    if SentryHandler is not None:
        # Create handler with custom configuration
        sentry_handler = SentryHandler(
            level=logging.ERROR,  # Only send ERROR and above
            with_breadcrumbs=False,  # Disable breadcrumbs
        )

        # Add to our custom logger
        custom_logger.addHandler(sentry_handler)

        # Test the custom configuration
        custom_logger.warning("This warning won't go to Sentry (below ERROR level)")
        custom_logger.error("This error will go to Sentry")

        print("✓ Manual Sentry handler configured and tested")
    else:
        print("❌ SentryHandler not available (sentry-sdk not installed)")

    print()


def demo_framework_integration():
    """Demonstrate integration with web frameworks."""
    print("=== Framework Integration Demo ===")

    # Simulate Flask request handling
    request_logger = logging.getLogger("flask.request")

    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("framework", "flask")
        scope.set_extra("request_id", "req_789")
        scope.set_extra("user_agent", "Mozilla/5.0 ...")
        scope.set_extra("ip_address", "192.168.1.100")

        request_logger.error("Flask request failed: Internal Server Error")

    # Simulate Django model error
    django_logger = logging.getLogger("django.request")

    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("framework", "django")
        scope.set_extra("view", "UserDetailView")
        scope.set_extra("model", "User")

        django_logger.warning("Django model validation failed")

    # Simulate FastAPI dependency error
    fastapi_logger = logging.getLogger("fastapi.dependencies")

    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("framework", "fastapi")
        scope.set_extra("endpoint", "/api/v1/users")
        scope.set_extra("dependency", "get_current_user")

        fastapi_logger.error("FastAPI dependency injection failed")

    print("✓ Framework-specific errors logged with context")
    print()


def demo_batch_processing():
    """Demonstrate batch processing with error tracking."""
    print("=== Batch Processing Demo ===")

    batch_logger = logging.getLogger("myapp.batch")

    # Simulate processing a batch of items
    batch_id = "batch_2024_001"
    total_items = 100

    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("batch_id", batch_id)
        scope.set_extra("total_items", total_items)

        # Simulate some failures
        failed_items = [15, 32, 67, 89]

        for item_id in failed_items:
            with sentry_sdk.configure_scope() as item_scope:
                item_scope.set_extra("item_id", item_id)
                item_scope.set_extra("batch_progress", f"{item_id}/{total_items}")

                if item_id == 67:
                    # Critical failure
                    batch_logger.critical(
                        f"Critical failure processing item {item_id} in batch {batch_id}"
                    )
                else:
                    # Regular error
                    batch_logger.error(
                        f"Failed to process item {item_id} in batch {batch_id}"
                    )

        # Summary
        batch_logger.warning(
            f"Batch {batch_id} completed with {len(failed_items)} failures out of {total_items} items"
        )

    print("✓ Batch processing errors tracked with item-level context")
    print()


def main():
    """Run all Sentry integration demos."""
    print("🚀 LogXide Sentry Integration Demo")
    print("=" * 50)
    print()

    # Check if Sentry integration is working
    from logxide import SentryHandler, auto_configure_sentry

    if SentryHandler is None:
        print("❌ Sentry integration not available!")
        print("   Install with: pip install logxide[sentry]")
        return 1

    # Check if auto-configuration worked
    test_handler = auto_configure_sentry()
    if test_handler and test_handler.is_available:
        print("✅ Sentry integration is active and configured")
        if SENTRY_CONFIGURED:
            print(
                f"   DSN configured: {SENTRY_DSN[:20]}..."
                if len(SENTRY_DSN) > 20
                else SENTRY_DSN
            )
    else:
        print("⚠️  Sentry integration available but not fully configured")
        if not SENTRY_CONFIGURED:
            print("   No valid SENTRY_DSN provided - running in demo mode")
        else:
            print("   Make sure SENTRY_DSN is set and valid")

    print()

    # Run all demos
    demo_basic_logging()
    demo_exception_handling()
    demo_structured_logging()
    demo_api_error_tracking()
    demo_performance_monitoring()
    demo_manual_sentry_handler()
    demo_framework_integration()
    demo_batch_processing()

    # Final message
    print("🎉 All demos completed!")
    print()
    print("💡 Tips:")
    print("   - Check your Sentry dashboard to see the captured events")
    print(
        "   - LogXide automatically sends WARNING, ERROR, and CRITICAL logs to Sentry"
    )
    print("   - Use structured logging with Sentry's scope for rich context")
    print("   - Exception logs include full stack traces automatically")
    print("   - Performance issues can be tracked with custom metrics")
    print()
    print("📖 Learn more:")
    print("   - Sentry documentation: https://docs.sentry.io/")
    print("   - LogXide documentation: https://github.com/Indosaram/logxide")

    # Ensure all logs are sent
    logging.flush()

    # Give Sentry time to send events
    print("\n⏳ Waiting for Sentry events to be sent...")
    time.sleep(2)

    return 0


if __name__ == "__main__":
    sys.exit(main())
