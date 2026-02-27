"""
LogXide Testing Utilities

Provides pytest-compatible fixtures and utilities for capturing and testing log output.
Designed as an alternative to pytest's caplog fixture for logxide.

Usage:
    # In your conftest.py, add:
    import pytest
    from logxide import logging
    from logxide.testing import LogCaptureFixture

    @pytest.fixture
    def caplog_logxide():
        fixture = LogCaptureFixture()
        fixture.set_level(logging.DEBUG)
        yield fixture
        fixture.clear()

    # Then use in tests:
    def test_example(caplog_logxide):
        logger = logging.getLogger("test")
        logger.addHandler(caplog_logxide.handler)
        logger.info("Hello!")

        assert "Hello!" in caplog_logxide.text
        assert ("test", 20, "Hello!") in caplog_logxide.record_tuples

    # Or use capture_logs context manager directly (no conftest needed):
    from logxide.testing import capture_logs

    def test_example():
        logger = logging.getLogger("test")
        with capture_logs() as caplog:
            logger.addHandler(caplog.handler)
            logger.info("test")
        assert "test" in caplog.text
"""

from contextlib import contextmanager
from typing import Generator, List, Optional, Tuple

from . import logxide as _logxide_ext
from .handlers import MemoryHandler

# Get logging module
logging = _logxide_ext.logging


class LogCaptureFixture:
    """
    Pytest caplog-compatible log capture fixture.

    Captures log records and provides access to them in various formats:
    - `.records`: List of LogRecord objects
    - `.text`: All messages joined with newlines
    - `.record_tuples`: List of (logger_name, level, message) tuples
    - `.messages`: List of message strings only

    Example:
        fixture = LogCaptureFixture()
        logger = logging.getLogger("test")
        logger.addHandler(fixture.handler)
        logger.info("test message")
        assert "test message" in fixture.text
    """

    def __init__(self):
        """Initialize the capture fixture."""
        self._handler: Optional[MemoryHandler] = None
        self._initial_level: Optional[int] = None

    def _ensure_handler(self) -> MemoryHandler:
        """Ensure handler exists, creating if necessary."""
        if self._handler is None:
            self._handler = MemoryHandler()
        return self._handler

    @property
    def handler(self) -> MemoryHandler:
        """Get the underlying MemoryHandler."""
        return self._ensure_handler()

    @property
    def records(self) -> List:
        """
        Get all captured log records.

        Returns:
            List of LogRecord objects.
        """
        return self._ensure_handler().records

    @property
    def text(self) -> str:
        """
        Get all captured log messages as a single string.

        Returns:
            All messages joined with newlines.
        """
        return self._ensure_handler().text

    @property
    def record_tuples(self) -> List[Tuple[str, int, str]]:
        """
        Get captured records as tuples.

        Returns:
            List of (logger_name, level_number, message) tuples.
            Compatible with pytest caplog.record_tuples.
        """
        return self._ensure_handler().record_tuples

    @property
    def messages(self) -> List[str]:
        """
        Get just the message strings from all captured records.

        Returns:
            List of message strings.
        """
        return [r.msg for r in self.records]

    def clear(self) -> None:
        """Clear all captured records."""
        if self._handler is not None:
            self._handler.clear()

    def set_level(self, level: int, logger: Optional[str] = None) -> None:
        """
        Set the minimum logging level for capture.

        Args:
            level: Logging level (e.g., logging.DEBUG, logging.INFO)
            logger: Logger name (optional, for compatibility)
        """
        self._ensure_handler().setLevel(level)

    @contextmanager
    def at_level(
        self, level: int, logger: Optional[str] = None
    ) -> Generator[None, None, None]:
        """
        Context manager to temporarily set capture level.

        Args:
            level: Logging level to capture at
            logger: Logger name (currently ignored, captures all)

        Yields:
            None
        """
        handler = self._ensure_handler()
        try:
            old_level = handler._inner.level if hasattr(handler, "_inner") else None
        except:
            old_level = None

        handler.setLevel(level)
        try:
            yield
        finally:
            if old_level is not None:
                handler.setLevel(old_level)


@contextmanager
def capture_logs(level: int = 10) -> Generator[LogCaptureFixture, None, None]:
    """
    Context manager for capturing logs in tests.

    Args:
        level: Minimum log level to capture (default: DEBUG=10)

    Yields:
        LogCaptureFixture with captured logs

    Example:
        from logxide import logging
        from logxide.testing import capture_logs

        logger = logging.getLogger("mytest")
        logger.setLevel(logging.DEBUG)

        with capture_logs(logging.INFO) as captured:
            logger.addHandler(captured.handler)
            logger.info("test message")

        assert "test message" in captured.text
    """
    fixture = LogCaptureFixture()
    fixture.set_level(level)
    yield fixture
    fixture.clear()


__all__ = [
    "LogCaptureFixture",
    "capture_logs",
]
