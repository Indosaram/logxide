"""
Simple demo showing logxide working with third-party library logging.
This approach manually configures third-party loggers to use logxide.
"""
import logxide

# Install logxide as drop-in replacement first
logxide.install()

# Import after installation
from logxide import logging


def demo_third_party_logging():
    """Demo third-party library logging with logxide."""

    # Configure logxide
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("=== LogXide Third-Party Integration Demo ===\n")

    # Test our own logging first
    main_logger = logging.getLogger("demo")
    main_logger.info("Starting third-party logging demo")

    # Simulate what requests library might do
    print("1. Simulating requests library logging:")
    requests_logger = logging.getLogger("requests.sessions")
    requests_logger.info("Starting new HTTPS connection (1): httpbin.org:443")
    requests_logger.debug("HTTP request details: GET /status/200")
    requests_logger.info("Connection established successfully")

    # Simulate what sqlalchemy might do
    print("\n2. Simulating SQLAlchemy logging:")
    sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
    sqlalchemy_logger.info("BEGIN (implicit)")
    sqlalchemy_logger.info("SELECT 1")
    sqlalchemy_logger.debug("Query execution time: 0.001s")
    sqlalchemy_logger.info("COMMIT")

    # Simulate urllib3 logging
    print("\n3. Simulating urllib3 logging:")
    urllib3_logger = logging.getLogger("urllib3.connectionpool")
    urllib3_logger.debug("Starting new HTTPS connection (1): api.github.com:443")
    urllib3_logger.debug('https://api.github.com:443 "GET /user HTTP/1.1" 200 1234')

    # Show different log levels
    print("\n4. Testing different log levels:")
    test_logger = logging.getLogger("test.library")
    test_logger.debug("Debug message from third-party library")
    test_logger.info("Info message from third-party library")
    test_logger.warning("Warning message from third-party library")
    test_logger.error("Error message from third-party library")
    test_logger.critical("Critical message from third-party library")

    # Show hierarchical logging
    print("\n5. Testing hierarchical loggers:")
    parent_logger = logging.getLogger("myapp")
    child_logger = logging.getLogger("myapp.database")
    grandchild_logger = logging.getLogger("myapp.database.connection")

    parent_logger.info("Parent logger message")
    child_logger.info("Child logger message")
    grandchild_logger.info("Grandchild logger message")

    main_logger.info("Third-party logging demo completed")

    # Flush to ensure all async logging completes
    logging.flush()


if __name__ == "__main__":
    demo_third_party_logging()
