"""
LogXide: High-performance, Rust-powered drop-in replacement for Python's logging module.

LogXide provides a fast, async-capable logging system that maintains full compatibility
with Python's standard logging module while delivering superior performance through
its Rust backend.
"""

import sys
from types import ModuleType
from typing import TYPE_CHECKING

# Import logxide with fallback for type checking
try:
    from . import logxide
except ImportError:
    # Handle case where Rust extension is not available
    if TYPE_CHECKING:
        from typing import Any

        # Type stubs for the Rust extension
        class RustExtension:
            logging: Any

        logxide = RustExtension()
    else:

        class RustExtension:
            class logging:
                @staticmethod
                def flush():
                    pass

                @staticmethod
                def register_python_handler(handler):
                    pass

                @staticmethod
                def set_thread_name(name):
                    pass

                PyLogger = object
                LogRecord = object

        logxide = RustExtension()

# Package metadata
__version__ = "0.1.2"
__author__ = "LogXide Team"
__email__ = "freedomzero91@gmail.com"
__license__ = "MIT"
__description__ = (
    "High-performance, Rust-powered drop-in replacement for Python's logging module"
)
__url__ = "https://github.com/Indosaram/logxide"

# Import from organized modules
from .compat_functions import (
    addLevelName,
    disable,
    getLevelName,
    getLoggerClass,
    setLoggerClass,
)
from .compat_handlers import (
    CRITICAL,
    DEBUG,
    ERROR,
    FATAL,
    INFO,
    NOTSET,
    WARN,
    WARNING,
    FileHandler,
    Formatter,
    Handler,
    LoggingManager,
    NullHandler,
    StreamHandler,
)
from .logger_wrapper import basicConfig, getLogger
from .module_system import _install, logging, uninstall

# Optional Sentry integration (imported lazily to avoid dependency issues)
try:
    from .sentry_integration import SentryHandler, auto_configure_sentry

    _sentry_available = True
except ImportError:
    _sentry_available = False
    SentryHandler = None
    auto_configure_sentry = None


class _LoggingModule(ModuleType):
    """
    Wrapper for the logging module that automatically calls install() when imported.
    """

    def __init__(self, wrapped):
        self._wrapped = wrapped
        self._installed = False
        super().__init__("logxide.logging")

    def __getattr__(self, name):
        # Automatically install logxide when logging module is accessed
        if not self._installed:
            _install()
            self._installed = True
        return getattr(self._wrapped, name)

    def __dir__(self):
        return dir(self._wrapped)


# Create wrapped logging module
_logging_module = _LoggingModule(logging)

# Make the logging module available as a submodule
sys.modules[__name__ + ".logging"] = _logging_module

# Replace the logging reference with the wrapped module
logging = _logging_module

# Note: Auto-install is available when logging module is accessed
# This maintains caplog compatibility while providing LogXide enhancement on demand

# Re-export important functions and classes from Rust extension
flush = logxide.logging.flush
register_python_handler = logxide.logging.register_python_handler
set_thread_name = logxide.logging.set_thread_name
PyLogger = logxide.logging.PyLogger
Logger = PyLogger  # Alias for compatibility
LogRecord = logxide.logging.LogRecord
Filter = logging.Filter
LoggerAdapter = logging.LoggerAdapter

__all__ = [
    # Core functionality
    "logging",
    "uninstall",
    "LoggingManager",
    # Version and metadata
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__description__",
    "__url__",
    # Logging levels (for convenience)
    "DEBUG",
    "INFO",
    "WARNING",
    "WARN",
    "ERROR",
    "CRITICAL",
    "FATAL",
    "NOTSET",
    # Classes
    "NullHandler",
    "Formatter",
    "Handler",
    "StreamHandler",
    "FileHandler",
    "PyLogger",
    "Logger",
    "LogRecord",
    "Filter",
    "LoggerAdapter",
    # Functions
    "getLogger",
    "basicConfig",
    "flush",
    "register_python_handler",
    "set_thread_name",
    "addLevelName",
    "getLevelName",
    "disable",
    "getLoggerClass",
    "setLoggerClass",
    # Sentry integration (optional)
    "SentryHandler",
    "auto_configure_sentry",
    # TODO: Implement these functions for full compatibility
    # "captureWarnings",
    # "makeLogRecord",
    # "getLogRecordFactory",
    # "setLogRecordFactory",
    # "getLevelNamesMapping",
    # "getHandlerByName",
    # "getHandlerNames",
]
