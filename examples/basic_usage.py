"""
Basic LogXide Usage Example

This example demonstrates the fundamental features of logxide:
- Basic configuration
- Different log levels
- Logger hierarchy
- Message formatting

Expected Output:
The example will show structured logging output with timestamps, logger names,
levels, and formatted messages. All messages above DEBUG level will be displayed
with proper string formatting.
"""

from logxide import logging


def main():
    print("=== LogXide Basic Usage Example ===\n")

    # Configure logxide with basic settings
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # 1. Root logger usage
    print("1. Root Logger:")
    root_logger = logging.getLogger()
    root_logger.info("This is the root logger")

    # 2. Different log levels
    print("\n2. Different Log Levels:")
    logger = logging.getLogger("example")
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")

    # 3. Logger hierarchy
    print("\n3. Logger Hierarchy:")
    parent_logger = logging.getLogger("myapp")
    child_logger = logging.getLogger("myapp.database")
    grandchild_logger = logging.getLogger("myapp.database.connection")

    parent_logger.info("Parent logger message")
    child_logger.info("Child logger message")
    grandchild_logger.info("Grandchild logger message")

    # 4. Different components
    print("\n4. Application Components:")
    api_logger = logging.getLogger("myapp.api")
    auth_logger = logging.getLogger("myapp.auth")
    cache_logger = logging.getLogger("myapp.cache")

    api_logger.info("API server started on port 8080")
    auth_logger.warning("Failed login attempt")
    cache_logger.debug("Cache hit for key: user_123")

    # 5. String formatting
    print("\n5. String Formatting:")
    logger.info(f"User {'alice'} logged in from {'192.168.1.100'}")
    logger.warning(f"High memory usage: {85}% ({1024} MB)")
    logger.error(f"Connection timeout after {30} seconds")

    print("\n6. Cleanup:")
    root_logger.info("Example completed successfully")

    # Ensure all logs are processed
    logging.flush()


if __name__ == "__main__":
    main()
