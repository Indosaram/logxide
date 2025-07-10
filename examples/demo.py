"""
Demo showing logxide with third-party libraries.
This shows manual logging approach since full drop-in replacement
requires extensive compatibility work.
"""

from logxide import logging

if __name__ == "__main__":
    # Configure logxide
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("=== LogXide Demo ===")

    root_logger = logging.getLogger()
    root_logger.info("This is a test log message.")

    # Since full drop-in replacement needs more compatibility work,
    # we'll demonstrate by manually creating loggers that third-party
    # libraries would typically use

    print("\n1. Simulating requests/urllib3 logging:")
    requests_logger = logging.getLogger("requests")
    requests_logger.setLevel(logging.DEBUG)
    urllib3_logger = logging.getLogger("urllib3")
    urllib3_logger.setLevel(logging.DEBUG)

    # Simulate what requests would log
    requests_logger.info("Starting new HTTPS connection (1): httpbin.org:443")
    urllib3_logger.debug("GET /status/404 HTTP/1.1")
    requests_logger.warning("Received 404 response")

    print("\n2. Simulating SQLAlchemy logging:")
    sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
    sqlalchemy_logger.setLevel(logging.INFO)

    # Simulate what SQLAlchemy would log
    sqlalchemy_logger.info("BEGIN (implicit)")
    sqlalchemy_logger.info("SELECT 1")
    sqlalchemy_logger.info("COMMIT")
    sqlalchemy_logger.info("BEGIN (implicit)")
    sqlalchemy_logger.error(
        "(sqlite3.OperationalError) no such table: non_existent_table"
    )
    sqlalchemy_logger.info("ROLLBACK")

    print("\n3. Application logging:")
    app_logger = logging.getLogger("myapp")
    app_logger.info("Application component initialized")
    app_logger.warning("This is a warning from the application")
    app_logger.error("Simulated error condition")

    root_logger.info("Demo completed")

    # IMPORTANT: Flush to ensure all async logging completes
    logging.flush()

    print("\nNote: For true drop-in replacement with real third-party libraries,")
    print("use logxide.install() before importing any libraries that use logging.")
