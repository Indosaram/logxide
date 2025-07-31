"""
Drop-in Replacement Example

This example demonstrates how logxide works as a complete drop-in
replacement for Python's standard logging module through the auto-install pattern.
"""

import sys

import logxide


def main():
    print("=== LogXide Drop-in Replacement Example ===\n")

    # Show the state before using logxide
    print("1. Before importing from logxide:")
    print(f"   sys.modules has 'logging': {'logging' in sys.modules}")
    if "logging" in sys.modules:
        print(f"   logging module type: {type(sys.modules['logging'])}")

    # Import from logxide - this automatically installs it as drop-in replacement
    print("\n2. Importing from logxide (auto-install)...")
    from logxide import logging

    # Show the state after auto-installation
    print("   ✓ logxide auto-installed")
    print(f"   logging module type: {type(logging)}")

    # Configure logging (this is actually logxide now)
    logging.basicConfig(
        level=logging.INFO, format="[LOGXIDE] %(name)s - %(levelname)s - %(message)s"
    )

    print("\n3. Testing basic logging functionality:")
    logger = logging.getLogger("example")
    logger.info("This message is processed by logxide!")
    logger.warning("All standard logging methods work normally")
    logger.error("Existing code requires no changes")

    print("\n4. Testing with simulated third-party libraries:")

    # Simulate what third-party libraries would do
    library_loggers = [
        ("requests.sessions", "Making HTTP request"),
        ("sqlalchemy.engine", "BEGIN (implicit)"),
        ("urllib3.connectionpool", "Starting new connection"),
        ("django.request", "GET /api/users"),
        ("flask.app", "127.0.0.1 - - [GET]"),
        ("celery.task", "Task started: user.process"),
    ]

    for lib_name, message in library_loggers:
        lib_logger = logging.getLogger(lib_name)
        lib_logger.info(message)
        print(f"   ✓ {lib_name} logging captured")

    print("\n5. Demonstrating compatibility:")

    # All standard logging features work
    test_logger = logging.getLogger("compatibility")
    test_logger.setLevel(logging.DEBUG)

    # Test various logging patterns
    test_logger.debug(f"Debug level: {'enabled'}")
    test_logger.info(f"User login: {'user123'} from {'192.168.1.1'}")
    test_logger.warning(f"Memory usage at {85}% threshold")
    test_logger.error(f"Connection failed after {3} retries")
    test_logger.critical("System shutdown initiated")

    # Test logger attributes that third-party libraries might check
    print(f"   ✓ Logger has 'level' attribute: {hasattr(test_logger, 'level')}")
    print(f"   ✓ Logger has 'handlers' attribute: {hasattr(test_logger, 'handlers')}")
    print(f"   ✓ Logger has 'manager' attribute: {hasattr(test_logger, 'manager')}")

    print("\n6. Performance characteristics:")
    logger.info("All logging is processed asynchronously in Rust")
    logger.info("High-performance logging for Python applications")
    logger.info("Zero-copy string handling where possible")

    # Ensure all logs are processed
    logging.flush()

    print("\n=== USAGE INSTRUCTIONS ===")
    print("To use logxide in your project, simply import from logxide:")
    print("")
    print("```python")
    print("from logxide import logging")
    print("")
    print("logging.basicConfig(level=logging.INFO)")
    print("logger = logging.getLogger(__name__)")
    print("logger.info('Hello from logxide!')")
    print("")
    print("# All libraries imported after this will use logxide")
    print("import requests  # Will use logxide for logging")
    print("import sqlalchemy  # Will use logxide for logging")
    print("```")
    print("")
    print("That's it! LogXide automatically installs itself as a drop-in replacement.")


if __name__ == "__main__":
    main()
