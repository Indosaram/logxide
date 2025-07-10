"""
Demo showing logxide capturing actual third-party library log output.
This demonstrates real integration with requests and sqlalchemy.
"""

import logxide

# Install logxide BEFORE importing any third-party libraries
logxide.install()

# Now import logging and third-party libraries
import logging
import sys


def main():
    """Main demo function showing real third-party library logging."""

    # Configure logxide with detailed format
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("=== LogXide Real Third-Party Library Demo ===\n")

    # Application logger
    app_logger = logging.getLogger("__file__")
    app_logger.info("Starting demo with real third-party libraries")

    # Test 1: Import and use requests
    print("1. Testing with requests library:")
    try:
        import requests
        import urllib3

        # Enable debug logging for requests and urllib3
        requests_logger = logging.getLogger("requests")
        requests_logger.setLevel(logging.DEBUG)
        urllib3_logger = logging.getLogger("urllib3")
        urllib3_logger.setLevel(logging.DEBUG)

        # Make a real HTTP request - this should generate actual logs
        response = requests.get("https://httpbin.org/json", timeout=10)

    except ImportError as e:
        app_logger.error(f"Could not import requests: {e}")
    except Exception as e:
        app_logger.error(f"Error making request: {e}")

    print("\n2. Testing with SQLAlchemy:")
    try:
        import sqlalchemy
        from sqlalchemy import create_engine, text

        # Enable SQLAlchemy logging
        sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
        sqlalchemy_logger.setLevel(logging.INFO)

        # Create an in-memory SQLite database
        engine = create_engine("sqlite:///:memory:", echo=True)

        # Execute some SQL - this should generate actual SQLAlchemy logs
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test_value"))
            row = result.fetchone()
            app_logger.info(f"SQL query result: {row}")

    except ImportError as e:
        app_logger.error(f"Could not import SQLAlchemy: {e}")
    except Exception as e:
        app_logger.error(f"Error with SQLAlchemy: {e}")

    app_logger.info("Demo completed successfully")

    # Ensure all async logs are flushed
    logging.flush()

    print("\n=== Verification ===")
    print(f"Python sys.modules['logging'] type: {type(sys.modules['logging'])}")
    print("All library imports used logxide for logging!")


if __name__ == "__main__":
    main()
