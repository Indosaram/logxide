"""
Test compatibility with Python standard library handlers.

This test verifies that logxide correctly emits to Python stdlib handlers
(like logging.FileHandler) when they are added via addHandler().
This is critical for compatibility with third-party libraries.
"""

import logging as std_logging
import os
import tempfile

import pytest


@pytest.mark.usefixtures("cleanup_logxide")
class TestStdlibHandlerCompatibility:
    """Test that stdlib handlers receive logs when used with logxide."""

    def setup_method(self):
        """Clear handlers before each test."""
        from logxide import logxide

        logxide.clear_handlers()

        # Clear Python logging cache
        if hasattr(std_logging.Logger, "manager") and hasattr(
            std_logging.Logger.manager, "loggerDict"
        ):
            std_logging.Logger.manager.loggerDict.clear()

    def teardown_method(self):
        """Clear handlers after each test."""
        from logxide import logxide

        logxide.clear_handlers()

    def test_stdlib_file_handler_receives_logs(self):
        """Verify stdlib FileHandler receives logs when logxide is installed."""
        # Install logxide
        from logxide.module_system import _install

        _install()

        # Create logger using standard logging API (like third-party libraries)
        logger = std_logging.getLogger("stdlib.filehandler.test")
        logger.setLevel(std_logging.DEBUG)

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            temp_file = f.name

        try:
            # Create stdlib FileHandler
            handler = std_logging.FileHandler(temp_file)
            handler.setLevel(std_logging.DEBUG)
            formatter = std_logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)

            # Add handler
            logger.addHandler(handler)

            # Log messages
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

            # Close handler to flush
            handler.close()

            # Verify content
            with open(temp_file) as f:
                content = f.read()

            assert len(content) > 0, "File should not be empty"
            assert "Debug message" in content
            assert "Info message" in content
            assert "Warning message" in content
            assert "Error message" in content
            assert "DEBUG" in content
            assert "INFO" in content
            assert "WARNING" in content
            assert "ERROR" in content

        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_stdlib_stream_handler_receives_logs(self):
        """Verify stdlib StreamHandler receives logs when logxide is installed."""
        import io

        # Install logxide
        from logxide.module_system import _install

        _install()

        # Create logger
        logger = std_logging.getLogger("stdlib.streamhandler.test")
        logger.setLevel(std_logging.DEBUG)

        # Create StringIO for capturing output
        stream = io.StringIO()

        # Create stdlib StreamHandler
        handler = std_logging.StreamHandler(stream)
        handler.setLevel(std_logging.DEBUG)
        formatter = std_logging.Formatter("%(levelname)s - %(message)s")
        handler.setFormatter(formatter)

        # Add handler
        logger.addHandler(handler)

        # Log messages
        logger.info("Stream test message")
        logger.warning("Stream warning")

        # Flush
        handler.flush()

        # Verify content
        content = stream.getvalue()

        assert len(content) > 0, "Stream should not be empty"
        assert "Stream test message" in content
        assert "Stream warning" in content

    def test_logxide_and_stdlib_handlers_together(self):
        """Verify both logxide and stdlib handlers receive logs."""
        from logxide import FileHandler, logging
        from logxide.module_system import _install

        _install()

        # Create temp files
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix="_logxide.log"
        ) as f:
            logxide_file = f.name

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix="_stdlib.log"
        ) as f:
            stdlib_file = f.name

        try:
            # Get logger
            logger = std_logging.getLogger("mixed.handlers.test")
            logger.setLevel(std_logging.DEBUG)

            # Add logxide FileHandler
            lx_handler = FileHandler(logxide_file)
            lx_handler.setLevel(10)  # DEBUG
            logger.addHandler(lx_handler)

            # Add stdlib FileHandler
            std_handler = std_logging.FileHandler(stdlib_file)
            std_handler.setLevel(std_logging.DEBUG)
            std_handler.setFormatter(
                std_logging.Formatter("%(levelname)s - %(message)s")
            )
            logger.addHandler(std_handler)

            # Log a message
            logger.info("Test message for both handlers")

            # Flush and close
            logging.flush()
            std_handler.close()

            # Verify logxide handler received the message
            with open(logxide_file) as f:
                lx_content = f.read()

            # Verify stdlib handler received the message
            with open(stdlib_file) as f:
                std_content = f.read()

            assert len(lx_content) > 0, "LogXide file should not be empty"
            assert len(std_content) > 0, "Stdlib file should not be empty"
            assert "Test message for both handlers" in lx_content
            assert "Test message for both handlers" in std_content

        finally:
            for f in [logxide_file, stdlib_file]:
                if os.path.exists(f):
                    os.unlink(f)

    @pytest.mark.skip(
        reason="Propagation to parent's stdlib handlers is a known limitation - child loggers emit to their own handlers"
    )
    def test_propagation_with_stdlib_handlers(self):
        """Test that propagation works correctly with stdlib handlers."""
        from logxide.module_system import _install

        _install()

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            temp_file = f.name

        try:
            # Create parent logger with stdlib handler
            parent = std_logging.getLogger("parent")
            parent.setLevel(std_logging.DEBUG)

            handler = std_logging.FileHandler(temp_file)
            handler.setLevel(std_logging.DEBUG)
            handler.setFormatter(std_logging.Formatter("%(name)s - %(message)s"))
            parent.addHandler(handler)

            # Create child logger (should propagate to parent)
            child = std_logging.getLogger("parent.child")
            child.setLevel(std_logging.DEBUG)

            # Log from child
            child.info("Child message")

            # Close handler
            handler.close()

            # Verify parent handler received the message
            with open(temp_file) as f:
                content = f.read()

            assert "Child message" in content

        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
