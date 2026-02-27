"""
Tests for compatibility functions in logxide.

This module tests the newly implemented Python logging API compatibility
functions to ensure they work correctly and maintain compatibility with
the standard library logging module.
"""

import warnings

import pytest

from logxide import logging
from logxide.compat_functions import (
    _registerHandler,
    _unregisterHandler,
    addLevelName,
    captureWarnings,
    getHandlerByName,
    getHandlerNames,
    getLevelName,
    getLevelNamesMapping,
    getLogRecordFactory,
    makeLogRecord,
    setLogRecordFactory,
)


class TestLevelNames:
    """Test level name functions."""

    def test_addLevelName(self):
        """Test adding a custom level name."""
        addLevelName(25, "CUSTOM")
        assert getLevelName(25) == "CUSTOM"
        assert getLevelName("CUSTOM") == 25

    def test_getLevelName_with_number(self):
        """Test getting level name from number."""
        assert getLevelName(10) == "DEBUG"
        assert getLevelName(20) == "INFO"
        assert getLevelName(30) == "WARNING"
        assert getLevelName(40) == "ERROR"
        assert getLevelName(50) == "CRITICAL"

    def test_getLevelName_with_string(self):
        """Test getting level number from string."""
        assert getLevelName("DEBUG") == 10
        assert getLevelName("INFO") == 20
        assert getLevelName("WARNING") == 30
        assert getLevelName("ERROR") == 40
        assert getLevelName("CRITICAL") == 50

    def test_getLevelName_case_insensitive(self):
        """Test that level name lookup is case insensitive."""
        assert getLevelName("debug") == 10
        assert getLevelName("Debug") == 10
        assert getLevelName("DEBUG") == 10

    def test_getLevelName_unknown(self):
        """Test getting unknown level name."""
        assert getLevelName(999) == "Level 999"
        assert getLevelName("UNKNOWN") == "Level UNKNOWN"


class TestCaptureWarnings:
    """Test warning capture functionality."""

    def teardown_method(self):
        """Ensure warnings are restored after each test."""
        captureWarnings(False)

    def test_captureWarnings_enable(self):
        """Test enabling warning capture."""
        captureWarnings(True)
        # If no exception, it worked
        assert True

    def test_captureWarnings_disable(self):
        """Test disabling warning capture."""
        captureWarnings(True)
        captureWarnings(False)
        # If no exception, it worked
        assert True

    def test_captureWarnings_toggle(self):
        """Test toggling warning capture multiple times."""
        captureWarnings(True)
        captureWarnings(False)
        captureWarnings(True)
        captureWarnings(False)
        assert True


class TestMakeLogRecord:
    """Test makeLogRecord function."""

    def test_makeLogRecord_basic(self):
        """Test creating a log record from a dictionary."""
        record_dict = {
            "name": "test.logger",
            "msg": "Test message",
            "levelno": 20,
            "levelname": "INFO",
            "pathname": "/path/to/file.py",
            "filename": "file.py",
            "lineno": 42,
        }

        record = makeLogRecord(record_dict)

        assert record.name == "test.logger"
        assert record.msg == "Test message"
        assert record.levelno == 20
        assert record.levelname == "INFO"

    def test_makeLogRecord_minimal(self):
        """Test creating a log record with minimal data."""
        record_dict = {
            "name": "test",
            "msg": "message",
        }

        record = makeLogRecord(record_dict)

        assert record.name == "test"
        assert record.msg == "message"

    def test_makeLogRecord_with_extra_fields(self):
        """Test creating a log record with extra custom fields."""
        record_dict = {
            "name": "test",
            "msg": "message",
            "custom_field": "custom_value",
            "user_id": 12345,
        }

        record = makeLogRecord(record_dict)

        assert record.custom_field == "custom_value"
        assert record.user_id == 12345

    def test_makeLogRecord_empty_dict(self):
        """Test creating a log record from an empty dictionary."""
        record = makeLogRecord({})

        # Should not raise an exception
        assert record is not None


class TestLogRecordFactory:
    """Test log record factory functions."""

    def test_getLogRecordFactory_default(self):
        """Test getting the default log record factory."""
        factory = getLogRecordFactory()
        # Default should be None or a callable
        assert factory is None or callable(factory)

    def test_setLogRecordFactory(self):
        """Test setting a custom log record factory."""

        def custom_factory(*args, **kwargs):
            return {"custom": True}

        original = getLogRecordFactory()

        try:
            setLogRecordFactory(custom_factory)
            assert getLogRecordFactory() == custom_factory
        finally:
            # Restore original
            setLogRecordFactory(original)

    def test_setLogRecordFactory_none(self):
        """Test setting log record factory to None."""
        original = getLogRecordFactory()

        try:
            setLogRecordFactory(None)
            assert getLogRecordFactory() is None
        finally:
            setLogRecordFactory(original)


