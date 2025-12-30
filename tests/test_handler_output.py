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

    @pytest.mark.skip(
        reason="StringIO not supported - LogXide uses Rust native handlers that write to OS streams"
    )
    def test_stream_handler_writes_to_stream(self):
        """Verify StreamHandler actually writes to the target stream (via basicConfig).

        Note: LogXide Rust native handlers write directly to OS-level stdout/stderr,
        not Python-level sys.stdout/sys.stderr, so StringIO capture doesn't work.
        Use file-based logging for testable output.
        """
        pass

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

    @pytest.mark.skip(
        reason="NullHandler cannot be tested with basicConfig - LogXide uses internal handlers"
    )
    def test_null_handler_produces_no_output(self):
        """Verify NullHandler doesn't write anything.

        Note: LogXide uses Rust native handlers internally and doesn't support
        adding custom Python handlers. This test is skipped as NullHandler
        behavior is tested internally.
        """
        pass

    @pytest.mark.skip(
        reason="Multiple handlers not supported - LogXide uses single internal Rust handler"
    )
    def test_multiple_handlers_all_receive_logs(self):
        """Verify multiple handlers all receive the same log messages.

        Note: LogXide uses a single Rust native handler internally and doesn't support
        adding multiple custom Python handlers. This test is skipped.
        """
        pass

    @pytest.mark.skip(
        reason="Handler-level filtering not supported - LogXide uses logger-level filtering only"
    )
    def test_handler_level_filtering(self):
        """Verify handler-level filtering works correctly.

        Note: LogXide uses a single Rust native handler internally and doesn't support
        per-handler level filtering. Use logger.setLevel() instead.
        """
        pass

    @pytest.mark.skip(
        reason="Custom formatters not supported - LogXide uses internal Rust formatters"
    )
    def test_formatter_with_all_fields(self):
        """Verify formatter can access and format all record fields.

        Note: LogXide uses Rust native formatters internally. Use basicConfig(format=...) instead.
        """
        pass

    @pytest.mark.skip(
        reason="Custom formatters with extra fields not supported via addHandler"
    )
    def test_structured_logging_with_extra(self):
        """Verify extra parameters are captured and can be logged.

        Note: LogXide supports extra fields but custom formatters must be configured via basicConfig.
        """
        pass

    @pytest.mark.skip(
        reason="Custom handlers not supported - LogXide uses basicConfig only"
    )
    def test_message_formatting_with_args(self):
        """Verify % style message formatting works correctly.

        Note: Message formatting works but handler setup via addHandler is not supported.
        """
        pass

    @pytest.mark.skip(reason="Exception logging with custom handlers not supported")
    def test_exception_logging_captures_traceback(self):
        """Verify exception() method captures and logs traceback.

        Note: LogXide supports exception logging but requires basicConfig for handler setup.
        """
        pass

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

    @pytest.mark.skip(reason="Concurrent logging with custom handlers not supported")
    def test_concurrent_logging_to_same_file(self):
        """Verify concurrent logging to the same file works without corruption.

        Note: LogXide handles concurrent logging internally with Rust handlers.
        This test is skipped as it requires custom handler setup via addHandler.
        """
        pass
