"""
Compatibility handlers for LogXide.
"""

import contextlib
import logging
import logging.handlers
import sys

from . import logxide


def _translatable(fmt):
    """Decide whether a Formatter can be rendered by the native Rust formatter.

    Returns (ok, fmt_str, datefmt). ok is False for Formatter subclasses that
    override format(), and for non-%(...) styles ({ or $), which fall back to
    Python dispatch. Accepts BOTH stdlib logging.Formatter/PercentStyle and
    logxide.compat_handlers variants by identity.
    """
    if fmt is None:
        return (True, None, None)

    from . import compat_handlers as _compat

    allowed_format: set[object] = {_compat.Formatter.format}
    allowed_style: set[object] = {_compat.PercentStyle}
    with contextlib.suppress(AttributeError):
        allowed_format.add(logging.Formatter.format)
    with contextlib.suppress(AttributeError):
        allowed_style.add(logging.PercentStyle)

    if type(fmt).format not in allowed_format:
        return (False, None, None)

    style = getattr(fmt, "_style", None)
    if style is not None:
        # stdlib-shaped Formatter: _style is a PercentStyle/StrFormatStyle/... object.
        if type(style) not in allowed_style:
            return (False, None, None)
        fmt_str = (
            getattr(fmt, "_fmt", None) or getattr(style, "_fmt", None) or "%(message)s"
        )
    else:
        # compat_handlers.Formatter: .style is the "%"/"{"/"$" character.
        if getattr(fmt, "style", "%") != "%":
            return (False, None, None)
        fmt_str = (
            getattr(fmt, "fmt", None) or getattr(fmt, "_fmt", None) or "%(message)s"
        )

    return (True, fmt_str, getattr(fmt, "datefmt", None))


def _prepare_record_for_rust(record, native=False):
    # Rust expects an instance of the logxide.logging.LogRecord pyclass.
    # We construct a native Rust-backed LogRecord and populate its fields.

    # Pre-parse exc_info to string if present
    exc_info_str = None
    if (
        record.exc_info
        and isinstance(record.exc_info, tuple)
        and len(record.exc_info) == 3
    ):
        import io
        import traceback

        sio = io.StringIO()
        traceback.print_exception(
            record.exc_info[0], record.exc_info[1], record.exc_info[2], None, sio
        )
        exc_info_str = sio.getvalue()
        sio.close()
        if exc_info_str.endswith("\n"):
            exc_info_str = exc_info_str[:-1]

    func_name = getattr(record, "funcName", "") or getattr(record, "func_name", "")

    # Native fast path forwards the RAW template + original args so the Rust formatter
    # renders %(message)s / %(asctime)s / extras. The pre-format path already set
    # record.msg = self.format(record) and record.args = None before calling us.
    # Mirror stdlib's `if self.args:` guard so an empty tuple is not passed as args
    # (which would attempt `template % ()`).
    native_args = record.args if (native and record.args) else None

    rust_record = logxide.logging.LogRecord(
        record.name,
        record.levelno,
        record.pathname or "",
        record.lineno or 0,
        str(record.msg),
        native_args,
        exc_info_str,
        func_name,
        getattr(record, "stack_info", None),
    )

    # Populate other metadata fields
    rust_record.created = getattr(record, "created", 0.0)
    rust_record.msecs = getattr(record, "msecs", 0.0)
    rust_record.relative_created = getattr(record, "relativeCreated", 0.0)
    rust_record.thread = getattr(record, "thread", 0)
    rust_record.thread_name = getattr(record, "threadName", "")
    rust_record.process = getattr(record, "process", 0)
    rust_record.process_name = getattr(record, "processName", "")
    rust_record.levelname = getattr(record, "levelname", "")

    # Extract extra attributes to the Rust LogRecord's extra dictionary
    standard_fields = {
        "name",
        "levelno",
        "levelname",
        "pathname",
        "filename",
        "module",
        "lineno",
        "funcName",
        "func_name",
        "created",
        "msecs",
        "relativeCreated",
        "relative_created",
        "thread",
        "threadName",
        "thread_name",
        "process",
        "processName",
        "process_name",
        "msg",
        "message",
        "args",
        "exc_info",
        "exc_text",
        "stack_info",
        "task_name",
    }
    for key, value in record.__dict__.items():
        if key not in standard_fields:
            setattr(rust_record, key, value)

    return rust_record


