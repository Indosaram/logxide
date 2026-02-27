"""
Test that handlers actually write logs to their configured targets.

This test verifies that the logging output actually reaches the intended
destinations (files, streams, etc.) with proper formatting and filtering.
"""

import os
import tempfile

import pytest


@pytest.mark.usefixtures("cleanup_logxide")
class TestHandlerOutput:
    """Test that logs are actually written to handler targets."""

    def setup_method(self):
        """Clear handlers before each test method."""
        from logxide import logxide

        # Complete reset before each test
        logxide.clear_handlers()

        # Also clear Python logging cache
        import logging as std_logging

        if hasattr(std_logging.Logger, "manager") and hasattr(
            std_logging.Logger.manager, "loggerDict"
        ):
            std_logging.Logger.manager.loggerDict.clear()

    def teardown_method(self):
        """Clear handlers after each test method."""
        from logxide import logxide

        logxide.clear_handlers()

    def test_file_handler_writes_to_file(self):
        """Verify FileHandler actually writes to a file (via basicConfig)."""
        import time

        from logxide import logging

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            temp_file = f.name

        try:
            # Setup logger using basicConfig with file output
            logging.basicConfig(
                filename=temp_file,
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                force=True,
            )

            logger = logging.getLogger("test.file")

            # Log some messages
            logger.info("Test info message")
            logger.warning("Test warning message")
            logger.error("Test error message")

            # Flush to ensure all logs are written
            logging.flush()

            # Give async handler time to write
            time.sleep(0.2)

            # Read the file and verify content
            with open(temp_file) as f:
                content = f.read()

            # Logger name might be "root" due to propagation, so just check for messages
            assert "Test info message" in content
            assert "Test warning message" in content
            assert "Test error message" in content
            assert "INFO" in content
            assert "WARNING" in content
            assert "ERROR" in content

        finally:
            # Cleanup
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_basicConfig_creates_working_handler(self):
        """Verify basicConfig creates a handler that actually works."""
        from logxide import logging

        # Use file-based test instead of StringIO
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            temp_file = f.name

        try:
            # Configure with basicConfig
            logging.basicConfig(
                filename=temp_file,
                level=logging.INFO,
                format="%(levelname)s - %(message)s",
                force=True,
            )

            # Get root logger and log
            logger = logging.getLogger()
            logger.info("Test via basicConfig")

            logging.flush()

            # Read file and verify output
            with open(temp_file) as f:
                output = f.read()

            # Verify output is present
            assert "Test via basicConfig" in output
            assert "INFO" in output
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
