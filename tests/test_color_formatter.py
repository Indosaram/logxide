"""
Tests for ColorFormatter and ANSI color support.
"""

import pytest


class TestColorFormatter:
    """Test ColorFormatter functionality."""

    def test_color_formatter_import(self):
        """Test that ColorFormatter can be imported."""
        from logxide import ColorFormatter

        assert ColorFormatter is not None

    def test_color_formatter_creation(self):
        """Test ColorFormatter instantiation."""
        from logxide import ColorFormatter

        formatter = ColorFormatter()
        assert formatter is not None

    def test_color_formatter_with_format(self):
        """Test ColorFormatter with custom format string."""
        from logxide import ColorFormatter

        fmt = "%(ansi_level_color)s[%(levelname)s]%(ansi_reset_color)s %(message)s"
        formatter = ColorFormatter(fmt)
        assert formatter is not None

    def test_color_formatter_format_record(self):
        """Test formatting a log record with colors."""
        from logxide import ColorFormatter, LogRecord

        fmt = "%(ansi_level_color)s%(levelname)s%(ansi_reset_color)s: %(message)s"
        formatter = ColorFormatter(fmt)

        # Create a minimal record
        record = LogRecord(
            name="test",
            levelno=20,  # INFO
            pathname="test.py",
            lineno=1,
            msg="Test message",
        )
        record.levelname = "INFO"

        formatted = formatter.format(record)

        # Should contain ANSI escape codes
        assert "\x1b[32m" in formatted  # Green for INFO
        assert "\x1b[0m" in formatted  # Reset
        assert "Test message" in formatted

    def test_color_codes_by_level(self):
        """Test that different levels produce different colors."""
        from logxide import ColorFormatter, LogRecord

        fmt = "%(ansi_level_color)s%(levelname)s%(ansi_reset_color)s"
        formatter = ColorFormatter(fmt)

        levels = [
            (10, "DEBUG", "\x1b[37m"),  # White
            (20, "INFO", "\x1b[32m"),  # Green
            (30, "WARNING", "\x1b[33m"),  # Yellow
            (40, "ERROR", "\x1b[31m"),  # Red
            (50, "CRITICAL", "\x1b[35m"),  # Magenta
        ]

        for levelno, levelname, expected_color in levels:
            record = LogRecord(
                name="test",
                levelno=levelno,
                pathname="test.py",
                lineno=1,
                msg="msg",
            )
            record.levelname = levelname

            formatted = formatter.format(record)
            assert expected_color in formatted, (
                f"Expected {expected_color} for {levelname}"
            )
            assert "\x1b[0m" in formatted, "Expected reset code"


class TestMemoryHandlerCapture:
    """Test MemoryHandler pytest caplog compatibility."""

    def test_memory_handler_import(self):
        """Test MemoryHandler can be imported."""
        from logxide import MemoryHandler

        assert MemoryHandler is not None

    def test_memory_handler_creation(self):
        """Test MemoryHandler instantiation."""
        from logxide import MemoryHandler

        handler = MemoryHandler()
        assert handler is not None

    def test_memory_handler_records_property(self):
        """Test records property exists."""
        from logxide import MemoryHandler

        handler = MemoryHandler()
        records = handler.records
        assert isinstance(records, list)

    def test_memory_handler_text_property(self):
        """Test text property exists."""
        from logxide import MemoryHandler

        handler = MemoryHandler()
        text = handler.text
        assert isinstance(text, str)

    def test_memory_handler_record_tuples_property(self):
        """Test record_tuples property exists."""
        from logxide import MemoryHandler

        handler = MemoryHandler()
        tuples = handler.record_tuples
        assert isinstance(tuples, list)

    def test_memory_handler_clear(self):
        """Test clear method."""
        from logxide import MemoryHandler

        handler = MemoryHandler()
        handler.clear()
        assert len(handler.records) == 0


class TestPythonFormatter:
    """Test standard Python formatter."""

    def test_formatter_import(self):
        """Test Formatter can be imported from logxide."""
        try:
            from logxide import RustFormatter

            assert RustFormatter is not None
        except (ImportError, AttributeError):
            pytest.skip("RustFormatter not available in this build")

    def test_formatter_basic(self):
        """Test basic formatter functionality."""
        try:
            from logxide import RustFormatter, LogRecord

            formatter = RustFormatter("%(levelname)s - %(message)s")

            record = LogRecord(
                name="test",
                levelno=20,
                pathname="test.py",
                lineno=1,
                msg="Hello",
            )
            record.levelname = "INFO"

            formatted = formatter.format(record)
            assert "INFO" in formatted
            assert "Hello" in formatted
        except (ImportError, AttributeError):
            pytest.skip("RustFormatter not available in this build")


