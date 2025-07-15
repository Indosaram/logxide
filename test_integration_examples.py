#!/usr/bin/env python3
"""
Test script to verify integration examples work correctly.

This script tests the integration examples for Flask, Django, and FastAPI
to ensure they work properly with LogXide.
"""

import sys
from pathlib import Path

# Add the logxide directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))


def test_flask_integration():
    """Test Flask integration example."""
    print("Testing Flask integration...")

    try:
        # Import and test basic functionality
        import logxide

        logxide.install()

        import logging

        from flask import Flask

        app = Flask(__name__)

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        logger = logging.getLogger("flask.test")

        @app.route("/")
        def hello():
            logger.info("Test endpoint accessed")
            return {"message": "Flask + LogXide test successful"}

        # Test logging without starting server
        logger.info("Flask integration test - logging works")
        logging.flush()

        print("✓ Flask integration test passed")
        return True

    except Exception as e:
        print(f"✗ Flask integration test failed: {e}")
        return False


def test_django_integration():
    """Test Django integration example."""
    print("Testing Django integration...")

    try:
        # Import and test basic functionality
        import logxide

        logxide.install()

        import logging

        import django
        from django.conf import settings

        # Configure Django settings
        if not settings.configured:
            settings.configure(
                DEBUG=True,
                SECRET_KEY="test-key",
                DATABASES={
                    "default": {
                        "ENGINE": "django.db.backends.sqlite3",
                        "NAME": ":memory:",
                    }
                },
                INSTALLED_APPS=[
                    "django.contrib.auth",
                    "django.contrib.contenttypes",
                ],
                USE_TZ=True,
            )

        django.setup()

        # Test logging
        logger = logging.getLogger("django.test")
        logger.info("Django integration test - logging works")
        logging.flush()

        print("✓ Django integration test passed")
        return True

    except Exception as e:
        print(f"✗ Django integration test failed: {e}")
        return False


def test_fastapi_integration():
    """Test FastAPI integration example."""
    print("Testing FastAPI integration...")

    try:
        # Import and test basic functionality
        import logxide

        logxide.install()

        import logging

        from fastapi import FastAPI

        app = FastAPI()

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        logger = logging.getLogger("fastapi.test")

        @app.get("/")
        async def root():
            logger.info("Test endpoint accessed")
            return {"message": "FastAPI + LogXide test successful"}

        # Test logging without starting server
        logger.info("FastAPI integration test - logging works")
        logging.flush()

        print("✓ FastAPI integration test passed")
        return True

    except Exception as e:
        print(f"✗ FastAPI integration test failed: {e}")
        return False


def test_logging_performance():
    """Test logging performance with LogXide."""
    print("Testing logging performance...")

    try:
        import logxide

        logxide.install()

        import logging
        import time

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        logger = logging.getLogger("performance.test")

        # Test high-volume logging
        start_time = time.time()

        for i in range(1000):
            logger.info(f"Performance test message {i}")

        queue_time = time.time() - start_time

        # Flush and measure total time
        logging.flush()
        total_time = time.time() - start_time

        print(f"   Queued 1000 messages in {queue_time:.3f}s")
        print(f"   Total processing time: {total_time:.3f}s")
        print(f"   Messages per second: {1000 / total_time:.0f}")

        print("✓ Performance test passed")
        return True

    except Exception as e:
        print(f"✗ Performance test failed: {e}")
        return False


def test_thread_safety():
    """Test thread safety of LogXide."""
    print("Testing thread safety...")

    try:
        import logxide

        logxide.install()

        import logging
        import threading

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - [%(thread)d] - %(message)s",
        )

        logger = logging.getLogger("thread.test")

        def worker(worker_id):
            for i in range(100):
                logger.info(f"Worker {worker_id} message {i}")

        # Create and start threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=[i])
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Flush logs
        logging.flush()

        print("✓ Thread safety test passed")
        return True

    except Exception as e:
        print(f"✗ Thread safety test failed: {e}")
        return False


def test_error_handling():
    """Test error handling and exception logging."""
    print("Testing error handling...")

    try:
        import logxide

        logxide.install()

        import logging

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        logger = logging.getLogger("error.test")

        # Test exception logging
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            logger.error(f"Caught exception: {e}")
            logger.exception("Full exception details:")

        # Test warning and error levels
        logger.warning("This is a warning message")
        logger.error("This is an error message")

        # Flush logs
        logging.flush()

        print("✓ Error handling test passed")
        return True

    except Exception as e:
        print(f"✗ Error handling test failed: {e}")
        return False


def test_compatibility():
    """Test compatibility with standard logging."""
    print("Testing compatibility...")

    try:
        import logxide

        logxide.install()

        import logging

        # Test that we can use standard logging patterns
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Test different logger creation patterns
        logger1 = logging.getLogger(__name__)
        logger2 = logging.getLogger("test.module")
        logger3 = logging.getLogger("test.module.submodule")

        # Test all log levels
        logger1.debug("Debug message")
        logger1.info("Info message")
        logger1.warning("Warning message")
        logger1.error("Error message")
        logger1.critical("Critical message")

        # Test logger hierarchy
        logger2.info("Parent logger message")
        logger3.info("Child logger message")

        # Test flush
        logging.flush()

        print("✓ Compatibility test passed")
        return True

    except Exception as e:
        print(f"✗ Compatibility test failed: {e}")
        return False


def main():
    """Run all integration tests."""
    print("Running LogXide integration tests...\n")

    tests = [
        test_flask_integration,
        test_django_integration,
        test_fastapi_integration,
        test_logging_performance,
        test_thread_safety,
        test_error_handling,
        test_compatibility,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed with exception: {e}")
            failed += 1
        print()

    print("Integration test results:")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Total:  {passed + failed}")

    if failed == 0:
        print("\n🎉 All integration tests passed!")
        return 0
    else:
        print(f"\n❌ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
