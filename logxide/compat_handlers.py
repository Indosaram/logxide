"""
Compatibility handler classes for LogXide.

This module provides handler classes that maintain compatibility with
Python's standard logging module.
"""

import sys

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
    """A handler that does nothing - compatible with logging.NullHandler"""

    def __init__(self):
        pass

    def handle(self, record):
        pass

    def emit(self, record):
        pass

    def __call__(self, record):
        """Make it callable for logxide compatibility"""
        pass


class Formatter:
    """Basic formatter class - compatible with logging.Formatter"""

    def __init__(self, fmt=None, datefmt=None, style="%", validate=True, **kwargs):
        self.fmt = fmt if fmt else "%(message)s"  # Default format if not provided
        self.datefmt = datefmt
        self.style = style
        self.validate = validate
        self._kwargs = kwargs

    def format(self, record):
        # Use record.__dict__ for string formatting
        # This assumes LogRecord exposes attributes via __dict__
        s = self.fmt % record.__dict__
        return s


class Handler:
    """Basic handler class - compatible with logging.Handler"""

    def __init__(self):
        self.formatter = None
        self.level = NOTSET

    def handle(self, record):
        self.emit(record)

    def emit(self, record):
        # This method should be overridden by subclasses
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

    def __call__(self, record):
        """Make it callable for logxide compatibility"""
        pass


class StreamHandler(Handler):
    """Stream handler class - compatible with logging.StreamHandler"""

    def __init__(self, stream=None):
        super().__init__()
        if stream is None:
            stream = sys.stderr
        self.stream = stream

    def emit(self, record):
        try:
            msg = self.formatter.format(record) if self.formatter else str(record.msg)
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)

    def flush(self):
        if self.stream and hasattr(self.stream, "flush"):
            self.stream.flush()


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
