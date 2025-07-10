"""
Simple SQLAlchemy test to isolate the issue.
"""

import logxide

logxide.install()

import logging

logging.basicConfig(
    level=logging.DEBUG, format="%(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("test")

try:
    logger.info("Importing SQLAlchemy...")
    from sqlalchemy import create_engine, text

    logger.info("Creating SQLAlchemy engine...")
    # Create an in-memory SQLite database with echo=True for logging
    engine = create_engine("sqlite:///:memory:", echo=True)

    logger.info("✓ SQLAlchemy engine created successfully")

    # Test a simple query
    with engine.connect() as conn:
        logger.info("Executing test query...")
        result = conn.execute(text("SELECT 1 as test_value"))
        row = result.fetchone()
        logger.info(f"Query result: {row}")

    logger.info("✓ SQLAlchemy test completed successfully")

except Exception as e:
    logger.error(f"Error: {e}")
    import traceback

    traceback.print_exc()

logging.flush()