class TestTestingModule:
    """Test the testing module utilities."""

    def test_testing_module_import(self):
        """Test testing module can be imported."""
        from logxide import testing

        assert testing is not None

    def test_log_capture_fixture_import(self):
        """Test LogCaptureFixture can be imported."""
        from logxide.testing import LogCaptureFixture

        assert LogCaptureFixture is not None

    def test_capture_logs_import(self):
        """Test capture_logs context manager can be imported."""
        from logxide.testing import capture_logs

        assert capture_logs is not None

    def test_log_capture_fixture_creation(self):
        """Test LogCaptureFixture instantiation."""
        from logxide.testing import LogCaptureFixture

        fixture = LogCaptureFixture()
        assert fixture is not None

    def test_log_capture_fixture_properties(self):
        """Test LogCaptureFixture has required properties."""
        from logxide.testing import LogCaptureFixture

        fixture = LogCaptureFixture()

        # These should not raise
        _ = fixture.records
        _ = fixture.text
        _ = fixture.record_tuples
        _ = fixture.messages

    def test_capture_logs_context_manager(self):
        """Test capture_logs context manager works."""
        from logxide.testing import capture_logs

        with capture_logs() as captured:
            assert captured is not None
            assert hasattr(captured, "records")
            assert hasattr(captured, "text")


class TestFilterCallback:
    """Test Python callable filter support."""

    def test_add_filter_method_exists(self):
        """Test that addFilter method exists on logger."""
        from logxide import logging

        logger = logging.getLogger("test_filter")
        assert hasattr(logger, "addFilter")

    def test_add_remove_filter(self):
        """Test adding and removing filters."""
        from logxide import logging

        logger = logging.getLogger("test_filter_add_remove")

        class MyFilter:
            def filter(self, record):
                return True

        f = MyFilter()
        logger.addFilter(f)
        logger.removeFilter(f)
        # Should not raise

    def test_filter_can_suppress_record(self):
        """Test that filter returning False suppresses the record."""
        from logxide import logging, MemoryHandler

        logger = logging.getLogger("test_filter_suppress")
        handler = MemoryHandler()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        handler.setLevel(logging.DEBUG)

        class SuppressFilter:
            def filter(self, record):
                # Suppress all records
                return False

        f = SuppressFilter()
        logger.addFilter(f)

        logger.info("This should be suppressed")

        # Record should be suppressed
        assert len(handler.records) == 0

        # Cleanup
        logger.removeFilter(f)

    def test_filter_can_modify_message(self):
        """Test that filter can modify record.msg."""
        from logxide import logging, MemoryHandler

        logger = logging.getLogger("test_filter_modify")
        handler = MemoryHandler()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        handler.setLevel(logging.DEBUG)
        handler.clear()  # Clear any previous records

        class ModifyFilter:
            def filter(self, record):
                # Modify the message - replace 'secret' with '***'
                if 'secret' in record.get('msg', ''):
                    record['msg'] = record['msg'].replace('secret', '***')
                return True

        f = ModifyFilter()
        logger.addFilter(f)

        logger.info("password is secret123")

        # Check the message was modified
        assert len(handler.records) == 1
        assert '***' in handler.records[0].msg
        assert 'secret' not in handler.records[0].msg

        # Cleanup
        logger.removeFilter(f)

    def test_callable_filter(self):
        """Test that a plain callable works as a filter."""
        from logxide import logging, MemoryHandler

        logger = logging.getLogger("test_callable_filter")
        handler = MemoryHandler()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        handler.setLevel(logging.DEBUG)
        handler.clear()

        # Plain callable that filters based on level
        def level_filter(record):
            return record.get('levelno', 0) >= 30  # Only WARNING and above

        logger.addFilter(level_filter)

        logger.debug("This is debug")  # Should be filtered out by callable
        logger.info("This is info")    # Should be filtered out by callable
        logger.warning("This is warning")  # Should pass

        assert len(handler.records) == 1
        assert "warning" in handler.records[0].msg.lower()

        # Cleanup
        logger.removeFilter(level_filter)


class TestLevelBasedFlush:
    """Test HTTPHandler level-based flush feature."""

    def test_http_handler_has_flush_level_methods(self):
        """Test that HTTPHandler has setFlushLevel and getFlushLevel."""
        from logxide import HTTPHandler

        handler = HTTPHandler("http://localhost:9999/logs")
        assert hasattr(handler, "setFlushLevel")
        assert hasattr(handler, "getFlushLevel")

    def test_default_flush_level_is_error(self):
        """Test that default flush level is ERROR (40)."""
        from logxide import HTTPHandler

        handler = HTTPHandler("http://localhost:9999/logs")
        # Default should be ERROR = 40
        assert handler.getFlushLevel() == 40

    def test_set_flush_level(self):
        """Test setting custom flush level."""
        from logxide import HTTPHandler, logging

        handler = HTTPHandler("http://localhost:9999/logs")

        # Set to CRITICAL
        handler.setFlushLevel(logging.CRITICAL)  # 50
        assert handler.getFlushLevel() == 50

        # Set to WARNING
        handler.setFlushLevel(logging.WARNING)  # 30
        assert handler.getFlushLevel() == 30

        # Set to DEBUG (flush on every record)
        handler.setFlushLevel(logging.DEBUG)  # 10
        assert handler.getFlushLevel() == 10
