"""
Tests for Sentry integration with LogXide.

These tests verify that LogXide properly integrates with Sentry SDK
to send log events at WARNING level and above to Sentry.
"""

import sys
from unittest.mock import Mock, patch

import pytest

# Import sentry_sdk for testing
import sentry_sdk


class TestSentryHandler:
    """Test the SentryHandler class functionality."""

    @pytest.fixture
    def mock_sentry_sdk(self):
        """Mock sentry_sdk for testing."""
        with patch("logxide.sentry_integration.sentry_sdk") as mock_sdk:
            mock_hub = Mock()
            mock_client = Mock()
            mock_hub.client = mock_client
            mock_sdk.Hub.current = mock_hub
            mock_sdk.configure_scope.return_value.__enter__ = Mock()
            mock_sdk.configure_scope.return_value.__exit__ = Mock()
            yield mock_sdk

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
        from logxide.sentry_integration import SentryHandler

        # Patch the _init_sentry method to simulate ImportError
        with patch.object(SentryHandler, "_init_sentry") as mock_init:

            def mock_init_sentry(self):
                self._sentry_sdk = None
                self._sentry_available = False

            mock_init.side_effect = mock_init_sentry

            handler = SentryHandler()
            assert not handler.is_available

    def test_sentry_handler_init_with_sentry(self, mock_sentry_sdk):
        """Test SentryHandler initialization when Sentry is available."""
        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler()
        assert handler.is_available
        assert handler.level == 30  # WARNING level

    def test_sentry_handler_init_without_client(self):
        """Test SentryHandler when Sentry SDK is available but not configured."""
        with patch("logxide.sentry_integration.sentry_sdk") as mock_sdk:
            mock_hub = Mock()
            mock_hub.client = None  # No client configured
            mock_sdk.Hub.current = mock_hub

            from logxide.sentry_integration import SentryHandler

            handler = SentryHandler()
            assert not handler.is_available

    def test_emit_below_threshold(self, mock_sentry_sdk, mock_record):
        """Test that logs below threshold don't go to Sentry."""
        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler(level=40)  # ERROR level
        mock_record.levelno = 30  # WARNING level (below threshold)

        handler.emit(mock_record)

        # Should not call capture_message or capture_exception
        mock_sentry_sdk.capture_message.assert_not_called()
        mock_sentry_sdk.capture_exception.assert_not_called()

    def test_emit_above_threshold(self, mock_sentry_sdk, mock_record):
        """Test that logs above threshold go to Sentry."""
        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler(level=30)  # WARNING level
        mock_record.levelno = 40  # ERROR level (above threshold)

        # Mock scope context manager
        mock_scope = Mock()
        mock_sentry_sdk.configure_scope.return_value.__enter__.return_value = mock_scope

        handler.emit(mock_record)

        # Should call capture_message
        mock_sentry_sdk.capture_message.assert_called_once()

        # Should set tags and extras
        mock_scope.set_tag.assert_called()
        mock_scope.set_extra.assert_called()

    def test_emit_exception_record(self, mock_sentry_sdk, mock_record):
        """Test handling of exception records."""
        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler()
        mock_record.exc_info = (Exception, Exception("test error"), None)

        # Mock scope context manager
        mock_scope = Mock()
        mock_sentry_sdk.configure_scope.return_value.__enter__.return_value = mock_scope

        handler.emit(mock_record)

        # Should call capture_exception for exception records
        mock_sentry_sdk.capture_exception.assert_called_once()
        mock_sentry_sdk.capture_message.assert_not_called()

    def test_level_mapping(self):
        """Test Python logging level to Sentry level mapping."""
        from logxide.compat_handlers import CRITICAL, ERROR, WARNING
        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler()

        assert handler._map_level_to_sentry(WARNING) == "warning"
        assert handler._map_level_to_sentry(ERROR) == "error"
        assert handler._map_level_to_sentry(CRITICAL) == "fatal"
        assert handler._map_level_to_sentry(10) == "info"  # DEBUG or below

    def test_message_extraction(self, mock_sentry_sdk):
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

    def test_extra_context_extraction(self, mock_sentry_sdk, mock_record):
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

    def test_breadcrumb_addition(self, mock_sentry_sdk):
        """Test breadcrumb addition for lower-level logs."""
        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler(with_breadcrumbs=True)

        record = Mock()
        record.levelno = 30  # WARNING
        record.levelname = "WARNING"
        record.name = "test.logger"
        record.getMessage.return_value = "Test warning"

        handler._add_breadcrumb(record, "WARNING", "Test warning", "test.logger")

        mock_sentry_sdk.add_breadcrumb.assert_called_once_with(
            message="Test warning",
            category="log",
            level="warning",
            data={"logger": "test.logger", "level": "WARNING"},
        )

    def test_error_handling(self, mock_sentry_sdk):
        """Test error handling during Sentry emission."""
        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler()

        # Mock an error during Sentry operation
        mock_sentry_sdk.configure_scope.side_effect = Exception("Sentry error")

        record = Mock()
        record.levelno = 40
        record.levelname = "ERROR"
        record.getMessage.return_value = "Test message"

        # Should handle the error gracefully
        with patch("sys.stderr") as mock_stderr:
            handler.emit(record)
            # Should write error to stderr
            mock_stderr.write.assert_called()

    def test_callable_interface(self, mock_sentry_sdk, mock_record):
        """Test that handler is callable for LogXide compatibility."""
        from logxide.sentry_integration import SentryHandler

        handler = SentryHandler()

        # Should be able to call handler directly
        handler(mock_record)

        # Should work the same as calling handle/emit
        assert callable(handler)


