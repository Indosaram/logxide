"""
Production-ready utilities for LogXide.

This module provides production-grade features for LogXide logging:
- JSON formatting for log aggregation systems
- Environment variable configuration
- Graceful shutdown handling
- Rate limiting and sampling
- Context binding for request tracing
"""

import atexit
import json
import os
import signal
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Any

from .compat_handlers import (
    DEBUG,
    ERROR,
    INFO,
    WARNING,
    Handler,
    StreamHandler,
)

# Context variable for storing bound context
_bound_context: ContextVar[dict[str, Any]] = ContextVar("bound_context")
_bound_context.set({})


def _get_record_field(record, key, default=None):
    """Get a field from a record object."""
    return getattr(record, key, default)


# =============================================================================
# JSON Formatter
# =============================================================================


class JSONFormatter:
    """
    JSON formatter for structured logging.

    This formatter outputs log records as JSON objects, making them easy to
    parse by log aggregation systems like ELK Stack, Splunk, or Datadog.

    Attributes:
        include_timestamp: Include ISO 8601 timestamp
        include_thread_info: Include thread ID and name
        include_process_info: Include process ID and name
        include_source_info: Include file, line, and function info
        extra_fields: Additional static fields to include in every log
    """

    def __init__(
        self,
        include_timestamp: bool = True,
        include_thread_info: bool = True,
        include_process_info: bool = True,
        include_source_info: bool = False,
        extra_fields: dict[str, Any] | None = None,
    ):
        """
        Initialize JSON formatter.

        Args:
            include_timestamp: Include ISO 8601 timestamp (default: True)
            include_thread_info: Include thread ID and name (default: True)
            include_process_info: Include process ID and name (default: True)
            include_source_info: Include file, line, and function (default: False)
            extra_fields: Additional static fields for every log entry
        """
        self.include_timestamp = include_timestamp
        self.include_thread_info = include_thread_info
        self.include_process_info = include_process_info
        self.include_source_info = include_source_info
        self.extra_fields = extra_fields or {}

    def format(self, record) -> str:
        """
        Format a log record as JSON.

        Args:
            record: Log record (dict or object with attributes)

        Returns:
            JSON string representation of the log record
        """
        # Build the log entry
        log_entry: dict[str, Any] = {}

        # Handle both dict and object records
        if isinstance(record, dict):
            get_field = record.get
        else:

            def get_field(key, default=None):
                return _get_record_field(record, key, default)

        # Core fields (always included)
        log_entry["level"] = get_field("levelname", "UNKNOWN")
        log_entry["message"] = get_field("msg", "")
        log_entry["logger"] = get_field("name", "root")

        # Timestamp
        if self.include_timestamp:
            created = get_field("created", time.time())
            msecs = get_field("msecs", 0)
            # Create ISO 8601 timestamp
            import datetime

            dt = datetime.datetime.fromtimestamp(created, tz=datetime.timezone.utc)
            log_entry["timestamp"] = dt.isoformat()
            log_entry["timestamp_unix"] = created + msecs / 1000.0

        # Thread info
        if self.include_thread_info:
            log_entry["thread_id"] = get_field("thread", 0)
            log_entry["thread_name"] = get_field("threadName", "MainThread")

        # Process info
        if self.include_process_info:
            log_entry["process_id"] = get_field("process", 0)
            log_entry["process_name"] = get_field("processName", "MainProcess")

        # Source info
        if self.include_source_info:
            log_entry["pathname"] = get_field("pathname", "")
            log_entry["filename"] = get_field("filename", "")
            log_entry["lineno"] = get_field("lineno", 0)
            log_entry["funcName"] = get_field("funcName", "")
            log_entry["module"] = get_field("module", "")

        # Add static extra fields
        log_entry.update(self.extra_fields)

        # Add bound context
        bound_ctx = _bound_context.get()
        if bound_ctx:
            log_entry["context"] = bound_ctx.copy()

        # Add dynamic extra fields from the record
        if isinstance(record, dict):
            # Get extra fields from dict
            for key, value in record.items():
                if key not in (
                    "name",
                    "levelno",
                    "levelname",
                    "pathname",
                    "filename",
                    "module",
                    "lineno",
                    "funcName",
                    "created",
                    "msecs",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "processName",
                    "process",
                    "msg",
                    "args",
                    "exc_info",
                    "stack_info",
                ):
                    log_entry[key] = value
        else:
            # Check for extra attribute on record object
            if hasattr(record, "__dict__"):
                for key, value in record.__dict__.items():
                    if key not in (
                        "name",
                        "levelno",
                        "levelname",
                        "pathname",
                        "filename",
                        "module",
                        "lineno",
                        "funcName",
                        "created",
                        "msecs",
                        "relativeCreated",
                        "thread",
                        "threadName",
                        "processName",
                        "process",
                        "msg",
                        "args",
                        "exc_info",
                        "stack_info",
                    ):
                        log_entry[key] = value

        return json.dumps(log_entry, default=str, ensure_ascii=False)


