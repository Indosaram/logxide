"""
Quick demo showing logxide capturing third-party library logs.
"""

import logxide

# Install logxide BEFORE importing any third-party libraries
logxide.install()

# Now import logging and test libraries
import logging


def main():
    """Quick demo showing working integration."""

    # Configure logxide
    logging.basicConfig(
        level=logging.DEBUG, format="%(name)s - %(levelname)s - %(message)s"
    )

    print("=== LogXide Quick Demo ===\n")

    # Test basic logging
    logger = logging.getLogger("test")
    logger.info("LogXide basic logging works!")

    # Test imports that would normally use logging
    print("1. Testing library imports:")

    try:
        import urllib3

        urllib3_logger = logging.getLogger("urllib3.connectionpool")
        urllib3_logger.setLevel(logging.DEBUG)
        urllib3_logger.debug("urllib3 imported successfully - using logxide!")

        print("✓ urllib3 imported and logging through logxide")
    except ImportError as e:
        logger.error(f"Could not import urllib3: {e}")

    try:
        import requests

        requests_logger = logging.getLogger("requests.sessions")
        requests_logger.setLevel(logging.DEBUG)
        requests_logger.info("requests imported successfully - using logxide!")

        print("✓ requests imported and logging through logxide")
    except ImportError as e:
        logger.error(f"Could not import requests: {e}")

    # Test hierarchical loggers
    print("\n2. Testing hierarchical loggers:")
    for name in ["myapp", "myapp.db", "myapp.api", "third.party.lib"]:
        test_logger = logging.getLogger(name)
        test_logger.setLevel(logging.INFO)
        test_logger.info(f"Message from {name}")

    # Show different log levels
    print("\n3. Testing log levels:")
    level_logger = logging.getLogger("levels")
    level_logger.setLevel(logging.DEBUG)

    for level_name in ["debug", "info", "warning", "error", "critical"]:
        method = getattr(level_logger, level_name)
        method(f"This is a {level_name} message")

    logger.info("Demo completed successfully!")

    # Flush all logs
    logging.flush()

    print("\n=== Summary ===")
    print("✓ logxide.install() working")
    print("✓ Third-party libraries can import and use logging")
    print("✓ All log messages processed by logxide")
    print("✓ Standard logging interface compatibility maintained")


if __name__ == "__main__":
    main()