class TestAutoConfiguration:
    """Test automatic Sentry configuration functionality."""

    def test_auto_configure_with_sentry_available(self):
        """Test auto-configuration when Sentry is available and configured."""
        with patch("logxide.sentry_integration.sentry_sdk") as mock_sdk:
            mock_hub = Mock()
            mock_client = Mock()
            mock_hub.client = mock_client
            mock_sdk.Hub.current = mock_hub

            from logxide.sentry_integration import auto_configure_sentry

            handler = auto_configure_sentry()
            assert handler is not None
            assert handler.is_available

    def test_auto_configure_without_sentry_client(self):
        """Test auto-configuration when Sentry SDK is available but not configured."""
        with patch("logxide.sentry_integration.sentry_sdk") as mock_sdk:
            mock_hub = Mock()
            mock_hub.client = None  # No client configured
            mock_sdk.Hub.current = mock_hub

            from logxide.sentry_integration import auto_configure_sentry

            handler = auto_configure_sentry()
            assert handler is None

    def test_auto_configure_explicit_enable(self):
        """Test auto-configuration with explicit enable=True."""
        with patch("logxide.sentry_integration.sentry_sdk") as mock_sdk:
            mock_hub = Mock()
            mock_hub.client = None  # No client configured
            mock_sdk.Hub.current = mock_hub

            from logxide.sentry_integration import auto_configure_sentry

            # Should create handler even without client when explicitly enabled
            handler = auto_configure_sentry(enable=True)
            assert handler is not None

    def test_auto_configure_explicit_disable(self):
        """Test auto-configuration with explicit enable=False."""
        with patch("logxide.sentry_integration.sentry_sdk") as mock_sdk:
            mock_hub = Mock()
            mock_client = Mock()
            mock_hub.client = mock_client  # Client is configured
            mock_sdk.Hub.current = mock_hub

            from logxide.sentry_integration import auto_configure_sentry

            # Should not create handler when explicitly disabled
            handler = auto_configure_sentry(enable=False)
            assert handler is None

    def test_auto_configure_without_sentry_sdk(self):
        """Test auto-configuration when sentry-sdk is not installed."""
        with (
            patch.dict(sys.modules, {"sentry_sdk": None}),
            patch("builtins.__import__", side_effect=ImportError),
        ):
            from logxide.sentry_integration import auto_configure_sentry

            handler = auto_configure_sentry()
            assert handler is None

    def test_auto_configure_with_warning_when_requested_but_unavailable(self):
        """Test warning when Sentry is explicitly requested but not available."""
        with (
            patch.dict(sys.modules, {"sentry_sdk": None}),
            patch("builtins.__import__", side_effect=ImportError),
            patch("warnings.warn") as mock_warn,
        ):
            from logxide.sentry_integration import auto_configure_sentry

            handler = auto_configure_sentry(enable=True)
            assert handler is None
            mock_warn.assert_called_once()


class TestLogXideIntegration:
    """Test integration with LogXide's main functionality."""

    def test_install_with_sentry_auto_detection(self):
        """Test that install() auto-detects and configures Sentry."""
        with patch("logxide.sentry_integration.sentry_sdk") as mock_sdk:
            mock_hub = Mock()
            mock_client = Mock()
            mock_hub.client = mock_client
            mock_sdk.Hub.current = mock_hub

            # Mock the auto-configure function
            with patch(
                "logxide.module_system.auto_configure_sentry"
            ) as mock_auto_config:
                mock_handler = Mock()
                mock_auto_config.return_value = mock_handler

                from logxide.module_system import _auto_configure_sentry

                # Should call auto-configuration
                _auto_configure_sentry()
                mock_auto_config.assert_called_once_with(None)

    def test_install_with_explicit_sentry_control(self):
        """Test install() with explicit Sentry control."""
        with patch("logxide.module_system.auto_configure_sentry") as mock_auto_config:
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
        with patch("logxide.sentry_integration.sentry_sdk") as mock_sdk:
            mock_hub = Mock()
            mock_client = Mock()
            mock_hub.client = mock_client
            mock_sdk.Hub.current = mock_hub

            # Mock loggers
            mock_logxide_logger = Mock()
            mock_std_logger = Mock()

            with (
                patch(
                    "logxide.module_system.getLogger", return_value=mock_logxide_logger
                ),
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

        # Configure Sentry with a test DSN
        sentry_sdk.init(dsn="https://test@test.ingest.sentry.io/test")

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

        # Configure Sentry
        sentry_sdk.init(dsn="https://test@test.ingest.sentry.io/test")

        # Import LogXide after Sentry configuration
        from logxide import logging

        # Should work without errors
        logger = logging.getLogger("test")
        logger.error("Test error message")

        # Flush to ensure all messages are processed
        logging.flush()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
