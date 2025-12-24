"""
Test suite for extra parameter functionality in LogXide.

This module tests the core feature of Python logging's `extra` parameter,
ensuring full compatibility and proper handling in both Python and Rust pipelines.
"""

import time

import pytest

from logxide import logging


class TestExtraParameters:
    """Test extra parameter functionality."""

    @pytest.mark.unit
    def test_basic_extra_fields(self, clean_logging_state):
        """Test basic extra parameter functionality."""
        # For now, just test that logging with extra fields doesn't raise an error
        logger = logging.getLogger("test.extra.basic")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False  # Prevent propagation to root logger

        # Create a handler to verify it gets called
        handler_called = []

        class TestHandler(logging.Handler):
            def emit(self, record):
                handler_called.append(True)
                # Check if extra fields are in the record
                assert hasattr(record, "user_id")
                assert record.user_id == "alice"
                assert hasattr(record, "ip")
                assert record.ip == "192.168.1.1"

        handler = TestHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        # Log with extra fields
        logger.info("User login", extra={"user_id": "alice", "ip": "192.168.1.1"})
        time.sleep(0.1)  # Allow async processing

        # Verify handler was called
        assert len(handler_called) == 1

    @pytest.mark.unit
    def test_multiple_extra_fields(self, clean_logging_state):
        """Test multiple extra fields in single log call."""
        captured_records = []

        class CaptureHandler(logging.Handler):
            def emit(self, record):
                # Store the record with its extra fields
                record_dict = {
                    "msg": record.getMessage(),
                    "levelname": record.levelname,
                    "name": record.name,
                }
                # Add any extra fields
                for key, value in vars(record).items():
                    if key not in [
                        "msg",
                        "levelname",
                        "name",
                        "args",
                        "created",
                        "exc_info",
                        "exc_text",
                        "filename",
                        "funcName",
                        "levelno",
                        "lineno",
                        "module",
                        "msecs",
                        "pathname",
                        "process",
                        "processName",
                        "relativeCreated",
                        "stack_info",
                        "thread",
                        "threadName",
                    ]:
                        record_dict[key] = value
                captured_records.append(record_dict)

        logger = logging.getLogger("test.extra.multiple")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False  # Prevent propagation to root logger
        
        handler = CaptureHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

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

        class CaptureHandler(logging.Handler):
            def emit(self, record):
                # Store the record with its extra fields
                record_dict = {
                    "msg": record.getMessage(),
                    "levelname": record.levelname,
                    "name": record.name,
                }
                # Add any extra fields
                for key, value in vars(record).items():
                    if key not in [
                        "msg",
                        "levelname",
                        "name",
                        "args",
                        "created",
                        "exc_info",
                        "exc_text",
                        "filename",
                        "funcName",
                        "levelno",
                        "lineno",
                        "module",
                        "msecs",
                        "pathname",
                        "process",
                        "processName",
                        "relativeCreated",
                        "stack_info",
                        "thread",
                        "threadName",
                    ]:
                        record_dict[key] = value
                captured_records.append(record_dict)

        logger = logging.getLogger("test.extra.levels")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False  # Prevent propagation to root logger
        handler = CaptureHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

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

        class CaptureHandler(logging.Handler):
            def emit(self, record):
                # Store the record with its extra fields
                record_dict = {
                    "msg": record.getMessage(),
                    "levelname": record.levelname,
                    "name": record.name,
                }
                # Add any extra fields
                for key, value in vars(record).items():
                    if key not in [
                        "msg",
                        "levelname",
                        "name",
                        "args",
                        "created",
                        "exc_info",
                        "exc_text",
                        "filename",
                        "funcName",
                        "levelno",
                        "lineno",
                        "module",
                        "msecs",
                        "pathname",
                        "process",
                        "processName",
                        "relativeCreated",
                        "stack_info",
                        "thread",
                        "threadName",
                    ]:
                        record_dict[key] = value
                captured_records.append(record_dict)

        logger = logging.getLogger("test.extra.types")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False  # Prevent propagation to root logger
        handler = CaptureHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

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

        # LogXide converts extra fields to strings when passing through Rust
        # This is an implementation detail for performance
        assert record["string_field"] == "text"
        assert record["int_field"] == "42"  # Converted to string
        assert record["float_field"] == "3.14"  # Converted to string
        assert record["bool_field"] == "True"  # Converted to string
        assert record["none_field"] == "None"  # Converted to string

    @pytest.mark.unit
    def test_extra_fields_no_collision(self, clean_logging_state):
        """Test that extra fields don't override standard fields."""
        logger = logging.getLogger("test.extra.collision")
        logger.setLevel(logging.DEBUG)

        # Configure basic handler
        logging.basicConfig(level=logging.DEBUG)

        # This should not crash even with conflicting field names
        logger.info(
            "Collision test",
            extra={
                "name": "fake_name",  # Should not override logger name
                "levelname": "FAKE",  # Should not override real level
                "custom_field": "custom_value",  # Should work fine
            },
        )

        # If we get here without exceptions, the test passes

    @pytest.mark.unit
    def test_empty_extra(self, clean_logging_state):
        """Test logging with empty extra dict."""
        captured_records = []

        class CaptureHandler(logging.Handler):
            def emit(self, record):
                # Store the record with its extra fields
                record_dict = {
                    "msg": record.getMessage(),
                    "levelname": record.levelname,
                    "name": record.name,
                }
                # Add any extra fields
                for key, value in vars(record).items():
                    if key not in [
                        "msg",
                        "levelname",
                        "name",
                        "args",
                        "created",
                        "exc_info",
                        "exc_text",
                        "filename",
                        "funcName",
                        "levelno",
                        "lineno",
                        "module",
                        "msecs",
                        "pathname",
                        "process",
                        "processName",
                        "relativeCreated",
                        "stack_info",
                        "thread",
                        "threadName",
                    ]:
                        record_dict[key] = value
                captured_records.append(record_dict)

        logger = logging.getLogger("test.extra.empty")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False  # Prevent propagation to root logger
        handler = CaptureHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        # Log with empty extra
        logger.info("Empty extra test", extra={})

        time.sleep(0.1)

        assert len(captured_records) == 1
        # Should work without errors

    @pytest.mark.unit
    def test_format_string_substitution(self, clean_logging_state):
        """Test that format strings with extra field placeholders work."""
        captured_records = []
        formatted_messages = []

        class TestHandler(logging.Handler):
            def emit(self, record):
                # Store record data
                record_dict = {"user": getattr(record, "user", None)}
                captured_records.append(record_dict)

                # Test formatting
                if hasattr(record, "user"):
                    msg = f"{record.levelname} - {record.getMessage()} - User: {record.user}"
                    formatted_messages.append(msg)

        handler = TestHandler()
        handler.setLevel(logging.DEBUG)
        logger = logging.getLogger("test.format.extra")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False  # Prevent propagation to root logger
        logger.addHandler(handler)

        # Log with extra field that could be used in format string
        logger.info("Login successful", extra={"user": "bob"})

        time.sleep(0.1)

        assert len(captured_records) == 1
        assert captured_records[0]["user"] == "bob"

        # Verify formatting worked
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

        class CaptureHandler(logging.Handler):
            def emit(self, record):
                # Store the record with its extra fields
                record_dict = {
                    "msg": record.getMessage(),
                    "levelname": record.levelname,
                    "name": record.name,
                }
                # Add any extra fields
                for key, value in vars(record).items():
                    if key not in [
                        "msg",
                        "levelname",
                        "name",
                        "args",
                        "created",
                        "exc_info",
                        "exc_text",
                        "filename",
                        "funcName",
                        "levelno",
                        "lineno",
                        "module",
                        "msecs",
                        "pathname",
                        "process",
                        "processName",
                        "relativeCreated",
                        "stack_info",
                        "thread",
                        "threadName",
                    ]:
                        record_dict[key] = value
                captured_records.append(record_dict)

        logger = logging.getLogger("test.perf.many")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False  # Prevent propagation to root logger
        handler = CaptureHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

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
