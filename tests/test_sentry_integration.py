"""
Tests for Sentry integration with LogXide.

These tests verify that LogXide properly integrates with Sentry SDK
to send log events at WARNING level and above to Sentry.
"""

import sys
from unittest.mock import Mock, patch

import pytest
import sentry_sdk


class TestSentryHandler:
    """Test the SentryHandler class functionality."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        # Store original sentry state
        original_client = sentry_sdk.Hub.current.client
        yield
        # Restore original sentry state
        if original_client:
            sentry_sdk.Hub.current.bind_client(original_client)
        else:
            # Clear any test client
            sentry_sdk.Hub.current.bind_client(None)

    @pytest.fixture
    def captured_events(self):
        """Fixture to capture Sentry events instead of sending them."""
        events = []

        def before_send(event, hint):
            """Capture events instead of sending them."""
            events.append(event)
            return None  # Don't actually send

        return events, before_send

    @pytest.fixture
    def mock_record(self):
        """Create a mock log record."""
        record = Mock()
        record.levelno = 40  # ERROR level
        record.levelname = "ERROR"
        record.name = "test.logger"
        record.msg = "Test error message"
        record.getMessage.return_value = "Test error message"
        record.exc_info = None
        record.__dict__ = {
            "levelno": 40,
            "levelname": "ERROR",
            "name": "test.logger",
            "msg": "Test error message",
            "pathname": "/test/file.py",
            "lineno": 42,
            "funcName": "test_function",
            "thread": 12345,
            "process": 67890,
        }
        return record

    def test_import_without_sentry_sdk(self):
        """Test that SentryHandler handles missing sentry-sdk gracefully."""
        # This test needs to simulate missing sentry_sdk
        with patch.dict(sys.modules):
            # Remove sentry_sdk from modules
            if "sentry_sdk" in sys.modules:
                del sys.modules["sentry_sdk"]
            sys.modules["sentry_sdk"] = None

            # Reload the module to test import failure handling
            import importlib

            from logxide import sentry_integration

            importlib.reload(sentry_integration)

            handler = sentry_integration.SentryHandler()
            assert not handler.is_available

    def test_sentry_handler_init_with_sentry(self, captured_events):
        """Test SentryHandler initialization when Sentry is available."""
        events, before_send = captured_events

        # Configure Sentry
        sentry_sdk.init(
            dsn="https://1234567890abcdef@o123456.ingest.sentry.io/1234567",
            before_send=before_send,
        )

        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler()
        assert handler.is_available
        assert handler.level == 30  # WARNING level

    def test_sentry_handler_init_without_client(self):
        """Test SentryHandler when Sentry SDK is available but not configured."""
        # Clear any existing Sentry configuration
        sentry_sdk.Hub.current.bind_client(None)

        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler()
        assert not handler.is_available

    def test_emit_below_threshold(self, captured_events):
        """Test that logs below threshold don't go to Sentry."""
        events, before_send = captured_events

        # Configure Sentry
        sentry_sdk.init(
            dsn="https://1234567890abcdef@o123456.ingest.sentry.io/1234567",
            before_send=before_send,
        )

        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler(level=40)  # ERROR level

        # Create a WARNING level record
        record = Mock()
        record.levelno = 30  # WARNING level (below threshold)
        record.levelname = "WARNING"
        record.getMessage.return_value = "Test warning"

        handler.emit(record)

        # Force flush
        sentry_sdk.flush(timeout=1.0)

        # Should not send any events
        assert len(events) == 0

    def test_emit_above_threshold(self, captured_events, mock_record):
        """Test that logs above threshold go to Sentry."""
        events, before_send = captured_events

        # Configure Sentry
        sentry_sdk.init(
            dsn="https://1234567890abcdef@o123456.ingest.sentry.io/1234567",
            before_send=before_send,
        )

        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler(level=30)  # WARNING level
        # mock_record is already configured as ERROR level (40)

        handler.emit(mock_record)

        # Force flush
        sentry_sdk.flush(timeout=1.0)

        # Should send one event
        assert len(events) == 1
        event = events[0]

        # Verify event properties
        assert event["level"] == "error"
        assert "tags" in event
        assert event["tags"]["logger"] == "test.logger"
        assert event["tags"]["logxide"] is True

    def test_emit_exception_record(self, captured_events):
        """Test handling of exception records."""
        events, before_send = captured_events

        # Configure Sentry
        sentry_sdk.init(
            dsn="https://1234567890abcdef@o123456.ingest.sentry.io/1234567",
            before_send=before_send,
        )

        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler()

        # Create a record with exception info
        record = Mock()
        record.levelno = 40
        record.levelname = "ERROR"
        record.getMessage.return_value = "Test error"

        # Create real exception info
        try:
            raise ValueError("Test exception")
        except ValueError:
            record.exc_info = sys.exc_info()

        handler.emit(record)

        # Force flush
        sentry_sdk.flush(timeout=1.0)

        # Should send one event with exception
        assert len(events) == 1
        event = events[0]
        assert "exception" in event
        assert len(event["exception"]["values"]) > 0

    def test_level_mapping(self):
        """Test Python logging level to Sentry level mapping."""
        from logxide.compat_handlers import CRITICAL, ERROR, WARNING
        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler()

        assert handler._map_level_to_sentry(WARNING) == "warning"
        assert handler._map_level_to_sentry(ERROR) == "error"
        assert handler._map_level_to_sentry(CRITICAL) == "fatal"
        assert handler._map_level_to_sentry(10) == "info"  # DEBUG or below

    def test_message_extraction(self):
        """Test message extraction from different record types."""
        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler()

        # Test with getMessage method
        record1 = Mock()
        record1.getMessage.return_value = "getMessage result"
        assert handler._get_message(record1) == "getMessage result"

        # Test with msg attribute
        record2 = Mock()
        record2.msg = "msg attribute"
        del record2.getMessage  # Remove getAttribute to test fallback
        assert handler._get_message(record2) == "msg attribute"

        # Test with message attribute
        record3 = Mock()
        record3.message = "message attribute"
        del record3.getMessage
        del record3.msg
        assert handler._get_message(record3) == "message attribute"

        # Test with dict-like record
        record4 = {"msg": "dict message"}
        assert handler._get_message(record4) == "dict message"

        # Test with string record
        record5 = "string record"
        assert handler._get_message(record5) == "string record"

    def test_extra_context_extraction(self, mock_record):
        """Test extraction of extra context from log records."""
        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler()
        extra = handler._extract_extra_context(mock_record)

        # Should include standard attributes
        assert "pathname" in extra
        assert "lineno" in extra
        assert "funcName" in extra
        assert "thread" in extra
        assert "process" in extra

        # Should not include internal attributes
        assert "levelno" not in extra
        assert "levelname" not in extra

    def test_breadcrumb_addition(self, captured_events):
        """Test breadcrumb addition for lower-level logs."""
        events, before_send = captured_events

        # Configure Sentry
        sentry_sdk.init(
            dsn="https://1234567890abcdef@o123456.ingest.sentry.io/1234567",
            before_send=before_send,
        )

        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler(with_breadcrumbs=True)

        record = Mock()
        record.levelno = 30  # WARNING
        record.levelname = "WARNING"
        record.name = "test.logger"
        record.getMessage.return_value = "Test warning"

        handler._add_breadcrumb(record, "WARNING", "Test warning", "test.logger")

        # Now send an error to capture breadcrumbs
        error_record = Mock()
        error_record.levelno = 40
        error_record.levelname = "ERROR"
        error_record.getMessage.return_value = "Test error"
        error_record.exc_info = None

        handler.emit(error_record)
        sentry_sdk.flush(timeout=1.0)

        # Check that breadcrumb was added
        assert len(events) == 1

    def test_error_handling(self, captured_events):
        """Test error handling during Sentry emission."""
        events, before_send = captured_events

        # Configure Sentry
        sentry_sdk.init(
            dsn="https://1234567890abcdef@o123456.ingest.sentry.io/1234567",
            before_send=before_send,
        )

        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler()

        # Create a record that will cause an error
        record = Mock()
        record.levelno = 40
        record.levelname = "ERROR"
        # This will cause an error when trying to format
        record.getMessage.side_effect = Exception("Format error")

        # Should handle the error gracefully
        with patch("sys.stderr") as mock_stderr:
            handler.emit(record)
            # Should write error to stderr
            mock_stderr.write.assert_called()

    def test_callable_interface(self, mock_record):
        """Test that handler is callable for LogXide compatibility."""
        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler()

        # Should be able to call handler directly
        handler(mock_record)

        # Should work the same as calling handle/emit
        assert callable(handler)


