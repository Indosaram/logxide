"""
LogXide: High-performance, Rust-powered drop-in replacement for Python's logging module.

LogXide provides a fast, async-capable logging system that maintains full compatibility
with Python's standard logging module while delivering superior performance through
its Rust backend.
"""

import sys
from types import ModuleType
from typing import cast

# Package metadata
__version__ = "0.1.0"
__author__ = "LogXide Team"
__email__ = "logxide@example.com"
__license__ = "MIT"
__description__ = (
    "High-performance, Rust-powered drop-in replacement for Python's logging module"
)
__url__ = "https://github.com/Indosaram/logxide"

# Import from organized modules
from . import logxide
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
from .module_system import install, logging, uninstall

# Make the logging module available as a submodule
sys.modules[__name__ + ".logging"] = cast(ModuleType, logging)

# Re-export important functions and classes from Rust extension
flush = logxide.logging.flush
register_python_handler = logxide.logging.register_python_handler
set_thread_name = logxide.logging.set_thread_name
PyLogger = logxide.logging.PyLogger

__all__ = [
    # Core functionality
    "logging",
    "install",
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
    "captureWarnings",
    "makeLogRecord",
    "getLogRecordFactory",
    "setLogRecordFactory",
    "getLevelNamesMapping",
    "getHandlerByName",
    "getHandlerNames",
]