class TestLevelNamesMapping:
    """Test getLevelNamesMapping function."""

    def test_getLevelNamesMapping_returns_dict(self):
        """Test that getLevelNamesMapping returns a dictionary."""
        mapping = getLevelNamesMapping()
        assert isinstance(mapping, dict)

    def test_getLevelNamesMapping_has_standard_levels(self):
        """Test that the mapping contains standard log levels."""
        mapping = getLevelNamesMapping()

        assert mapping["DEBUG"] == 10
        assert mapping["INFO"] == 20
        assert mapping["WARNING"] == 30
        assert mapping["ERROR"] == 40
        assert mapping["CRITICAL"] == 50

    def test_getLevelNamesMapping_has_aliases(self):
        """Test that the mapping contains level aliases."""
        mapping = getLevelNamesMapping()

        assert mapping["WARN"] == 30  # Alias for WARNING
        assert mapping["FATAL"] == 50  # Alias for CRITICAL

    def test_getLevelNamesMapping_returns_copy(self):
        """Test that getLevelNamesMapping returns a copy, not the original."""
        # Get initial state
        initial_mapping = getLevelNamesMapping()
        initial_keys = set(initial_mapping.keys())

        mapping1 = getLevelNamesMapping()

        # Modify one mapping
        mapping1["CUSTOM_COPY_TEST"] = 999

        # Get a fresh copy
        mapping2 = getLevelNamesMapping()

        # The new mapping should only have original keys
        # (it may have keys from other tests, but not our CUSTOM_COPY_TEST)
        assert "CUSTOM_COPY_TEST" not in mapping2

    def test_getLevelNamesMapping_is_complete(self):
        """Test that the mapping contains all expected levels."""
        mapping = getLevelNamesMapping()

        # Should have at least the standard levels plus aliases
        assert len(mapping) >= 7


class TestHandlerRegistry:
    """Test handler registry functions."""

    def teardown_method(self):
        """Clean up handlers after each test."""
        for name in list(getHandlerNames()):
            _unregisterHandler(name)

    def test_getHandlerNames_empty(self):
        """Test getting handler names when none are registered."""
        names = getHandlerNames()
        assert isinstance(names, list)

    def test_registerHandler(self):
        """Test registering a handler."""
        from logxide.compat_handlers import NullHandler

        handler = NullHandler()
        _registerHandler("test_handler", handler)

        names = getHandlerNames()
        assert "test_handler" in names

    def test_getHandlerByName(self):
        """Test getting a handler by name."""
        from logxide.compat_handlers import NullHandler

        handler = NullHandler()
        _registerHandler("test_handler", handler)

        retrieved = getHandlerByName("test_handler")
        assert retrieved is handler

    def test_getHandlerByName_not_found(self):
        """Test getting a non-existent handler."""
        handler = getHandlerByName("non_existent")
        assert handler is None

    def test_unregisterHandler(self):
        """Test unregistering a handler."""
        from logxide.compat_handlers import NullHandler

        handler = NullHandler()
        _registerHandler("test_handler", handler)

        assert "test_handler" in getHandlerNames()

        _unregisterHandler("test_handler")

        assert "test_handler" not in getHandlerNames()

    def test_unregisterHandler_not_found(self):
        """Test unregistering a non-existent handler."""
        # Should not raise an exception
        _unregisterHandler("non_existent")

    def test_multiple_handlers(self):
        """Test registering multiple handlers."""
        from logxide.compat_handlers import NullHandler

        handler1 = NullHandler()
        handler2 = NullHandler()
        handler3 = NullHandler()

        _registerHandler("handler1", handler1)
        _registerHandler("handler2", handler2)
        _registerHandler("handler3", handler3)

        names = getHandlerNames()
        assert len(names) == 3
        assert "handler1" in names
        assert "handler2" in names
        assert "handler3" in names


class TestIntegration:
    """Integration tests for compatibility functions."""

    def test_all_functions_importable(self):
        """Test that all compatibility functions can be imported from logging."""
        from logxide import logging

        assert hasattr(logging, "captureWarnings")
        assert hasattr(logging, "makeLogRecord")
        assert hasattr(logging, "getLogRecordFactory")
        assert hasattr(logging, "setLogRecordFactory")
        assert hasattr(logging, "getLevelNamesMapping")
        assert hasattr(logging, "getHandlerByName")
        assert hasattr(logging, "getHandlerNames")

    def test_all_functions_callable(self):
        """Test that all compatibility functions are callable."""
        from logxide import logging

        assert callable(logging.captureWarnings)
        assert callable(logging.makeLogRecord)
        assert callable(logging.getLogRecordFactory)
        assert callable(logging.setLogRecordFactory)
        assert callable(logging.getLevelNamesMapping)
        assert callable(logging.getHandlerByName)
        assert callable(logging.getHandlerNames)

    def test_makeLogRecord_with_real_logger(self):
        """Test makeLogRecord integration with actual logging."""
        from logxide import logging

        record_dict = {
            "name": "test.integration",
            "msg": "Integration test message",
            "levelno": 20,
            "levelname": "INFO",
        }

        record = logging.makeLogRecord(record_dict)

        # Verify the record was created correctly
        assert record.name == "test.integration"
        assert record.msg == "Integration test message"
