"""
Working demo showing how to get third-party library logs with logxide.
"""

from logxide import logging

# Configure logxide with DEBUG level to see all messages
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def demo_working():
    """Demo showing working third-party style logging."""

    print("=== LogXide Working Demo ===\n")

    # Main application logger
    main_logger = logging.getLogger("myapp")
    main_logger.setLevel(logging.DEBUG)
    main_logger.info("Application starting")

    # Simulate requests library logging (what it would look like)
    print("1. Third-party library style logging:")
    requests_logger = logging.getLogger("requests")
    requests_logger.setLevel(logging.DEBUG)
    requests_logger.info("Making HTTP request to https://api.example.com")
    requests_logger.debug("Request headers: {'User-Agent': 'python-requests/2.31.0'}")
    requests_logger.info("Received response: 200 OK")

    # Simulate database library logging
    db_logger = logging.getLogger("database.pool")
    db_logger.setLevel(logging.DEBUG)
    db_logger.info("Database connection pool initialized")
    db_logger.debug("Pool size: 5, Active connections: 1")
    db_logger.warning("Connection pool utilization above 80%")

    # Show different components
    print("\n2. Different application components:")
    api_logger = logging.getLogger("myapp.api")
    api_logger.setLevel(logging.DEBUG)
    cache_logger = logging.getLogger("myapp.cache")
    cache_logger.setLevel(logging.DEBUG)
    auth_logger = logging.getLogger("myapp.auth")
    auth_logger.setLevel(logging.DEBUG)

    api_logger.info("API server started on port 8000")
    cache_logger.info("Redis cache connected")
    auth_logger.warning("Failed login attempt from IP 192.168.1.100")

    # Show error scenarios
    print("\n3. Error scenarios:")
    error_logger = logging.getLogger("myapp.errors")
    error_logger.setLevel(logging.DEBUG)
    error_logger.error("Database connection failed")
    error_logger.critical("Service unavailable - shutting down")

    main_logger.info("Demo completed successfully")

    # Ensure all logs are flushed
    logging.flush()


def demonstrate_real_import():
    """Show what happens with actual imports after logxide.install()"""
    import logxide

    print("\n=== Demonstrating logxide.install() ===")
    print(
        "Before install - sys.modules['logging']:",
        "logging" in __import__("sys").modules,
    )

    # Install logxide as drop-in replacement
    logxide.install()

    print(
        "After install - sys.modules['logging']:",
        "logging" in __import__("sys").modules,
    )
    print(
        "sys.modules['logging'] type:", type(__import__("sys").modules.get("logging"))
    )

    # Now any import of logging will get logxide
    import logging as std_logging

    print("Standard 'import logging' now gets:", type(std_logging))

    # Configure and test
    std_logging.basicConfig(format="[INSTALLED] %(name)s: %(message)s")
    test_logger = std_logging.getLogger("after.install")
    test_logger.setLevel(std_logging.INFO)
    test_logger.info("This message uses logxide through standard import!")

    std_logging.flush()


if __name__ == "__main__":
    demo_working()
    demonstrate_real_import()
