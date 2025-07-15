#!/usr/bin/env python3
"""
Comprehensive test suite for all LogXide integration examples.

This script tests that all integration examples can be imported and basic
functionality works correctly without starting servers.
"""

import importlib.util
import sys
import traceback
from pathlib import Path

# Add the logxide directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))


def test_example_import(example_name, example_path):
    """Test that an example can be imported successfully."""
    print(f"Testing {example_name}...")

    try:
        # Load the module
        module_name = example_path.stem
        spec = importlib.util.spec_from_file_location(module_name, example_path)
        if spec is None:
            print(f"✗ {example_name} - Could not load module spec")
            return False

        module = importlib.util.module_from_spec(spec)

        # Add to sys.modules to avoid import issues
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
            print(f"✓ {example_name} - Import successful")
            return True
        finally:
            # Clean up
            if module_name in sys.modules:
                del sys.modules[module_name]

    except Exception as e:
        print(f"✗ {example_name} - Import failed: {str(e)}")
        if "verbose" in sys.argv:
            traceback.print_exc()
        return False


def test_logxide_basic():
    """Test basic LogXide functionality."""
    print("Testing LogXide basic functionality...")

    try:
        import logxide

        logxide.install()

        import logging

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Test basic logging
        logger = logging.getLogger("test")
        logger.info("Basic LogXide test")
        logger.warning("Warning message")
        logger.error("Error message")

        # Test flush
        logging.flush()

        print("✓ LogXide basic functionality - Success")
        return True

    except Exception as e:
        print(f"✗ LogXide basic functionality - Failed: {str(e)}")
        return False


def test_flask_integration():
    """Test Flask integration without starting server."""
    print("Testing Flask integration...")

    try:
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

        # Test that route was registered
        with app.test_client() as client:
            response = client.get("/")
            assert response.status_code == 200

        logger.info("Flask integration test completed")
        logging.flush()

        print("✓ Flask integration - Success")
        return True

    except Exception as e:
        print(f"✗ Flask integration - Failed: {str(e)}")
        return False


def test_django_integration():
    """Test Django integration without starting server."""
    print("Testing Django integration...")

    try:
        import logxide

        logxide.install()

        import logging

        import django
        from django.conf import settings

        # Configure Django settings
        if not settings.configured:
            settings.configure(
                DEBUG=True,
                SECRET_KEY="test-key-for-integration-test",
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
        logger.info("Django integration test")

        # Test that Django is working
        from django.contrib.auth.models import User

        assert User is not None

        logging.flush()

        print("✓ Django integration - Success")
        return True

    except Exception as e:
        print(f"✗ Django integration - Failed: {str(e)}")
        return False


def test_fastapi_integration():
    """Test FastAPI integration without starting server."""
    print("Testing FastAPI integration...")

    try:
        import logxide

        logxide.install()

        import logging

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

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

        # Test with test client
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200

        logger.info("FastAPI integration test completed")
        logging.flush()

        print("✓ FastAPI integration - Success")
        return True

    except Exception as e:
        print(f"✗ FastAPI integration - Failed: {str(e)}")
        return False


def test_performance():
    """Test LogXide performance."""
    print("Testing LogXide performance...")

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

        # Verify performance is reasonable
        assert total_time < 5.0, f"Performance test too slow: {total_time:.3f}s"

        print("✓ LogXide performance - Success")
        return True

    except Exception as e:
        print(f"✗ LogXide performance - Failed: {str(e)}")
        return False


def main():
    """Run all integration tests."""
    print("Running LogXide integration example tests...\n")

    # Test basic functionality first
    tests = [
        ("LogXide Basic", test_logxide_basic),
        ("Flask Integration", test_flask_integration),
        ("Django Integration", test_django_integration),
        ("FastAPI Integration", test_fastapi_integration),
        ("Performance", test_performance),
    ]

    # Test example imports
    examples_dir = Path(__file__).parent / "examples"
    example_files = [
        ("Flask Integration Example", examples_dir / "flask_integration.py"),
        ("Django Integration Example", examples_dir / "django_integration.py"),
        ("FastAPI Demo Example", examples_dir / "fastapi_demo.py"),
        ("FastAPI Advanced Example", examples_dir / "fastapi_advanced.py"),
        ("Third Party Integration", examples_dir / "third_party_integration.py"),
    ]

    passed = 0
    failed = 0

    # Run functional tests
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {test_name} - Exception: {str(e)}")
            failed += 1
        print()

    # Run example import tests
    for example_name, example_path in example_files:
        if example_path.exists():
            if test_example_import(example_name, example_path):
                passed += 1
            else:
                failed += 1
        else:
            print(f"✗ {example_name} - File not found: {example_path}")
            failed += 1
        print()

    print("Integration test results:")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Total:  {passed + failed}")

    if failed == 0:
        print("\n🎉 All integration tests passed!")
        print("✅ All LogXide integration examples work correctly!")
        return 0
    else:
        print(f"\n❌ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
