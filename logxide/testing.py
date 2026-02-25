"""
LogXide Testing Utilities

Provides pytest-compatible fixtures and utilities for capturing and testing log output.
Designed to be a drop-in replacement for pytest's caplog fixture.

Usage:
    # In conftest.py
    from logxide.testing import caplog

    # Or use LogCaptureFixture directly
    from logxide.testing import LogCaptureFixture

    def test_example(caplog):
        logger = logging.getLogger("test")
        logger.info("Hello, World!")

        assert "Hello, World!" in caplog.text
        assert ("test", logging.INFO, "Hello, World!") in caplog.record_tuples
"""

from contextlib import contextmanager
from typing import Generator, List, Optional, Tuple

from . import logxide as _logxide_ext
from .handlers import MemoryHandler


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
        with fixture.at_level(logging.DEBUG):
            logger.debug("test message")
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

    def set_level(self, level: int) -> None:
        """
        Set the minimum logging level for capture.

        Args:
            level: Logging level (e.g., logging.DEBUG, logging.INFO)
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
        # Store current level if possible
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
        with capture_logs(logging.INFO) as captured:
            logger.info("test")
        assert "test" in captured.text
    """
    fixture = LogCaptureFixture()
    fixture.set_level(level)
    yield fixture


# Note: pytest fixture integration is deferred to avoid import conflicts.
# When pytest imports this module, it may conflict with logxide's module replacement.
# Users should define the caplog fixture in their conftest.py if needed:
#
# from logxide.testing import LogCaptureFixture
#
# @pytest.fixture
# def caplog():
#     fixture = LogCaptureFixture()
#     yield fixture
#     fixture.clear()


__all__ = [
    "LogCaptureFixture",
    "capture_logs",
]