class JSONHandler(StreamHandler):
    """
    Stream handler that outputs JSON formatted logs.

    Combines StreamHandler with JSONFormatter for easy setup.
    """

    def __init__(
        self,
        stream=None,
        include_timestamp: bool = True,
        include_thread_info: bool = True,
        include_process_info: bool = True,
        include_source_info: bool = False,
        extra_fields: dict[str, Any] | None = None,
    ):
        """
        Initialize JSON handler.

        Args:
            stream: Output stream (default: sys.stderr)
            include_timestamp: Include ISO 8601 timestamp
            include_thread_info: Include thread ID and name
            include_process_info: Include process ID and name
            include_source_info: Include file, line, and function
            extra_fields: Additional static fields for every log entry
        """
        super().__init__(stream)
        self.formatter = JSONFormatter(
            include_timestamp=include_timestamp,
            include_thread_info=include_thread_info,
            include_process_info=include_process_info,
            include_source_info=include_source_info,
            extra_fields=extra_fields,
        )


# =============================================================================
# Environment Variable Configuration
# =============================================================================


def configure_from_env(
    prefix: str = "LOGXIDE",
    default_level: int = WARNING,
    default_format: str | None = None,
) -> dict[str, Any]:
    """
    Configure logging from environment variables.

    Environment variables:
    - {prefix}_LEVEL: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - {prefix}_FORMAT: Log format string or "json" for JSON output
    - {prefix}_JSON: Set to "1" or "true" for JSON output
    - {prefix}_JSON_TIMESTAMP: Include timestamp in JSON (default: true)
    - {prefix}_JSON_THREAD: Include thread info in JSON (default: true)
    - {prefix}_JSON_PROCESS: Include process info in JSON (default: true)
    - {prefix}_JSON_SOURCE: Include source info in JSON (default: false)

    Args:
        prefix: Environment variable prefix (default: "LOGXIDE")
        default_level: Default log level if not specified
        default_format: Default format string if not specified

    Returns:
        Dictionary with configuration settings applied
    """
    from . import basicConfig, getLogger

    config: dict[str, Any] = {}

    # Parse log level
    level_str = os.environ.get(f"{prefix}_LEVEL", "").upper()
    level_map = {
        "DEBUG": DEBUG,
        "INFO": INFO,
        "WARNING": WARNING,
        "WARN": WARNING,
        "ERROR": ERROR,
        "CRITICAL": 50,
        "FATAL": 50,
    }
    level = level_map.get(level_str, default_level)
    config["level"] = level

    # Check for JSON output
    json_enabled = os.environ.get(f"{prefix}_JSON", "").lower() in ("1", "true", "yes")
    format_str = os.environ.get(f"{prefix}_FORMAT", "")

    if json_enabled or format_str.lower() == "json":
        # JSON output mode
        config["json"] = True
        config["json_timestamp"] = os.environ.get(
            f"{prefix}_JSON_TIMESTAMP", "true"
        ).lower() in ("1", "true", "yes")
        config["json_thread"] = os.environ.get(
            f"{prefix}_JSON_THREAD", "true"
        ).lower() in ("1", "true", "yes")
        config["json_process"] = os.environ.get(
            f"{prefix}_JSON_PROCESS", "true"
        ).lower() in ("1", "true", "yes")
        config["json_source"] = os.environ.get(
            f"{prefix}_JSON_SOURCE", "false"
        ).lower() in ("1", "true", "yes")

        # Apply configuration
        basicConfig(level=level)

        # Add JSON handler to root logger
        root_logger = getLogger()
        json_handler = JSONHandler(
            include_timestamp=config["json_timestamp"],
            include_thread_info=config["json_thread"],
            include_process_info=config["json_process"],
            include_source_info=config["json_source"],
        )
        json_handler.setLevel(level)
        root_logger.addHandler(json_handler)
    else:
        # Standard format mode
        config["json"] = False
        if format_str:
            config["format"] = format_str
            basicConfig(level=level, format=format_str)
        elif default_format:
            config["format"] = default_format
            basicConfig(level=level, format=default_format)
        else:
            basicConfig(level=level)

    return config


