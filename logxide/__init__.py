"""
LogXide: High-performance, Rust-powered drop-in replacement for Python's logging module.

LogXide provides a fast, async-capable logging system that maintains full compatibility
with Python's standard logging module while delivering superior performance through
its Rust backend.
"""

import os
import re
import sys
from types import ModuleType


def _check_python_version():
    """
    Check if the compiled extension matches runtime Python version.

    This prevents cryptic import errors when using LogXide compiled for
    a different Python version.
    """
    import glob

    package_dir = os.path.dirname(os.path.abspath(__file__))
    extension_patterns = [
        os.path.join(package_dir, "logxide.*.so"),
        os.path.join(package_dir, "logxide.*.pyd"),
        os.path.join(package_dir, "logxide.*.dylib"),
    ]

    extension_file = None
    for pattern in extension_patterns:
        matches = glob.glob(pattern)
        if matches:
            extension_file = matches[0]
            break

    if not extension_file:
        return

    # Pattern matches: logxide.cpython-314-*.so, logxide.cpython-311-*.pyd, etc.
    version_match = re.search(r"cpython-(\d)(\d+)(?:\d*)", extension_file)

    if version_match:
        major = int(version_match.group(1))
        minor = int(version_match.group(2)[:2])  # e.g., 14 -> 14
        compiled_version = (major, minor)
        runtime_version = sys.version_info[:2]

        if compiled_version != runtime_version:
            sys.stderr.write(
                f"""
═══════════════════════════════════════════════════════════════
❌ FATAL: Python Version Mismatch
═══════════════════════════════════════════════════════════════

LogXide was compiled for Python {compiled_version[0]}.{compiled_version[1]}
but you are running Python {runtime_version[0]}.{runtime_version[1]}

This will cause complete logging failures (0 bytes written, no output).

Solutions:
1. Reinstall LogXide with the correct Python version:
   pip uninstall logxide
   python{runtime_version[0]}.{runtime_version[1]} -m pip install logxide

2. Use the correct Python interpreter:
   python{runtime_version[0]}.{runtime_version[1]} your_script.py

3. Build from source with your Python version:
   git clone https://github.com/Indosaram/logxide
   cd logxide
   pip install maturin
   python{runtime_version[0]}.{runtime_version[1]} -m maturin develop

═══════════════════════════════════════════════════════════════
"""
            )
            sys.exit(1)


_check_python_version()

# Import Rust extension - if this fails, it's a bug
from . import logxide

# Package metadata
__version__ = "0.1.4"
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
    captureWarnings,
    disable,
    getHandlerByName,
    getHandlerNames,
    getLevelName,
    getLevelNamesMapping,
    getLoggerClass,
    getLogRecordFactory,
    makeLogRecord,
    setLoggerClass,
    setLogRecordFactory,
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
    Formatter,
    Handler,
    LoggingManager,
)
from .compat_handlers import (
    NullHandler as _CompatNullHandler,
)

# Import Rust native handlers from the extension module
# We now use the shim handlers by default for better compatibility
from .handlers import FileHandler, StreamHandler, RotatingFileHandler
from . import logxide as _logxide_ext

# Keep raw Rust handlers available if needed
RustFileHandler = _logxide_ext.FileHandler
RustStreamHandler = _logxide_ext.StreamHandler
RustRotatingFileHandler = _logxide_ext.RotatingFileHandler

NullHandler = _CompatNullHandler  # Use compat NullHandler for now
from .logger_wrapper import basicConfig, getLogger
from .module_system import _install, logging, uninstall

# Import clear_handlers from Rust extension
clear_handlers = logxide.logging.clear_handlers

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
set_thread_name = logxide.logging.set_thread_name
PyLogger = logxide.logging.PyLogger
Logger = PyLogger  # Alias for compatibility
LogRecord = logxide.logging.LogRecord
Filter = logging.Filter
LoggerAdapter = logging.LoggerAdapter

# Rust native handler registration functions (internal use)
_register_stream_handler = logxide.logging.register_stream_handler
_register_file_handler = logxide.logging.register_file_handler
_register_null_handler = logxide.logging.register_null_handler
_register_console_handler = logxide.logging.register_console_handler
_register_rotating_file_handler = logxide.logging.register_rotating_file_handler

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
    "RotatingFileHandler",
    "NullHandler",
    "PyLogger",
    "Logger",
    "LogRecord",
    "Filter",
    "LoggerAdapter",
    # Functions
    "getLogger",
    "basicConfig",
    "flush",
    "set_thread_name",
    "clear_handlers",
    "addLevelName",
    "getLevelName",
    "disable",
    "getLoggerClass",
    "setLoggerClass",
    # Sentry integration (optional)
    "SentryHandler",
    "auto_configure_sentry",
    # Newly implemented compatibility functions (Phase 4)
    "captureWarnings",
    "makeLogRecord",
    "getLogRecordFactory",
    "setLogRecordFactory",
    "getLevelNamesMapping",
    "getHandlerByName",
    "getHandlerNames",
]
