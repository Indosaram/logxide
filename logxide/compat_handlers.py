"""
Compatibility handler classes for LogXide.

This module provides handler classes that maintain compatibility with
Python's standard logging module.
"""

import atexit
import contextlib
import sys

# Define logging level constants
import threading
import time
import traceback

NOTSET = 0
DEBUG = 10
INFO = 20
WARNING = 30
WARN = WARNING  # Alias for WARNING (deprecated but still used)
ERROR = 40
CRITICAL = 50
FATAL = CRITICAL  # Alias for CRITICAL


class NullHandler:
    """A handler that does nothing - compatible with logging.NullHandler"""

    def __init__(self):
        pass

    def handle(self, record):
        pass

    def emit(self, record):
        pass

    def __call__(self, record):
        """Make it callable for logxide compatibility"""
        self.handle(record)


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
            record_dict = record.__dict__ if hasattr(record, '__dict__') else {}
        
        # Ensure 'message' key exists (some formats use it)
        if 'message' not in record_dict:
            record_dict['message'] = record_dict.get('msg', '')
        
        # Add asctime if not present and format string requires it
        if 'asctime' not in record_dict and '%(asctime)' in self.fmt:
            record_dict['asctime'] = self.formatTime(record, self.datefmt)
        
        # Apply format string
        try:
            # Use Python's % formatting with record dict
            s = self.fmt % record_dict
            return s
        except (KeyError, ValueError, TypeError) as e:
            # Fallback to just the message if formatting fails
            return record_dict.get('msg', str(record))

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
    """Basic handler class - compatible with logging.Handler"""

    def __init__(self):
        self.formatter = None
        self.level = NOTSET

    def handle(self, record):
        """
        Handle a log record by checking level and calling emit.
        
        This is a complete override to prevent any stdlib logging.Handler
        methods from being called, which would expect LogRecord objects
        instead of dicts.
        """
        # Check if this handler's level allows this record
        if isinstance(record, dict):
            record_level = record.get('levelno', 0)
        else:
            record_level = getattr(record, 'levelno', 0)
        
        if record_level >= self.level:
            self.emit(record)

    def emit(self, record):
        """
        Emit a log record. Must be overridden by subclasses.
        
        This method should never call any stdlib logging methods.
        """
        pass

    def handleError(self, record):
        # Default error handling - print to stderr
        import traceback

        if sys.stderr:
            sys.stderr.write("--- Logging error ---\n")
            traceback.print_exc(file=sys.stderr)
            sys.stderr.write("Call stack:\n")
            traceback.print_stack(file=sys.stderr)
            sys.stderr.write("--- End of logging error ---\n")

    @property
    def terminator(self):
        return "\n"

    def setFormatter(self, formatter):
        """Set the formatter for this handler"""
        self.formatter = formatter

    def setLevel(self, level):
        """Set the effective level for this handler"""
        self.level = level

    def format(self, record):
        """Format the specified record."""
        if self.formatter:
            return self.formatter.format(record)
        else:
            # Default formatting
            if isinstance(record, dict):
                return record.get("msg", str(record))
            else:
                return getattr(record, "msg", str(record))

    def close(self):
        """
        Tidy up any resources used by the handler.

        This version does nothing - it's up to subclasses to implement
        any cleanup operations.
        """
        pass

    def __call__(self, record):
        """Make it callable for logxide compatibility"""
        self.handle(record)


class StreamHandler(Handler):
    """Stream handler class - compatible with logging.StreamHandler"""

    _class_lock = threading.RLock()  # Class-level lock for _at_exit_shutdown
    _class_shutdown = False  # Class-level shutdown flag

    def __init__(self, stream=None):
        super().__init__()
        if stream is None:
            stream = sys.stderr
        self._stream = stream
        self._shutdown = False  # Instance-level shutdown flag
        self._lock = threading.RLock()  # Instance-level lock

    def _get_stream(self):
        """Get the stream, ensuring it's not closed."""
        if hasattr(self, "_stream"):
            stream = self._stream
            if hasattr(stream, "closed") and not stream.closed:
                return stream
        return None

    @property
    def stream(self):
        return self._get_stream() or sys.stderr

    @stream.setter
    def stream(self, value):
        self._stream = value

    def emit(self, record):
        # Check if we're shutting down (instance or class level)
        if self._shutdown or self._class_shutdown:
            return

        try:
            # Handle different record types from LogXide
            if isinstance(record, dict):
                msg = record.get("msg", str(record))
            elif hasattr(record, "msg"):
                msg = str(record.msg)
            elif hasattr(record, "message"):
                msg = str(record.message)
            else:
                msg = str(record)

            # Apply formatter if available - but only use our own Formatter class
            # to avoid issues with stdlib logging.Formatter expecting LogRecord objects
            if self.formatter:
                # Check if this is our Formatter (from logxide.compat_handlers)
                formatter_module = getattr(self.formatter.__class__, '__module__', '')
                if formatter_module == 'logxide.compat_handlers':
                    # Safe to use our formatter with dict records
                    try:
                        msg = self.formatter.format(record)
                    except (AttributeError, KeyError, TypeError):
                        # If formatting fails, use the original message
                        pass
                # If it's a stdlib formatter, skip it to avoid errors with dict records

            stream = self.stream
            # Check if stream is closed before writing
            if hasattr(stream, "closed") and stream.closed:
                return

            # Thread-safe write
            with self._lock:
                if not self._shutdown and not self._class_shutdown and stream and hasattr(stream, "write"):
                    try:
                        stream.write(msg + self.terminator)
                        self.flush()
                    except (ValueError, OSError):
                        # Stream was closed during operation
                        pass
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)

    def flush(self):
        if self._shutdown or self._class_shutdown:
            return

        with self._lock:
            if self.stream and hasattr(self.stream, "flush"):
                # Check if stream is closed before flushing
                if hasattr(self.stream, "closed") and self.stream.closed:
                    return
                with contextlib.suppress(ValueError, OSError):
                    self.stream.flush()

    def close(self):
        """
        Close the stream.
        """
        with self._lock:
            self._shutdown = True
            self.flush()
            if hasattr(self.stream, "close"):
                with contextlib.suppress(ValueError, OSError):
                    self.stream.close()
        Handler.close(self)

    @classmethod
    def _at_exit_shutdown(cls):
        """Shutdown all handlers at exit."""
        with cls._class_lock:
            cls._class_shutdown = True


class FileHandler(StreamHandler):
    """File handler class - compatible with logging.FileHandler"""

    def __init__(self, filename, mode="a", encoding=None, delay=False):
        # Implement basic file handling
        self.baseFilename = filename
        self.mode = mode
        self.encoding = encoding
        self.delay = delay
        # Open file and keep it open for the handler
        self._file = open(filename, mode, encoding=encoding)  # noqa: SIM115
        super().__init__(stream=self._file)

    def close(self):
        """Close the file."""
        if hasattr(self, "_file") and self._file:
            self._file.close()
            self._file = None
        if hasattr(super(), "close"):
            super().close()  # type: ignore[misc]


class LoggingManager:
    """Mock logging manager for compatibility"""

    def __init__(self):
        self.disable = 0  # SQLAlchemy checks this attribute


# Register shutdown handler
atexit.register(StreamHandler._at_exit_shutdown)