# =============================================================================
# Graceful Shutdown
# =============================================================================

_shutdown_handlers: list[callable] = []
_shutdown_registered = False
_shutdown_lock = threading.Lock()


def _shutdown_handler(signum=None, frame=None):
    """Internal shutdown handler."""
    import contextlib

    from . import flush

    # Flush all LogXide buffers
    with contextlib.suppress(Exception):
        flush()

    # Call registered handlers
    for handler in _shutdown_handlers:
        with contextlib.suppress(Exception):
            handler()


def register_shutdown_handler(handler: callable) -> None:
    """
    Register a handler to be called during graceful shutdown.

    Args:
        handler: Callable to invoke during shutdown
    """
    global _shutdown_registered

    with _shutdown_lock:
        _shutdown_handlers.append(handler)

        if not _shutdown_registered:
            # Register atexit handler
            atexit.register(_shutdown_handler)

            # Register signal handlers (Unix only)
            try:
                signal.signal(signal.SIGTERM, _shutdown_handler)
                signal.signal(signal.SIGINT, _shutdown_handler)
            except (ValueError, OSError):
                # Might fail in non-main thread or unsupported platform
                pass

            _shutdown_registered = True


def graceful_shutdown() -> None:
    """
    Manually trigger graceful shutdown.

    This flushes all LogXide buffers and calls registered shutdown handlers.
    """
    _shutdown_handler()


# Register default shutdown handler on module import
register_shutdown_handler(lambda: None)  # Ensures flush is registered


# =============================================================================
# Rate Limiting and Sampling
# =============================================================================


class RateLimitedHandler(Handler):
    """
    Handler that limits the rate of log emissions.

    Useful for preventing log flooding in high-traffic scenarios.
    """

    def __init__(
        self,
        wrapped_handler: Handler,
        max_per_second: float = 100.0,
        burst_size: int = 10,
    ):
        """
        Initialize rate-limited handler.

        Args:
            wrapped_handler: Handler to wrap with rate limiting
            max_per_second: Maximum logs per second (default: 100)
            burst_size: Allow burst of this many logs before limiting (default: 10)
        """
        super().__init__()
        self.wrapped_handler = wrapped_handler
        self.max_per_second = max_per_second
        self.burst_size = burst_size
        self._tokens = float(burst_size)
        self._last_update = time.monotonic()
        self._lock = threading.Lock()
        self._dropped_count = 0

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(
            self.burst_size, self._tokens + elapsed * self.max_per_second
        )
        self._last_update = now

    def emit(self, record) -> None:
        """
        Emit a log record if within rate limit.

        Args:
            record: Log record to emit
        """
        with self._lock:
            self._refill_tokens()

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                self.wrapped_handler.emit(record)
            else:
                self._dropped_count += 1

    def get_dropped_count(self) -> int:
        """
        Get the number of dropped log records.

        Returns:
            Number of records dropped due to rate limiting
        """
        with self._lock:
            return self._dropped_count

    def reset_dropped_count(self) -> int:
        """
        Reset and return the dropped count.

        Returns:
            Number of records dropped since last reset
        """
        with self._lock:
            count = self._dropped_count
            self._dropped_count = 0
            return count