class FileHandler(logging.FileHandler):
    def __init__(self, filename, mode="a", encoding=None, delay=False, errors=None):
        # Initialize inner handler first (before parent creates file handle)
        self._inner = logxide.FileHandler(filename)
        self._native = True
        super().__init__(filename, mode, encoding, delay, errors)
        # Close parent's file handle since we use Rust handler
        if hasattr(self, "stream") and self.stream:
            self.stream.close()
            self.stream = None
        self._recompute_native()

    def _recompute_native(self):
        ok, fmt_str, datefmt = _translatable(self.formatter)
        if ok and not self.filters:
            self._inner.setFormatterSpec(fmt_str, datefmt)
            self._native = True
        else:
            self._inner.setPythonDispatch()
            self._native = False

    def setLevel(self, level):
        super().setLevel(level)
        self._inner.setLevel(level)

    def setFormatter(self, fmt):
        super().setFormatter(fmt)
        self._recompute_native()

    def addFilter(self, filter):
        super().addFilter(filter)
        self._recompute_native()

    def removeFilter(self, filter):
        super().removeFilter(filter)
        self._recompute_native()

    def emit(self, record):
        try:
            if self._native:
                self._inner.emit(_prepare_record_for_rust(record, native=True))
            else:
                if self.formatter:
                    record.msg = self.format(record)
                    record.args = None
                self._inner.emit(_prepare_record_for_rust(record))
        except Exception:
            self.handleError(record)

    def setFlushLevel(self, level):
        """
        Set the flush level. Records at or above this level trigger immediate flush.
        Default is ERROR (40).
        """
        self._inner.setFlushLevel(level)

    def getFlushLevel(self):
        """
        Get the current flush level.
        """
        return self._inner.getFlushLevel()

    def setErrorCallback(self, callback):
        """
        Set error callback for write failures.
        """
        self._inner.setErrorCallback(callback)

    def flush(self):
        """Flush the handler."""
        self._inner.flush()


class StreamHandler(logging.StreamHandler):
    def __init__(self, stream=None):
        target = "stdout" if stream is sys.stdout else "stderr"
        self._inner = logxide.StreamHandler(target)
        self._native = True
        super().__init__(stream)
        self._recompute_native()

    def _recompute_native(self):
        ok, fmt_str, datefmt = _translatable(self.formatter)
        if ok and not self.filters:
            self._inner.setFormatterSpec(fmt_str, datefmt)
            self._native = True
        else:
            self._inner.setPythonDispatch()
            self._native = False

    def setLevel(self, level):
        super().setLevel(level)
        self._inner.setLevel(level)

    def setFormatter(self, fmt):
        super().setFormatter(fmt)
        self._recompute_native()

    def addFilter(self, filter):
        super().addFilter(filter)
        self._recompute_native()

    def removeFilter(self, filter):
        super().removeFilter(filter)
        self._recompute_native()

    def emit(self, record):
        try:
            if self._native:
                self._inner.emit(_prepare_record_for_rust(record, native=True))
            else:
                if self.formatter:
                    record.msg = self.format(record)
                    record.args = None
                self._inner.emit(_prepare_record_for_rust(record))
        except Exception:
            self.handleError(record)

    def setErrorCallback(self, callback):
        """
        Set error callback for write failures.
        """
        self._inner.setErrorCallback(callback)


class RotatingFileHandler(logging.handlers.RotatingFileHandler):
    def __init__(
        self,
        filename,
        mode="a",
        maxBytes=0,
        backupCount=0,
        encoding=None,
        delay=False,
        errors=None,
    ):
        # Initialize inner handler first (before parent creates file handle)
        self._inner = logxide.RotatingFileHandler(filename, maxBytes, backupCount)
        self._native = True
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
        # Close parent's file handle since we use Rust handler
        if hasattr(self, "stream") and self.stream:
            self.stream.close()
            self.stream = None
        self._recompute_native()

    def _recompute_native(self):
        ok, fmt_str, datefmt = _translatable(self.formatter)
        if ok and not self.filters:
            self._inner.setFormatterSpec(fmt_str, datefmt)
            self._native = True
        else:
            self._inner.setPythonDispatch()
            self._native = False

    def setLevel(self, level):
        super().setLevel(level)
        self._inner.setLevel(level)

    def setFormatter(self, fmt):
        super().setFormatter(fmt)
        self._recompute_native()

    def addFilter(self, filter):
        super().addFilter(filter)
        self._recompute_native()

    def removeFilter(self, filter):
        super().removeFilter(filter)
        self._recompute_native()

    def emit(self, record):
        try:
            if self._native:
                self._inner.emit(_prepare_record_for_rust(record, native=True))
            else:
                if self.formatter:
                    record.msg = self.format(record)
                    record.args = None
                self._inner.emit(_prepare_record_for_rust(record))
        except Exception:
            self.handleError(record)

    def setFlushLevel(self, level):
        """
        Set the flush level. Records at or above this level trigger immediate flush.
        Default is ERROR (40).
        """
        self._inner.setFlushLevel(level)

    def getFlushLevel(self):
        """
        Get the current flush level.
        """
        return self._inner.getFlushLevel()

    def setErrorCallback(self, callback):
        """
        Set error callback for write failures.
        """
        self._inner.setErrorCallback(callback)

    def flush(self):
        """Flush the handler."""
        self._inner.flush()


