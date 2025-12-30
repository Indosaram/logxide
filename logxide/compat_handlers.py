"""
Compatibility handler classes for LogXide.

This module provides handler classes that maintain compatibility with
Python's standard logging module, but delegates actual logging to
Rust native handlers for maximum performance.
"""

import sys
import time
import traceback

# Import Rust native handler registration functions

# Define logging level constants
NOTSET = 0
DEBUG = 10
INFO = 20
WARNING = 30
WARN = WARNING  # Alias for WARNING (deprecated but still used)
ERROR = 40
CRITICAL = 50
FATAL = CRITICAL  # Alias for CRITICAL


class NullHandler:
    """A handler that does nothing - compatible with logging.NullHandler

    Note: This is a no-op wrapper for compatibility. LogXide ignores all handlers
    and uses internal Rust handlers for performance.
    """

    def __init__(self):
        pass

    def handle(self, record):
        pass

    def emit(self, record):
        pass

    def setLevel(self, level):
        pass

    def setFormatter(self, formatter):
        pass

    def __call__(self, record):
        """Make it callable for logxide compatibility"""
        pass


class Formatter:
    """Enhanced formatter - compatible with logging.Formatter, supports extra fields"""

    def __init__(self, fmt=None, datefmt=None, style="%", validate=True, **kwargs):
        self.fmt = fmt if fmt else "%(message)s"  # Default format if not provided
        self.datefmt = datefmt
        self.style = style
        self.validate = validate
        self._kwargs = kwargs

    def format(self, record):
        """
        Format a log record using the format string.

        This handles both dict records (from Rust) and LogRecord objects.
        """
        # Convert record to dict for formatting
        if isinstance(record, dict):
            record_dict = record.copy()
        else:
            record_dict = record.__dict__ if hasattr(record, "__dict__") else {}

        # Ensure 'message' key exists (some formats use it)
        if "message" not in record_dict:
            record_dict["message"] = record_dict.get("msg", "")

        # Add asctime if not present and format string requires it
        if "asctime" not in record_dict and "%(asctime)" in self.fmt:
            record_dict["asctime"] = self.formatTime(record, self.datefmt)

        # Apply format string
        try:
            # Use Python's % formatting with record dict
            s = self.fmt % record_dict
            return s
        except (KeyError, ValueError, TypeError):
            # Fallback to just the message if formatting fails
            return record_dict.get("msg", str(record))

    def formatTime(self, record, datefmt=None):
        """
        Format the time for a record.

        Args:
            record: LogRecord instance
            datefmt: Date format string (if None, uses default format)

        Returns:
            Formatted time string
        """
        if isinstance(record, dict):
            ct = record.get("created", time.time())
        else:
            ct = getattr(record, "created", time.time())

        if datefmt:
            s = time.strftime(datefmt, time.localtime(ct))
        else:
            t = time.localtime(ct)
            s = time.strftime("%Y-%m-%d %H:%M:%S", t)
            if isinstance(record, dict):
                msecs = record.get("msecs", 0)
            else:
                msecs = getattr(record, "msecs", 0)
            s = f"{s},{int(msecs)}"
        return s

    def formatException(self, ei):
        """
        Format exception information.

        Args:
            ei: Exception info tuple (type, value, traceback)

        Returns:
            Formatted exception string
        """
        import io

        sio = io.StringIO()
        tb = ei[2]
        traceback.print_exception(ei[0], ei[1], tb, None, sio)
        s = sio.getvalue()
        sio.close()
        if s[-1:] == "\n":
            s = s[:-1]
        return s

    def formatStack(self, stack_info):
        """
        Format stack information.

        Args:
            stack_info: Stack info string

        Returns:
            Formatted stack string
        """
        return stack_info


