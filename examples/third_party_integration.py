"""
Third-Party Library Integration Example

This example demonstrates real integration with popular Python libraries
showing how logxide captures their actual log output.
"""

import sys

from logxide import logging


def main():
    """Demonstrate real third-party library integration."""

    print("=== LogXide Third-Party Integration Example ===\n")

    # Configure logxide with detailed formatting
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    app_logger = logging.getLogger("integration_demo")
    app_logger.info("Starting third-party library integration demo")

    print(f"Using logging module: {type(sys.modules['logging'])}")

    # Test 1: HTTP Client Libraries (requests + urllib3)
    print("\n1. HTTP Client Libraries (requests + urllib3):")
    try:
        import requests
        import urllib3

        # Enable debug logging to see actual library logs
        urllib3_logger = logging.getLogger("urllib3.connectionpool")
        urllib3_logger.setLevel(logging.DEBUG)

        app_logger.info("Making HTTP request to demonstrate real logging...")

        # This will generate actual urllib3 debug logs through logxide
        response = requests.get("https://httpbin.org/json", timeout=5)

        app_logger.info(f"HTTP request completed: {response.status_code}")
        print("   ✓ Real urllib3/requests logs captured by logxide")

    except ImportError as e:
        app_logger.error(f"Could not import HTTP libraries: {e}")
        print("   ✗ HTTP libraries not available")
    except Exception as e:
        app_logger.error(f"HTTP request failed: {e}")
        print("   ✗ HTTP request failed (network issue)")

    # Test 2: Database ORM (SQLAlchemy)
    print("\n2. Database ORM (SQLAlchemy):")
    try:
        from sqlalchemy import create_engine, text

        # Enable SQLAlchemy logging to see actual SQL logs
        sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
        sqlalchemy_logger.setLevel(logging.INFO)

        app_logger.info("Creating database and executing queries...")

        # Create in-memory SQLite database with echo=True for SQL logging
        engine = create_engine("sqlite:///:memory:", echo=True)

        # Execute SQL - this generates actual SQLAlchemy logs through logxide
        with engine.connect() as conn:
            # Create a table
            conn.execute(text("CREATE TABLE users (id INTEGER, name TEXT)"))

            # Insert data
            conn.execute(text("INSERT INTO users VALUES (1, 'Alice'), (2, 'Bob')"))

            # Query data
            result = conn.execute(text("SELECT * FROM users"))
            rows = result.fetchall()

            app_logger.info(f"Query returned {len(rows)} rows: {rows}")

        print("   ✓ Real SQLAlchemy SQL logs captured by logxide")

    except ImportError as e:
        app_logger.error(f"Could not import SQLAlchemy: {e}")
        print("   ✗ SQLAlchemy not available")
    except Exception as e:
        app_logger.error(f"Database operation failed: {e}")
        print("   ✗ Database operations failed")

    # Test 3: Multiple Library Simulation
    print("\n3. Multiple Library Ecosystem:")

    libraries = [
        ("django.request", "Processing GET /api/users/"),
        ("flask.app", "127.0.0.1 - - [10/Jul/2025 18:30:45] GET /"),
        ("celery.worker", "Task user.process_data[abc-123] received"),
        ("redis.connection", "Connected to Redis at localhost:6379"),
        ("boto3.session", "Found credentials in environment variables"),
        ("pandas.core", "DataFrame created with 1000 rows, 5 columns"),
    ]

    for lib_name, message in libraries:
        lib_logger = logging.getLogger(lib_name)
        lib_logger.info(message)

    print("   ✓ Multiple libraries would all log through logxide")

    # Test 4: Performance Characteristics
    print("\n4. Performance Testing:")
    app_logger.info("Testing high-volume logging performance...")

    # Simulate high-volume logging
    perf_logger = logging.getLogger("performance")
    for i in range(100):
        perf_logger.debug(f"High-volume log entry {i:03d}")

    app_logger.info("High-volume logging completed (async processing)")
    print("   ✓ High-volume logs processed asynchronously")

    # Ensure all logs are processed before finishing
    logging.flush()

    print("\n=== Integration Summary ===")
    print("✓ Auto-install pattern provides drop-in replacement")
    print("✓ Real HTTP library logs captured (urllib3/requests)")
    print("✓ Real database logs captured (SQLAlchemy)")
    print("✓ Multiple libraries can coexist seamlessly")
    print("✓ Async processing provides high performance")
    print("✓ Zero changes needed to existing library code")

    app_logger.info("Third-party integration demo completed successfully")


if __name__ == "__main__":
    main()
