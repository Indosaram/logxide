"""
Sentry integration for LogXide.

This module provides seamless integration with Sentry error tracking,
automatically sending log events at WARNING level and above to Sentry
when it's configured in the project.
"""

import sys
from typing import Any, Literal, Optional, cast

from .compat_handlers import CRITICAL, ERROR, WARNING, Handler


class SentryHandler(Handler):
    """
    A handler that sends log records to Sentry.

    Automatically detects if Sentry SDK is available and configured.
    Only sends events at WARNING level and above to avoid noise.
    """

    def __init__(self, level: int = WARNING, with_breadcrumbs: bool = True):
        """
        Initialize the Sentry handler.

        Args:
            level: Minimum log level to send to Sentry (default: WARNING)
            with_breadcrumbs: Whether to add breadcrumbs for lower-level logs
        """
        super().__init__()
        self.level = level
        self.with_breadcrumbs = with_breadcrumbs
        self._sentry_sdk = None
        self._sentry_available = False

        # Try to import Sentry SDK
        self._init_sentry()

    def _init_sentry(self) -> None:
        """Initialize Sentry SDK if available and configured."""
        try:
            import sentry_sdk

            self._sentry_sdk = sentry_sdk

            # Check if Sentry is actually configured
            hub = sentry_sdk.Hub.current
            if hub.client is not None:
                self._sentry_available = True
            else:
                # Sentry SDK is available but not configured
                self._sentry_available = False

        except ImportError:
            # Sentry SDK is not installed
            self._sentry_available = False

    def emit(self, record) -> None:
        """
        Emit a log record to Sentry.

        Args:
            record: The log record to emit
        """
        if not self._sentry_available:
            return

        try:
            # Extract information from the record
            level_no = getattr(record, "levelno", WARNING)
            level_name = getattr(record, "levelname", "WARNING")
            message = self._get_message(record)
            logger_name = getattr(record, "name", "logxide")

            # Only send events at or above our threshold
            if level_no >= self.level:
                self._send_sentry_event(
                    record, level_no, level_name, message, logger_name
                )
            elif self.with_breadcrumbs and level_no >= WARNING:
                # Add as breadcrumb for context
                self._add_breadcrumb(record, level_name, message, logger_name)

        except Exception as e:
            # Prevent logging errors from causing infinite loops
            self._handle_error(e)

    def _get_message(self, record) -> str:
        """Extract the message from a log record."""
        if hasattr(record, "getMessage"):
            return record.getMessage()
        elif hasattr(record, "msg"):
            return str(record.msg)
        elif hasattr(record, "message"):
            return str(record.message)
        elif isinstance(record, dict):
            return record.get("msg", str(record))
        else:
            return str(record)

    def _send_sentry_event(
        self, record, level_no: int, level_name: str, message: str, logger_name: str
    ) -> None:
        """Send an event to Sentry."""
        if not self._sentry_sdk:
            return

        # Map LogXide levels to Sentry levels
        sentry_level = self._map_level_to_sentry(level_no)

        # Prepare extra context
        extra = self._extract_extra_context(record)

        # Prepare tags
        tags = {
            "logger": logger_name,
            "logxide": True,
        }

        # Add thread and process info if available
        if hasattr(record, "thread"):
            tags["thread"] = str(record.thread)
        if hasattr(record, "process"):
            tags["process"] = str(record.process)

        # Send the event
        with self._sentry_sdk.configure_scope() as scope:
            # Set tags
            for key, value in tags.items():
                scope.set_tag(key, value)

            # Set extra context
            for key, value in extra.items():
                scope.set_extra(key, value)

            # Set level
            scope.level = sentry_level

            # Check if this is an exception record
            if hasattr(record, "exc_info") and record.exc_info:
                # This is an exception - capture it with the exception info
                self._sentry_sdk.capture_exception(error=record.exc_info)
            else:
                # Regular log message - capture as message
                self._sentry_sdk.capture_message(message, level=sentry_level)

    def _add_breadcrumb(
        self, record, level_name: str, message: str, logger_name: str
    ) -> None:
        """Add a breadcrumb to Sentry for context."""
        if not self._sentry_sdk:
            return

        self._sentry_sdk.add_breadcrumb(
            message=message,
            category="log",
            level=self._map_level_to_sentry_breadcrumb(level_name),
            data={
                "logger": logger_name,
                "level": level_name,
            },
        )

    def _map_level_to_sentry(
        self, level_no: int
    ) -> Literal["fatal", "critical", "error", "warning", "info", "debug"]:
        """Map Python logging levels to Sentry levels.
        
        Returns a Sentry-compatible log level string that matches the
        LogLevelStr type from sentry_sdk.
        """
        if level_no >= CRITICAL:
            return "fatal"
        elif level_no >= ERROR:
            return "error"
        elif level_no >= WARNING:
            return "warning"
        else:
            return "info"

    def _map_level_to_sentry_breadcrumb(
        self, level_name: str
    ) -> Literal["fatal", "critical", "error", "warning", "info", "debug"]:
        """Map Python logging level names to Sentry breadcrumb levels.
        
        Returns a Sentry-compatible log level string that matches the
        LogLevelStr type from sentry_sdk.
        """
        level_mapping = {
            "CRITICAL": "fatal",
            "ERROR": "error",
            "WARNING": "warning",
            "INFO": "info",
            "DEBUG": "debug",
        }
        result = level_mapping.get(level_name.upper(), "info")
        # Cast is safe because we control the mapping and default value
        return cast(
            Literal["fatal", "critical", "error", "warning", "info", "debug"], result
        )

    def _extract_extra_context(self, record) -> dict[str, Any]:
        """Extract extra context from a log record."""
        extra = {}

        # Standard record attributes
        for attr in ["filename", "lineno", "funcName", "pathname", "module"]:
            if hasattr(record, attr):
                extra[attr] = getattr(record, attr)

        # Thread and process info
        for attr in ["thread", "threadName", "process", "processName"]:
            if hasattr(record, attr):
                extra[attr] = getattr(record, attr)

        # Timestamp
        if hasattr(record, "created"):
            extra["timestamp"] = record.created

        # Any additional attributes that aren't standard
        if hasattr(record, "__dict__"):
            record_dict = record.__dict__
            standard_attrs = {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
            }

            for key, value in record_dict.items():
                if key not in standard_attrs and not key.startswith("_"):
                    try:
                        # Only include JSON-serializable values
                        import json

                        json.dumps(value)  # Test if serializable
                        extra[f"custom_{key}"] = value
                    except (TypeError, ValueError):
                        # Skip non-serializable values
                        pass

        return extra

    def _handle_error(self, error: Exception) -> None:
        """Handle errors that occur during Sentry emission."""
        # Write to stderr to avoid logging loops
        if sys.stderr:
            sys.stderr.write(f"SentryHandler error: {error}\n")

    @property
    def is_available(self) -> bool:
        """Check if Sentry is available and configured."""
        return self._sentry_available

    def __call__(self, record) -> None:
        """Make the handler callable for LogXide compatibility."""
        self.handle(record)


def auto_configure_sentry(enable: Optional[bool] = None) -> Optional[SentryHandler]:
    """
    Automatically configure Sentry integration if available.

    Args:
        enable: Explicitly enable/disable Sentry (None for auto-detect)

    Returns:
        SentryHandler instance if configured, None otherwise
    """
    if enable is False:
        return None

    try:
        import sentry_sdk

        # Check if Sentry is configured
        hub = sentry_sdk.Hub.current
        if hub.client is None and enable is not True:
            # Sentry SDK available but not configured, and not explicitly enabled
            return None

        # Create and return handler
        handler = SentryHandler()

        if handler.is_available or enable is True:
            return handler
        else:
            return None

    except ImportError:
        if enable is True:
            # Explicitly requested but not available
            import warnings

            warnings.warn(
                "Sentry integration requested but sentry-sdk is not installed. "
                "Install with: pip install logxide[sentry]",
                UserWarning,
                stacklevel=2,
            )
        return None


__all__ = ["SentryHandler", "auto_configure_sentry"]