class HTTPHandler(logging.Handler):
    """
    High-performance HTTP handler with batching and background transmission.

    Args:
        url: HTTP endpoint URL
        headers: HTTP headers dict (e.g., {"Authorization": "Bearer token"})
        capacity: Max buffer capacity (default: 10000)
        batch_size: Records per batch (default: 1000)
        flush_interval: Seconds between auto-flush (default: 30)
        global_context: Dict of fields added to every record
        transform_callback: Callable(records) -> transformed_records for custom JSON
        context_provider: Callable() -> dict for dynamic context per batch
        error_callback: Callable(error_msg) for HTTP failure handling
    """

    def __init__(
        self,
        url,
        headers=None,
        capacity=10000,
        batch_size=1000,
        flush_interval=30,
        global_context=None,
        transform_callback=None,
        context_provider=None,
        error_callback=None,
        overflow="block",
    ):
        super().__init__()
        self._inner = logxide.HTTPHandler(
            url,
            headers=headers,
            capacity=capacity,
            batch_size=batch_size,
            flush_interval=flush_interval,
            global_context=global_context,
            transform_callback=transform_callback,
            context_provider=context_provider,
            error_callback=error_callback,
            overflow=overflow,
        )

    def setLevel(self, level):
        super().setLevel(level)
        self._inner.setLevel(level)

    def emit(self, record):
        try:
            if self.formatter:
                record.msg = self.format(record)
                record.args = None
            rust_record = _prepare_record_for_rust(record)
            self._inner.emit(rust_record)
        except Exception:
            self.handleError(record)

    def flush(self):
        self._inner.flush()

    def close(self):
        self._inner.shutdown()
        super().close()

    def get_metrics(self):
        """
        Return delivery accounting for this handler.

        Keys: emitted, sink_acknowledged, queue_dropped, delivery_failed, in_flight.
        """
        return self._inner.get_metrics()

    def setFlushLevel(self, level):
        """
        Set the flush level. Records at or above this level trigger immediate flush.
        Default is ERROR (40).

        Args:
            level: Log level (e.g., logging.ERROR, logging.CRITICAL)
        """
        self._inner.setFlushLevel(level)

    def getFlushLevel(self):
        """
        Get the current flush level.

        Returns:
            int: Current flush level (e.g., 40 for ERROR)
        """
        return self._inner.getFlushLevel()


class OTLPHandler(logging.Handler):
    """
    High-performance OTLP (OpenTelemetry) handler for log export.

    Args:
        url: OTLP endpoint URL (e.g., http://localhost:4318/v1/logs)
        service_name: Service name for OTLP logs
        headers: Optional HTTP headers dict
    """

    def __init__(
        self,
        url,
        service_name,
        headers=None,
        overflow="block",
    ):
        super().__init__()
        self._inner = logxide.OTLPHandler(
            url=url, service_name=service_name, headers=headers, overflow=overflow
        )

    def setLevel(self, level):
        super().setLevel(level)
        self._inner.setLevel(level)

    def emit(self, record):
        try:
            if self.formatter:
                record.msg = self.format(record)
                record.args = None
            rust_record = _prepare_record_for_rust(record)
            self._inner.emit(rust_record)
        except Exception:
            self.handleError(record)

    def flush(self):
        self._inner.flush()

    def close(self):
        self._inner.shutdown()
        super().close()

    def get_metrics(self):
        """
        Return delivery accounting for this handler.

        Keys: emitted, sink_acknowledged, queue_dropped, delivery_failed, in_flight.
        """
        return self._inner.get_metrics()


class MemoryHandler(logging.Handler):
    """
    High-performance memory handler for testing and log capture.
    Stores records in Rust native memory for maximum performance.

    Provides pytest caplog-compatible properties:
    - `.records`: List of LogRecord objects
    - `.text`: All messages joined with newlines
    - `.record_tuples`: List of (logger_name, level, message) tuples
    """

    def __init__(self):
        super().__init__()
        self._inner = logxide.MemoryHandler()

    def setLevel(self, level):
        super().setLevel(level)
        self._inner.setLevel(level)

    def emit(self, record):
        try:
            # MemoryHandler is always native: forward raw; caplog reads _inner.
            self._inner.emit(_prepare_record_for_rust(record, native=True))
        except Exception:
            self.handleError(record)

    def get_records(self):
        """Returns all captured records as a list.

        Deprecated: use .records property.
        """
        return self._inner.records

    @property
    def records(self):
        """
        All captured log records.

        Returns:
            List of LogRecord objects.
        """
        return self._inner.records

    @property
    def text(self):
        """
        All captured log messages as a single newline-separated string.

        Compatible with pytest caplog.text.

        Returns:
            str: All messages joined with newlines.
        """
        return self._inner.text

    @property
    def record_tuples(self):
        """
        Captured records as tuples.

        Compatible with pytest caplog.record_tuples.

        Returns:
            List of (logger_name, level_number, message) tuples.
        """
        return self._inner.record_tuples

    def clear(self):
        """Clear all captured records."""
        self._inner.clear()

    def flush(self):
        pass

    def close(self):
        super().close()