class SamplingHandler(Handler):
    """
    Handler that samples logs based on configurable rates.

    Allows different sampling rates for different log levels.
    """

    def __init__(
        self,
        wrapped_handler: Handler,
        sample_rate: float = 1.0,
        level_rates: dict[int, float] | None = None,
    ):
        """
        Initialize sampling handler.

        Args:
            wrapped_handler: Handler to wrap with sampling
            sample_rate: Default sampling rate (0.0 to 1.0, default: 1.0)
            level_rates: Per-level sampling rates {level: rate}
        """
        super().__init__()
        self.wrapped_handler = wrapped_handler
        self.sample_rate = sample_rate
        self.level_rates = level_rates or {}
        self._sampled_count = 0
        self._total_count = 0
        self._lock = threading.Lock()

    def emit(self, record) -> None:
        """
        Emit a log record based on sampling rate.

        Args:
            record: Log record to emit
        """
        import random

        # Get the level from record
        if isinstance(record, dict):
            levelno = record.get("levelno", 0)
        else:
            levelno = getattr(record, "levelno", 0)

        # Determine sample rate for this level
        rate = self.level_rates.get(levelno, self.sample_rate)

        with self._lock:
            self._total_count += 1

            if rate >= 1.0 or random.random() < rate:
                self._sampled_count += 1
                self.wrapped_handler.emit(record)

    def get_stats(self) -> dict[str, int]:
        """
        Get sampling statistics.

        Returns:
            Dictionary with 'sampled' and 'total' counts
        """
        with self._lock:
            return {"sampled": self._sampled_count, "total": self._total_count}


class DuplicateFilter:
    """
    Filter that suppresses duplicate log messages.

    Useful for preventing repeated identical error messages.
    """

    def __init__(
        self,
        timeout: float = 60.0,
        max_duplicates: int = 1,
    ):
        """
        Initialize duplicate filter.

        Args:
            timeout: Time in seconds before allowing duplicate (default: 60)
            max_duplicates: Max times to allow same message in timeout (default: 1)
        """
        self.timeout = timeout
        self.max_duplicates = max_duplicates
        self._seen: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def filter(self, record) -> bool:
        """
        Check if record should be logged.

        Args:
            record: Log record to check

        Returns:
            True if record should be logged, False otherwise
        """
        # Get message from record
        if isinstance(record, dict):
            msg = record.get("msg", "")
            levelno = record.get("levelno", 0)
        else:
            msg = getattr(record, "msg", "")
            levelno = getattr(record, "levelno", 0)

        key = f"{levelno}:{msg}"
        now = time.monotonic()

        with self._lock:
            # Clean old entries
            self._seen = {
                k: v for k, v in self._seen.items() if now - v[0] < self.timeout
            }

            if key in self._seen:
                last_time, count = self._seen[key]
                if count >= self.max_duplicates:
                    return False
                self._seen[key] = (last_time, count + 1)
            else:
                self._seen[key] = (now, 1)

            return True


# =============================================================================
# Context Binding
# =============================================================================


def bind_context(**kwargs) -> None:
    """
    Bind context variables to the current async context.

    These variables will be included in all subsequent log records
    until unbound or the context ends.

    Args:
        **kwargs: Key-value pairs to bind to context

    Example:
        >>> bind_context(request_id="abc123", user_id=42)
        >>> logger.info("Processing request")  # Will include request_id and user_id
    """
    current = _bound_context.get().copy()
    current.update(kwargs)
    _bound_context.set(current)


def unbind_context(*keys) -> None:
    """
    Unbind context variables from the current async context.

    Args:
        *keys: Keys to remove from bound context

    Example:
        >>> unbind_context("request_id", "user_id")
    """
    if not keys:
        _bound_context.set({})
    else:
        current = _bound_context.get().copy()
        for key in keys:
            current.pop(key, None)
        _bound_context.set(current)


def get_bound_context() -> dict[str, Any]:
    """
    Get the currently bound context.

    Returns:
        Copy of the bound context dictionary
    """
    return _bound_context.get().copy()


@contextmanager
def bound_contextvars(**kwargs):
    """
    Context manager for temporarily binding context variables.

    Args:
        **kwargs: Key-value pairs to bind

    Example:
        >>> with bound_contextvars(request_id="abc123"):
        ...     logger.info("Processing")  # Includes request_id
        >>> logger.info("Done")  # No request_id
    """
    token = _bound_context.set({**_bound_context.get(), **kwargs})
    try:
        yield
    finally:
        _bound_context.reset(token)


