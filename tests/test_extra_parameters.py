"""
Test suite for extra parameter functionality in LogXide.

This module tests the core feature of Python logging's `extra` parameter,
ensuring full compatibility and proper handling in both Python and Rust pipelines.
"""

import os
import tempfile
import time

import pytest

from logxide import logging


class TestExtraParameters:
    """Test extra parameter functionality."""

    @pytest.mark.unit
    def test_basic_extra_fields(self, clean_logging_state):
        """Test basic extra parameter functionality."""
        captured_records = []

        def capture_handler(record):
            captured_records.append(record)

        logger = logging.getLogger("test.extra.basic")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(capture_handler)

        # Log with extra fields
        logger.info("User login", extra={"user_id": "alice", "ip": "192.168.1.1"})
        time.sleep(0.1)  # Allow async processing

        assert len(captured_records) == 1
        record = captured_records[0]
        assert "user_id" in record
        assert record["user_id"] == "alice"
        assert "ip" in record
        assert record["ip"] == "192.168.1.1"

    @pytest.mark.unit
    def test_multiple_extra_fields(self, clean_logging_state):
        """Test multiple extra fields in single log call."""
        captured_records = []

        def capture_handler(record):
            captured_records.append(record)

        logger = logging.getLogger("test.extra.multiple")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(capture_handler)

        # Log with many extra fields
        logger.warning(
            "System alert",
            extra={
                "component": "database",
                "severity": "high",
                "error_code": "DB_TIMEOUT",
                "retry_count": "3",
                "duration": "5.2s",
            },
        )
        time.sleep(0.1)

        assert len(captured_records) == 1
        record = captured_records[0]

        # Verify all extra fields are present
        assert record["component"] == "database"
        assert record["severity"] == "high"
        assert record["error_code"] == "DB_TIMEOUT"
        assert record["retry_count"] == "3"
        assert record["duration"] == "5.2s"

    @pytest.mark.unit
    def test_extra_fields_all_levels(self, clean_logging_state):
        """Test extra parameter works with all log levels."""
        captured_records = []

        def capture_handler(record):
            captured_records.append(record)

        logger = logging.getLogger("test.extra.levels")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(capture_handler)

        # Test all log levels with extra
        logger.debug("Debug msg", extra={"level": "debug"})
        logger.info("Info msg", extra={"level": "info"})
        logger.warning("Warning msg", extra={"level": "warning"})
        logger.error("Error msg", extra={"level": "error"})
        logger.critical("Critical msg", extra={"level": "critical"})

        time.sleep(0.2)

        assert len(captured_records) == 5

        # Verify each level has its extra field
        for i, expected_level in enumerate(
            ["debug", "info", "warning", "error", "critical"]
        ):
            assert "level" in captured_records[i]
            assert captured_records[i]["level"] == expected_level

    @pytest.mark.unit
    def test_extra_fields_type_conversion(self, clean_logging_state):
        """Test that various types in extra fields are handled correctly."""
        captured_records = []

        def capture_handler(record):
            captured_records.append(record)

        logger = logging.getLogger("test.extra.types")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(capture_handler)

        # Log with different types
        logger.info(
            "Type test",
            extra={
                "string_field": "text",
                "int_field": 42,
                "float_field": 3.14,
                "bool_field": True,
                "none_field": None,
            },
        )

        time.sleep(0.1)

        assert len(captured_records) == 1
        record = captured_records[0]

        # All values should be converted to strings in Rust
        assert record["string_field"] == "text"
        assert record["int_field"] == "42"
        assert record["float_field"] == "3.14"
        assert record["bool_field"] == "True"
        assert record["none_field"] == "None"

    @pytest.mark.unit
    def test_extra_fields_no_collision(self, clean_logging_state):
        """Test that extra fields don't override standard fields."""
        captured_records = []

        def capture_handler(record):
            captured_records.append(record)

        logger = logging.getLogger("test.extra.collision")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(capture_handler)

        # Try to override standard fields (should be ignored or handled gracefully)
        logger.info(
            "Collision test",
            extra={
                "name": "fake_name",  # Should not override logger name
                "levelname": "FAKE",  # Should not override real level
                "custom_field": "custom_value",  # Should work fine
            },
        )

        time.sleep(0.1)

        assert len(captured_records) == 1
        record = captured_records[0]

        # Standard fields should not be overridden
        assert record["name"] == "test.extra.collision"
        assert record["levelname"] == "INFO"

        # Custom field should be present
        assert record["custom_field"] == "custom_value"

    @pytest.mark.unit
    def test_empty_extra(self, clean_logging_state):
        """Test logging with empty extra dict."""
        captured_records = []

        def capture_handler(record):
            captured_records.append(record)

        logger = logging.getLogger("test.extra.empty")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(capture_handler)

        # Log with empty extra
        logger.info("Empty extra test", extra={})

        time.sleep(0.1)

        assert len(captured_records) == 1
        # Should work without errors

    @pytest.mark.integration
    def test_pure_rust_handlers_with_extra(self, clean_logging_state):
        """Test extra fields work with pure Rust handlers."""
        # Register pure Rust console handler
        import logxide

        logxide.register_console_handler(level=logging.DEBUG)

        logger = logging.getLogger("test.rust.extra")
        logger.setLevel(logging.DEBUG)

        # These should be processed entirely in Rust
        logger.info(
            "Rust handler test", extra={"handler": "rust", "processed_by": "rust"}
        )
        logger.error(
            "Error with context", extra={"error_code": "E001", "module": "auth"}
        )

        time.sleep(0.1)
        # Visual verification - messages should appear in console with extra fields

    @pytest.mark.integration
    def test_file_handler_with_extra(self, clean_logging_state):
        """Test extra fields are written to file correctly."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as tmp:
            log_file = tmp.name

        try:
            # Register Rust file handler
            import logxide

            logxide.register_file_handler(
                filename=log_file,
                max_bytes=1024 * 1024,
                backup_count=3,
                level=logging.INFO,
            )

            logger = logging.getLogger("test.file.extra")
            logger.setLevel(logging.DEBUG)

            # Log with extra fields
            logger.info("File test", extra={"user": "alice", "action": "login"})
            logger.error("File error", extra={"code": "F001", "severity": "high"})

            time.sleep(0.2)  # Wait for file write

            # Verify file contents
            with open(log_file) as f:
                content = f.read()
                assert "File test" in content
                assert "File error" in content
                # Extra fields should be included in some form

        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)

    @pytest.mark.unit
    def test_format_string_substitution(self, clean_logging_state):
        """Test that format strings with extra field placeholders work."""
        captured_records = []
        formatted_messages = []

        class TestFormatter(logging.Formatter):
            def format(self, record):
                # In reality, this is a NO-OP in LogXide, but we test the record has fields
                msg = f"{record.get('levelname', 'UNKNOWN')} - {record.get('msg', '')} - User: {record.get('user', 'unknown')}"
                formatted_messages.append(msg)
                return msg

        class TestHandler:
            def __init__(self):
                self.formatter = TestFormatter()

            def __call__(self, record):
                captured_records.append(record)
                if self.formatter:
                    self.formatter.format(record)

        handler = TestHandler()
        logger = logging.getLogger("test.format.extra")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        # Log with extra field that could be used in format string
        logger.info("Login successful", extra={"user": "bob"})

        time.sleep(0.1)

        assert len(captured_records) == 1
        assert captured_records[0]["user"] == "bob"

        # Even though Python formatter is NO-OP, we can verify the record has the field
        assert len(formatted_messages) == 1
        assert "bob" in formatted_messages[0]


class TestExtraParametersPerformance:
    """Test performance aspects of extra parameter handling."""

    @pytest.mark.performance
    def test_extra_fields_performance(self, clean_logging_state):
        """Test that extra fields don't significantly impact performance."""
        logger = logging.getLogger("test.perf.extra")
        logger.setLevel(logging.INFO)

        # Time logging without extra
        start = time.time()
        for i in range(100):
            logger.info(f"Message {i}")
        time_no_extra = time.time() - start

        # Time logging with extra
        start = time.time()
        for i in range(100):
            logger.info(f"Message {i}", extra={"iteration": i, "type": "test"})
        time_with_extra = time.time() - start

        # Extra fields should not cause significant slowdown
        # Allow up to 2x slowdown (in practice should be much less)
        assert time_with_extra < time_no_extra * 2

    @pytest.mark.performance
    def test_many_extra_fields(self, clean_logging_state):
        """Test handling of many extra fields."""
        captured_records = []

        def capture_handler(record):
            captured_records.append(record)

        logger = logging.getLogger("test.perf.many")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(capture_handler)

        # Create a large extra dict
        large_extra = {f"field_{i}": f"value_{i}" for i in range(50)}

        logger.info("Many fields test", extra=large_extra)

        time.sleep(0.2)

        assert len(captured_records) == 1
        record = captured_records[0]

        # Verify all fields made it through
        for i in range(50):
            assert f"field_{i}" in record
            assert record[f"field_{i}"] == f"value_{i}"
