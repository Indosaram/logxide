"""
Simple integration tests that work with current logxide implementation.
"""

import pytest

from logxide import logging


class TestIntegrationSimple:
    """Simple integration tests."""

    def test_end_to_end_logging(self):
        """Test basic end-to-end logging flow."""
        # Setup
        logging.basicConfig()

        # Create logger
        logger = logging.getLogger("integration.test")

        # Log messages (should not raise exceptions)
        logger.info("Starting integration test")
        logger.warning("This is a warning")
        logger.error("This is an error")

        # Flush
        logging.flush()

        # Test passes if no exceptions are raised

    def test_multiple_loggers_integration(self):
        """Test multiple loggers working together."""
        logging.basicConfig()

        # Create multiple loggers
        db_logger = logging.getLogger("app.database")
        api_logger = logging.getLogger("app.api")
        cache_logger = logging.getLogger("app.cache")

        # Log from each
        db_logger.info("Database connection established")
        api_logger.info("API server started")
        cache_logger.info("Cache initialized")

        # Flush all
        logging.flush()

        # Test passes if no exceptions are raised

    def test_logger_reuse(self):
        """Test that loggers can be reused."""
        logger1 = logging.getLogger("reuse.test")
        logger2 = logging.getLogger("reuse.test")

        # Should be the same logger
        assert logger1.name == logger2.name

        # Both should work
        logger1.info("Message from logger1")
        logger2.info("Message from logger2")

        logging.flush()


if __name__ == "__main__":
    pytest.main([__file__])
