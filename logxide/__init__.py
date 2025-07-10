# Allow `from logxide import logging` to work as a drop-in replacement,
# by creating a pure Python module that forwards to the Rust extension's API.

# Import the Rust extension's `logging` attribute directly (not as a Python submodule)
logging_mod = __import__("logxide.logxide", fromlist=["logging"]).logging

getLogger = logging_mod.getLogger
_rust_basicConfig = logging_mod.basicConfig
flush = logging_mod.flush
set_thread_name = logging_mod.set_thread_name
get_thread_name = logging_mod.get_thread_name
register_python_handler = logging_mod.register_python_handler
PyLogger = logging_mod.PyLogger


def basicConfig(**kwargs):
    """
    Basic configuration for the logging system.

    Supported parameters:
    - level: Set the effective level for the root logger
    - format: Format string for log messages
    - datefmt: Date format string
    """
    # Extract format parameters that need special handling
    format_str = kwargs.pop("format", None)
    datefmt = kwargs.pop("datefmt", None)

    # Build kwargs for Rust basicConfig
    rust_kwargs = {}
    if "level" in kwargs:
        rust_kwargs["level"] = kwargs["level"]
    if format_str is not None:
        rust_kwargs["format"] = format_str
    if datefmt is not None:
        rust_kwargs["datefmt"] = datefmt

    # Call Rust basicConfig with processed parameters
    _rust_basicConfig(rust_kwargs if rust_kwargs else {})


# Define logging level constants (compatible with Python's logging module)
DEBUG = 10
INFO = 20
WARNING = 30
WARN = WARNING  # Alias for WARNING (deprecated but still used)
ERROR = 40
CRITICAL = 50
FATAL = CRITICAL  # Alias for CRITICAL


# Additional classes needed for compatibility with standard logging
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

    def __init__(self, fmt=None, datefmt=None):
        self.fmt = fmt
        self.datefmt = datefmt

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


# Module-level constants and functions for compatibility
NOTSET = 0


def addLevelName(level, levelName):
    """Add a level name - compatibility function"""
    pass


def getLevelName(level):
    """Get level name - compatibility function"""
    level_names = {10: "DEBUG", 20: "INFO", 30: "WARNING", 40: "ERROR", 50: "CRITICAL"}
    return level_names.get(level, f"Level {level}")


def disable(level):
    """Disable logging below the specified level - compatibility function"""
    # For compatibility - not fully implemented
    pass


def getLoggerClass():
    """Get the logger class - compatibility function"""
    return PyLogger


def setLoggerClass(klass):
    """Set the logger class - compatibility function"""
    # For compatibility - not implemented
    pass


class LoggingManager:
    """Mock logging manager for compatibility"""

    def __init__(self):
        self.disable = 0  # SQLAlchemy checks this attribute


class _LoggingModule:
    getLogger = staticmethod(getLogger)
    basicConfig = staticmethod(basicConfig)
    flush = staticmethod(flush)
    set_thread_name = staticmethod(set_thread_name)
    get_thread_name = staticmethod(get_thread_name)
    register_python_handler = staticmethod(register_python_handler)
    PyLogger = PyLogger

    # Add logging level constants
    DEBUG = DEBUG
    INFO = INFO
    WARNING = WARNING
    WARN = WARN
    ERROR = ERROR
    CRITICAL = CRITICAL
    FATAL = FATAL
    NOTSET = NOTSET

    # Add compatibility classes
    NullHandler = NullHandler
    Formatter = Formatter
    Handler = Handler
    StreamHandler = StreamHandler
    Logger = PyLogger  # Standard logging uses Logger class

    # Add compatibility functions
    addLevelName = staticmethod(addLevelName)
    getLevelName = staticmethod(getLevelName)
    disable = staticmethod(disable)
    getLoggerClass = staticmethod(getLoggerClass)
    setLoggerClass = staticmethod(setLoggerClass)
    LoggingManager = LoggingManager


import sys

logging = _LoggingModule()
sys.modules[__name__ + ".logging"] = logging


def install():
    """
    Install logxide as a drop-in replacement for the standard logging module.

    This function monkey-patches sys.modules so that all imports of 'logging'
    will use logxide instead of Python's standard logging module.

    Call this function early in your application, before importing any
    third-party libraries that use logging.

    Example:
        import logxide
        logxide.install()

        # Now all libraries will use logxide
        import requests  # requests will use logxide for logging
        import sqlalchemy  # sqlalchemy will use logxide for logging
    """
    sys.modules["logging"] = logging


def uninstall():
    """
    Restore the standard logging module.

    This undoes the monkey-patching done by install().
    """
    if "logging" in sys.modules and hasattr(sys.modules["logging"], "__name__"):
        # Only remove if it's our module
        if not hasattr(
            sys.modules["logging"], "__file__"
        ):  # Our module doesn't have __file__
            del sys.modules["logging"]


__all__ = ["logging", "install", "uninstall", "LoggingManager"]
