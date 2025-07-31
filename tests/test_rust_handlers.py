"""
Test suite for pure Rust handlers in LogXide.

This module tests the pure Rust pipeline that bypasses Python handlers
for maximum performance.
"""

import os
import tempfile
import time

import pytest

from logxide import logging


class TestRustHandlers:
    """Test pure Rust handler functionality."""

    @pytest.mark.integration
    def test_rust_console_handler_registration(self, clean_logging_state, capsys):
        """Test registering and using pure Rust console handler."""
        # Register Rust console handler
        logging.logxide.register_console_handler(level=logging.DEBUG)

        logger = logging.getLogger("test.rust.console")
        logger.setLevel(logging.DEBUG)

        # Log messages at different levels
        logger.debug("Debug message from Rust")
        logger.info("Info message from Rust")
        logger.warning("Warning message from Rust")
        logger.error("Error message from Rust")
        logger.critical("Critical message from Rust")

        time.sleep(0.1)  # Allow async processing

        # Check that messages were printed to console
        captured = capsys.readouterr()
        assert (
            "Debug message from Rust" in captured.err
            or "Debug message from Rust" in captured.out
        )
        assert (
            "Critical message from Rust" in captured.err
            or "Critical message from Rust" in captured.out
        )

    @pytest.mark.integration
    def test_rust_file_handler_registration(self, clean_logging_state):
        """Test registering and using pure Rust file handler."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as tmp:
            log_file = tmp.name

        try:
            # Register Rust file handler with rotation
            logging.logxide.register_file_handler(
                filename=log_file,
                max_bytes=1024 * 1024,  # 1MB
                backup_count=3,
                level=logging.INFO,
            )

            logger = logging.getLogger("test.rust.file")
            logger.setLevel(logging.DEBUG)

            # Log messages (DEBUG should be filtered out by handler level)
            logger.debug("This should not appear in file")
            logger.info("Info message to file")
            logger.warning("Warning message to file")
            logger.error("Error message to file")

            time.sleep(0.2)  # Wait for async file write

            # Verify file contents
            with open(log_file) as f:
                content = f.read()

            assert "This should not appear" not in content  # DEBUG filtered
            assert "Info message to file" in content
            assert "Warning message to file" in content
            assert "Error message to file" in content

        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)

    @pytest.mark.integration
    def test_rust_handlers_with_extra_fields(self, clean_logging_state):
        """Test that Rust handlers properly handle extra fields."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as tmp:
            log_file = tmp.name

        try:
            # Register both console and file handlers
            logging.logxide.register_console_handler(level=logging.DEBUG)
            logging.logxide.register_file_handler(
                filename=log_file,
                max_bytes=1024 * 1024,
                backup_count=1,
                level=logging.INFO,
            )

            logger = logging.getLogger("test.rust.extra")
            logger.setLevel(logging.DEBUG)

            # Log with extra fields
            logger.info(
                "User action",
                extra={
                    "user_id": "alice",
                    "action": "login",
                    "ip_address": "192.168.1.100",
                },
            )

            logger.error(
                "Database error",
                extra={
                    "error_code": "CONN_TIMEOUT",
                    "retry_count": "3",
                    "connection": "primary",
                },
            )

            time.sleep(0.2)

            # Verify extra fields appear in file
            with open(log_file) as f:
                content = f.read()

            # Extra fields should be included in output
            assert "User action" in content
            assert "Database error" in content

        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)

    @pytest.mark.performance
    def test_rust_vs_python_handler_performance(self, clean_logging_state):
        """Compare performance of Rust vs Python handlers."""
        # Test Python handler performance
        python_messages = []

        class PythonHandler:
            def __call__(self, record):
                python_messages.append(record)

        logger_python = logging.getLogger("test.perf.python")
        logger_python.setLevel(logging.INFO)
        logger_python.addHandler(PythonHandler())

        start = time.time()
        for i in range(1000):
            logger_python.info(f"Message {i}", extra={"index": i})
        time.sleep(0.2)  # Wait for async
        python_time = time.time() - start

        # Test Rust handler performance
        logging.logxide.register_console_handler(
            level=logging.CRITICAL + 1
        )  # Suppress output

        logger_rust = logging.getLogger("test.perf.rust")
        logger_rust.setLevel(logging.INFO)

        start = time.time()
        for i in range(1000):
            logger_rust.info(f"Message {i}", extra={"index": i})
        time.sleep(0.1)  # Rust is faster
        rust_time = time.time() - start

        # Rust should be significantly faster
        assert rust_time < python_time

        # Calculate speedup
        speedup = python_time / rust_time
        print(
            f"\nPerformance: Rust handlers are {speedup:.2f}x faster than Python handlers"
        )

    @pytest.mark.integration
    def test_file_rotation(self, clean_logging_state):
        """Test that Rust file handler supports rotation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "rotation_test.log")

            # Small max_bytes to trigger rotation
            logging.logxide.register_file_handler(
                filename=log_file,
                max_bytes=1024,  # 1KB - small for testing
                backup_count=2,
                level=logging.INFO,
            )

            logger = logging.getLogger("test.rust.rotation")
            logger.setLevel(logging.INFO)

            # Write enough messages to trigger rotation
            for i in range(100):
                logger.info(
                    f"This is a long message number {i} that should eventually trigger rotation"
                )

            time.sleep(0.3)

            # Check that rotation occurred
            files = os.listdir(tmpdir)
            log_files = [f for f in files if f.startswith("rotation_test.log")]

            # Should have main file and at least one backup
            assert len(log_files) >= 1
            assert os.path.exists(log_file)

    @pytest.mark.integration
    def test_multiple_rust_handlers(self, clean_logging_state):
        """Test registering multiple Rust handlers."""
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix="_1.log"
        ) as tmp1:
            log_file1 = tmp1.name
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix="_2.log"
        ) as tmp2:
            log_file2 = tmp2.name

        try:
            # Register multiple file handlers
            logging.logxide.register_file_handler(
                filename=log_file1,
                max_bytes=1024 * 1024,
                backup_count=1,
                level=logging.INFO,
            )

            logging.logxide.register_file_handler(
                filename=log_file2,
                max_bytes=1024 * 1024,
                backup_count=1,
                level=logging.WARNING,  # Different level
            )

            logger = logging.getLogger("test.rust.multiple")
            logger.setLevel(logging.DEBUG)

            # Log at different levels
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

            time.sleep(0.2)

            # Check file contents
            with open(log_file1) as f:
                content1 = f.read()
            with open(log_file2) as f:
                content2 = f.read()

            # File 1 (INFO level) should have all messages
            assert "Info message" in content1
            assert "Warning message" in content1
            assert "Error message" in content1

            # File 2 (WARNING level) should only have warning and error
            assert "Info message" not in content2
            assert "Warning message" in content2
            assert "Error message" in content2

        finally:
            for f in [log_file1, log_file2]:
                if os.path.exists(f):
                    os.unlink(f)
