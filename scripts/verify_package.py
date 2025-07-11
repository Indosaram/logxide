#!/usr/bin/env python3
"""
Package verification script for LogXide

This script verifies that the LogXide package works correctly after installation.
"""

import sys
import traceback


def test_import():
    """Test basic import functionality."""
    print("Testing basic import...")

    try:
        import logxide

        print(f"✓ Successfully imported logxide version {logxide.__version__}")
        return True
    except Exception as e:
        print(f"❌ Failed to import logxide: {e}")
        traceback.print_exc()
        return False


def test_logging_module():
    """Test logging module functionality."""
    print("Testing logging module...")

    try:
        from logxide import logging

        # Test basic logging
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
        logger = logging.getLogger(__name__)

        logger.info("Test info message")
        logger.warning("Test warning message")
        logger.error("Test error message")

        print("✓ Basic logging functionality works")
        return True
    except Exception as e:
        print(f"❌ Failed logging test: {e}")
        traceback.print_exc()
        return False


def test_drop_in_replacement():
    """Test drop-in replacement functionality."""
    print("Testing drop-in replacement...")

    try:
        import logxide

        logxide.install()

        # Now import logging should use logxide
        import logging

        # Test that it's actually logxide
        if hasattr(logging, "flush"):
            logging.basicConfig(level=logging.INFO)
            logger = logging.getLogger("test")
            logger.info("Drop-in replacement test")
            logging.flush()
            print("✓ Drop-in replacement functionality works")
            return True
        else:
            print("❌ Drop-in replacement failed: missing flush method")
            return False
    except Exception as e:
        print(f"❌ Failed drop-in replacement test: {e}")
        traceback.print_exc()
        return False


def test_performance():
    """Test basic performance (simple benchmark)."""
    print("Testing performance...")

    try:
        import time

        from logxide import logging

        logging.basicConfig(level=logging.INFO, format="%(message)s")
        logger = logging.getLogger("performance_test")

        # Measure time for 1000 log messages
        start_time = time.time()
        for i in range(1000):
            logger.info(f"Performance test message {i}")
        logging.flush()
        end_time = time.time()

        duration = end_time - start_time
        messages_per_second = 1000 / duration

        print(
            f"✓ Performance test completed: {messages_per_second:.0f} messages/second"
        )
        return True
    except Exception as e:
        print(f"❌ Failed performance test: {e}")
        traceback.print_exc()
        return False


def test_thread_safety():
    """Test thread safety."""
    print("Testing thread safety...")

    try:
        import threading
        import time

        from logxide import logging

        logging.basicConfig(level=logging.INFO, format="%(threadName)s: %(message)s")
        logger = logging.getLogger("thread_test")

        def worker(worker_id):
            for i in range(10):
                logger.info(f"Worker {worker_id} message {i}")
                time.sleep(0.001)

        # Create and start threads
        threads = []
        for i in range(3):
            t = threading.Thread(target=worker, args=(i,), name=f"Worker-{i}")
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        logging.flush()
        print("✓ Thread safety test completed")
        return True
    except Exception as e:
        print(f"❌ Failed thread safety test: {e}")
        traceback.print_exc()
        return False


def test_formatting():
    """Test formatting capabilities."""
    print("Testing formatting...")

    try:
        from logxide import logging

        # Test various format specifiers
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)-8s] %(name)-15s: %(message)s",
        )
        logger = logging.getLogger("format_test")

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        logging.flush()
        print("✓ Formatting test completed")
        return True
    except Exception as e:
        print(f"❌ Failed formatting test: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    print("🧪 LogXide Package Verification")
    print("=" * 40)

    tests = [
        ("Import Test", test_import),
        ("Logging Module Test", test_logging_module),
        ("Drop-in Replacement Test", test_drop_in_replacement),
        ("Performance Test", test_performance),
        ("Thread Safety Test", test_thread_safety),
        ("Formatting Test", test_formatting),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            failed += 1

    print("\n" + "=" * 40)
    print(f"📊 Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("✅ All tests passed! LogXide package is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