class TestAutoConfiguration:
    """Test automatic Sentry configuration functionality."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        # Store original sentry state
        original_client = sentry_sdk.Hub.current.client
        yield
        # Restore original sentry state
        if original_client:
            sentry_sdk.Hub.current.bind_client(original_client)
        else:
            # Clear any test client
            sentry_sdk.Hub.current.bind_client(None)

    def test_auto_configure_with_sentry_available(self):
        """Test auto-configuration when Sentry is available and configured."""
        # Configure Sentry
        sentry_sdk.init(
            dsn="https://1234567890abcdef@o123456.ingest.sentry.io/1234567",
            before_send=lambda event, hint: None,
        )

        from logxide.sentry_integration import auto_configure_sentry

        handler = auto_configure_sentry()
        assert handler is not None
        assert handler.is_available

    def test_auto_configure_without_sentry_client(self):
        """Test auto-configuration when Sentry SDK is available but not configured."""
        # Clear any existing Sentry configuration
        sentry_sdk.Hub.current.bind_client(None)

        from logxide.sentry_integration import auto_configure_sentry

        handler = auto_configure_sentry()
        assert handler is None

    def test_auto_configure_explicit_enable(self):
        """Test auto-configuration with explicit enable=True."""
        # Clear any existing Sentry configuration
        sentry_sdk.Hub.current.bind_client(None)

        from logxide.sentry_integration import auto_configure_sentry

        # Should create handler even without client when explicitly enabled
        handler = auto_configure_sentry(enable=True)
        assert handler is not None

    def test_auto_configure_explicit_disable(self):
        """Test auto-configuration with explicit enable=False."""
        # Configure Sentry
        sentry_sdk.init(
            dsn="https://1234567890abcdef@o123456.ingest.sentry.io/1234567",
            before_send=lambda event, hint: None,
        )

        from logxide.sentry_integration import auto_configure_sentry

        # Should not create handler when explicitly disabled
        handler = auto_configure_sentry(enable=False)
        assert handler is None

    def test_auto_configure_without_sentry_sdk(self):
        """Test auto-configuration when sentry-sdk is not installed."""
        # This test simulates missing sentry_sdk
        with patch.dict(sys.modules):
            # Remove sentry_sdk from modules
            if "sentry_sdk" in sys.modules:
                del sys.modules["sentry_sdk"]
            sys.modules["sentry_sdk"] = None

            # Reload the module to pick up the patched import
            import importlib

            from logxide import sentry_integration

            importlib.reload(sentry_integration)

            handler = sentry_integration.auto_configure_sentry()
            assert handler is None

    def test_auto_configure_with_warning_when_requested_but_unavailable(self):
        """Test warning when Sentry is explicitly requested but not available."""
        # This test simulates missing sentry_sdk
        with patch.dict(sys.modules), patch("warnings.warn") as mock_warn:
            # Remove sentry_sdk from modules
            if "sentry_sdk" in sys.modules:
                del sys.modules["sentry_sdk"]
            sys.modules["sentry_sdk"] = None

            # Reload the module to pick up the patched import
            import importlib

            from logxide import sentry_integration

            importlib.reload(sentry_integration)

            handler = sentry_integration.auto_configure_sentry(enable=True)
            assert handler is None
            mock_warn.assert_called_once()


class TestLogXideIntegration:
    """Test integration with LogXide's main functionality."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        # Store original sentry state
        original_client = sentry_sdk.Hub.current.client
        yield
        # Restore original sentry state
        if original_client:
            sentry_sdk.Hub.current.bind_client(original_client)
        else:
            # Clear any test client
            sentry_sdk.Hub.current.bind_client(None)

    def test_install_with_sentry_auto_detection(self):
        """Test that install() auto-detects and configures Sentry."""
        # Configure Sentry
        sentry_sdk.init(
            dsn="https://1234567890abcdef@o123456.ingest.sentry.io/1234567",
            before_send=lambda event, hint: None,
        )

        with patch(
            "logxide.sentry_integration.auto_configure_sentry"
        ) as mock_auto_config:
            mock_handler = Mock()
            mock_auto_config.return_value = mock_handler

            from logxide.module_system import _auto_configure_sentry

            # Should call auto-configuration
            _auto_configure_sentry()
            mock_auto_config.assert_called_once_with(None)

    def test_install_with_explicit_sentry_control(self):
        """Test install() with explicit Sentry control."""
        with patch(
            "logxide.sentry_integration.auto_configure_sentry"
        ) as mock_auto_config:
            mock_handler = Mock()
            mock_auto_config.return_value = mock_handler

            from logxide.module_system import _auto_configure_sentry

            # Test explicit enable
            _auto_configure_sentry(True)
            mock_auto_config.assert_called_with(True)

            # Test explicit disable
            _auto_configure_sentry(False)
            mock_auto_config.assert_called_with(False)

    def test_sentry_handler_added_to_loggers(self):
        """Test that Sentry handler is added to both LogXide and standard loggers."""
        # Configure Sentry
        sentry_sdk.init(
            dsn="https://1234567890abcdef@o123456.ingest.sentry.io/1234567",
            before_send=lambda event, hint: None,
        )

        # Mock loggers
        mock_logxide_logger = Mock()
        mock_std_logger = Mock()

        with (
            patch("logxide.module_system.getLogger", return_value=mock_logxide_logger),
            patch("logging.root", mock_std_logger),
        ):
            from logxide.module_system import _auto_configure_sentry

            _auto_configure_sentry()

            # Should add handler to both loggers
            mock_logxide_logger.addHandler.assert_called_once()
            mock_std_logger.addHandler.assert_called_once()