class Handler:
    """Basic handler class - compatible with logging.Handler

    Note: This is a compatibility shim. LogXide uses Rust native handlers
    for actual log processing. Python handlers are not supported for
    performance reasons.
    """

    def __init__(self):
        self.formatter = None
        self.level = NOTSET

    def handle(self, record):
        """Handle a log record - compatibility method only"""
        pass

    def emit(self, record):
        """Emit a log record - must be overridden by subclasses"""
        pass

    def handleError(self, record):
        """Handle errors during emit()"""
        import traceback

        if sys.stderr:
            sys.stderr.write("--- Logging error ---\n")
            traceback.print_exc(file=sys.stderr)
            sys.stderr.write("--- End of logging error ---\n")

    @property
    def terminator(self):
        return "\n"

    def setFormatter(self, formatter):
        """Set the formatter for this handler - not supported in LogXide"""
        self.formatter = formatter
        # Note: Formatter setting is currently ignored by Rust handlers

    def setLevel(self, level):
        """Set the effective level for this handler"""
        self.level = level

    def format(self, record):
        """Format the specified record."""
        if self.formatter:
            return self.formatter.format(record)
        else:
            if isinstance(record, dict):
                return record.get("msg", str(record))
            else:
                return getattr(record, "msg", str(record))

    def close(self):
        """Close the handler - compatibility method only"""
        pass

    def __call__(self, record):
        """Make it callable for logxide compatibility"""
        pass


class StreamHandler(Handler):
    """Stream handler class - compatibility wrapper

    WARNING: LogXide does not support custom Python handlers for performance
    reasons. Handlers are managed internally by Rust. This class exists only
    for API compatibility.

    To configure output, use basicConfig() instead:
        logxide.basicConfig(level=logging.DEBUG, format='%(message)s')
    """

    def __init__(self, stream=None):
        super().__init__()
        if stream is None:
            stream = sys.stderr
        self._stream = stream

    @property
    def stream(self):
        return self._stream

    @stream.setter
    def stream(self, value):
        self._stream = value

    def emit(self, record):
        """No-op: LogXide uses internal Rust handlers"""
        pass

    def flush(self):
        """No-op: LogXide uses internal Rust handlers"""
        pass

    def close(self):
        """No-op: LogXide uses internal Rust handlers"""
        pass

    def setLevel(self, level):
        """No-op: LogXide uses internal Rust handlers"""
        self.level = level


class FileHandler(Handler):
    """File handler class - compatibility wrapper

    WARNING: LogXide does not support custom Python handlers for performance
    reasons. Handlers are managed internally by Rust. This class exists only
    for API compatibility.

    To configure file output, use basicConfig() instead:
        logxide.basicConfig(filename='app.log', level=logging.DEBUG)
    """

    def __init__(self, filename, mode="a", encoding=None, delay=False):
        super().__init__()
        self.baseFilename = filename
        self.mode = mode
        self.encoding = encoding
        self.delay = delay

    def close(self):
        """No-op: LogXide uses internal Rust handlers"""
        pass

    def emit(self, record):
        """No-op: LogXide uses internal Rust handlers"""
        pass


class RotatingFileHandler(Handler):
    """Rotating file handler - compatibility wrapper

    WARNING: LogXide does not support custom Python handlers for performance
    reasons. Handlers are managed internally by Rust. This class exists only
    for API compatibility.
    """

    def __init__(
        self,
        filename,
        mode="a",
        maxBytes=0,
        backupCount=0,
        encoding=None,
        delay=False,
    ):
        super().__init__()
        self.baseFilename = filename
        self.mode = mode
        self.maxBytes = maxBytes
        self.backupCount = backupCount
        self.encoding = encoding
        self.delay = delay

    def doRollover(self):
        """No-op: LogXide uses internal Rust handlers"""
        pass

    def emit(self, record):
        """No-op: LogXide uses internal Rust handlers"""
        pass

    def close(self):
        """No-op: LogXide uses internal Rust handlers"""
        pass


class LoggingManager:
    """Mock logging manager for compatibility"""

    def __init__(self):
        self.disable = 0  # SQLAlchemy checks this attribute


# No shutdown handler needed - Rust handles cleanup
