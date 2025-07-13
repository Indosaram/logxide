"""
Compatibility handler classes for LogXide.

This module provides handler classes that maintain compatibility with
Python's standard logging module.
"""

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

    def __init__(self, fmt=None, datefmt=None, style='%', validate=True, **kwargs):
        self.fmt = fmt
        self.datefmt = datefmt
        self.style = style
        self.validate = validate
        # Accept and ignore any additional kwargs for compatibility
        self._kwargs = kwargs

    def format(self, record):
        return str(record)


class Handler:
    """Basic handler class - compatible with logging.Handler"""

    def __init__(self):
        self.formatter = None
        self.level = NOTSET

    def handle(self, record):
        pass

    def emit(self, record):
        pass

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
        self.stream = stream


class LoggingManager:
    """Mock logging manager for compatibility"""

    def __init__(self):
        self.disable = 0  # SQLAlchemy checks this attribute