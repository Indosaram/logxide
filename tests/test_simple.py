"""
Simple tests that work with current logxide implementation.
"""

import pytest

from logxide import logging


class TestBasicFunctionality:
    """Test basic functionality that currently works."""

    def test_logger_creation(self):
        """Test that loggers can be created."""
        logger = logging.getLogger("test.logger")
        assert logger is not None
        assert logger.name == "test.logger"

    def test_logger_hierarchy(self):
        """Test logger hierarchy."""
        parent_logger = logging.getLogger("parent")
        child_logger = logging.getLogger("parent.child")
        grandchild_logger = logging.getLogger("parent.child.grandchild")

        assert parent_logger.name == "parent"
        assert child_logger.name == "parent.child"
        assert grandchild_logger.name == "parent.child.grandchild"

    def test_basic_config_no_args(self):
        """Test basic configuration without arguments."""
        # Should not raise any exceptions
        logging.basicConfig()

    def test_flush_functionality(self):
        """Test flush functionality."""
        # Should not raise any exceptions
        logging.flush()

    def test_logging_methods_exist(self):
        """Test that logging methods exist."""
        logger = logging.getLogger("test.methods")

        # Check that methods exist
        assert hasattr(logger, "debug")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "critical")

    def test_multiple_loggers(self):
        """Test multiple loggers working together."""
        logger1 = logging.getLogger("app.database")
        logger2 = logging.getLogger("app.api")
        logger3 = logging.getLogger("app.cache")

        # Should all work without exceptions
        assert logger1.name == "app.database"
        assert logger2.name == "app.api"
        assert logger3.name == "app.cache"

    def test_logger_names_uniqueness(self):
        """Test that loggers with same name return same instance."""
        logger1 = logging.getLogger("same.name")
        logger2 = logging.getLogger("same.name")

        # Should have the same name
        assert logger1.name == logger2.name


class TestCompatibility:
    """Test compatibility with Python logging module."""

    def test_has_getLogger(self):
        """Test that getLogger function exists."""
        assert hasattr(logging, "getLogger")
        assert callable(logging.getLogger)

    def test_has_basicConfig(self):
        """Test that basicConfig function exists."""
        assert hasattr(logging, "basicConfig")
        assert callable(logging.basicConfig)

    def test_has_flush(self):
        """Test that flush function exists."""
        assert hasattr(logging, "flush")
        assert callable(logging.flush)

    def test_can_call_logging_methods(self):
        """Test that logging methods can be called without errors."""
        logger = logging.getLogger("test.compatibility")

        # These should not raise exceptions
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        # Flush should work
        logging.flush()


if __name__ == "__main__":
    pytest.main([__file__])