@pytest.mark.integration
class TestSentryIntegrationEnd2End:
    """End-to-end integration tests (require sentry-sdk)."""

    def test_real_sentry_integration(self):
        """Test with real sentry-sdk (if available)."""

        # Configure Sentry with a test DSN that doesn't send events
        sentry_sdk.init(
            dsn="https://1234567890abcdef@o123456.ingest.sentry.io/1234567",
            before_send=lambda event, hint: None,  # Don't actually send
        )

        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler()
        assert handler.is_available

        # Create a test record
        record = Mock()
        record.levelno = 40  # ERROR
        record.levelname = "ERROR"
        record.name = "test"
        record.getMessage.return_value = "Test error"
        record.exc_info = None
        record.__dict__ = {"levelno": 40, "levelname": "ERROR", "name": "test"}

        # Should not raise exceptions
        handler.emit(record)

    def test_logxide_with_real_sentry(self):
        """Test LogXide auto-install with real Sentry."""

        # Configure Sentry with a test DSN that doesn't send events
        sentry_sdk.init(
            dsn="https://1234567890abcdef@o123456.ingest.sentry.io/1234567",
            before_send=lambda event, hint: None,  # Don't actually send
        )

        # Import LogXide after Sentry configuration
        from logxide import logging

        # Should work without errors
        logger = logging.getLogger("test")
        logger.error("Test error message")

        # Flush to ensure all messages are processed
        logging.flush()