def with_context(**context_kwargs):
    """
    Decorator that binds context for the duration of a function call.

    Args:
        **context_kwargs: Key-value pairs to bind

    Example:
        >>> @with_context(component="auth")
        ... def authenticate(user_id):
        ...     logger.info("Authenticating", extra={"user_id": user_id})
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with bound_contextvars(**context_kwargs):
                return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with bound_contextvars(**context_kwargs):
                return await func(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


# =============================================================================
# Health Check
# =============================================================================


class LoggingHealthCheck:
    """
    Health check for the logging system.

    Provides methods to check if logging is functioning properly.
    """

    def __init__(self):
        self._last_log_time: float | None = None
        self._log_count = 0
        self._error_count = 0
        self._lock = threading.Lock()

    def record_log(self) -> None:
        """Record that a log was successfully emitted."""
        with self._lock:
            self._last_log_time = time.time()
            self._log_count += 1

    def record_error(self) -> None:
        """Record that a logging error occurred."""
        with self._lock:
            self._error_count += 1

    def get_status(self) -> dict[str, Any]:
        """
        Get the health status of the logging system.

        Returns:
            Dictionary with health status information
        """
        with self._lock:
            return {
                "healthy": self._error_count == 0,
                "last_log_time": self._last_log_time,
                "log_count": self._log_count,
                "error_count": self._error_count,
            }

    def reset(self) -> None:
        """Reset health check counters."""
        with self._lock:
            self._last_log_time = None
            self._log_count = 0
            self._error_count = 0


# Global health check instance
_health_check = LoggingHealthCheck()


def get_logging_health() -> dict[str, Any]:
    """
    Get the health status of the logging system.

    Returns:
        Dictionary with health status information
    """
    return _health_check.get_status()


# =============================================================================
# Production Configuration Presets
# =============================================================================


def configure_production(
    service_name: str,
    environment: str = "production",
    json_output: bool = True,
    level: int = INFO,
) -> None:
    """
    Configure logging for production environment.

    Sets up:
    - JSON or standard format based on json_output
    - Appropriate log level
    - Graceful shutdown handling
    - Service name and environment in log context

    Args:
        service_name: Name of the service (included in logs)
        environment: Environment name (default: "production")
        json_output: Use JSON output format (default: True)
        level: Log level (default: INFO)
    """
    from . import basicConfig, getLogger

    # Configure basic settings
    basicConfig(level=level)

    # Get root logger
    root_logger = getLogger()

    if json_output:
        # Add JSON handler with service info
        handler = JSONHandler(
            include_timestamp=True,
            include_thread_info=True,
            include_process_info=True,
            include_source_info=False,
            extra_fields={
                "service": service_name,
                "environment": environment,
            },
        )
        handler.setLevel(level)
        root_logger.addHandler(handler)

    # Bind service context
    bind_context(service=service_name, environment=environment)

    # Ensure graceful shutdown is registered
    register_shutdown_handler(lambda: None)


def configure_development(
    level: int = DEBUG,
    format_str: str | None = None,
) -> None:
    """
    Configure logging for development environment.

    Sets up:
    - Debug level logging
    - Readable format with colors (if supported)
    - Source information included

    Args:
        level: Log level (default: DEBUG)
        format_str: Custom format string (optional)
    """
    from . import basicConfig

    if format_str is None:
        format_str = (
            "%(asctime)s - %(name)s - %(levelname)-8s - "
            "%(filename)s:%(lineno)d - %(message)s"
        )

    basicConfig(level=level, format=format_str)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # JSON formatting
    "JSONFormatter",
    "JSONHandler",
    # Environment configuration
    "configure_from_env",
    # Graceful shutdown
    "register_shutdown_handler",
    "graceful_shutdown",
    # Rate limiting and sampling
    "RateLimitedHandler",
    "SamplingHandler",
    "DuplicateFilter",
    # Context binding
    "bind_context",
    "unbind_context",
    "get_bound_context",
    "bound_contextvars",
    "with_context",
    # Health check
    "LoggingHealthCheck",
    "get_logging_health",
    # Configuration presets
    "configure_production",
    "configure_development",
]
