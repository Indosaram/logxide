"""
LogXide: High-performance, Rust-powered drop-in replacement for Python's logging module.
"""

import os
import re
import sys


def _check_python_version():
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
    version_match = re.search(r"cpython-(\d)(\d+)(?:\d*)", extension_file)
    if version_match:
        major = int(version_match.group(1))
        minor = int(version_match.group(2)[:2])
        compiled_version = (major, minor)
        runtime_version = sys.version_info[:2]
        if compiled_version != runtime_version:
            sys.stderr.write(
                "\u274c FATAL: Python Version Mismatch\n"
                f"Compiled: {compiled_version},"
                f" Runtime: {runtime_version}\n"
            )
            sys.exit(1)


_check_python_version()

from . import logxide

__version__ = "0.1.13"

from . import logxide as _logxide_ext
from .compat_functions import (
    addLevelName as addLevelName,
)
from .compat_functions import (
    captureWarnings as captureWarnings,
)
from .compat_functions import (
    disable as disable,
)
from .compat_functions import (
    getHandlerByName as getHandlerByName,
)
from .compat_functions import (
    getHandlerNames as getHandlerNames,
)
from .compat_functions import (
    getLevelName as getLevelName,
)
from .compat_functions import (
    getLevelNamesMapping as getLevelNamesMapping,
)
from .compat_functions import (
    getLoggerClass as getLoggerClass,
)
from .compat_functions import (
    getLogRecordFactory as getLogRecordFactory,
)
from .compat_functions import (
    makeLogRecord as makeLogRecord,
)
from .compat_functions import (
    setLoggerClass as setLoggerClass,
)
from .compat_functions import (
    setLogRecordFactory as setLogRecordFactory,
)
from .compat_handlers import (
    CRITICAL as CRITICAL,
)
from .compat_handlers import (
    DEBUG as DEBUG,
)
from .compat_handlers import (
    ERROR as ERROR,
)
from .compat_handlers import (
    FATAL as FATAL,
)
from .compat_handlers import (
    INFO as INFO,
)
from .compat_handlers import (
    NOTSET as NOTSET,
)
from .compat_handlers import (
    WARN as WARN,
)
from .compat_handlers import (
    WARNING as WARNING,
)
from .compat_handlers import (
    Formatter as Formatter,
)
from .compat_handlers import (
    Handler as Handler,
)
from .compat_handlers import (
    LoggerAdapter as LoggerAdapter,
)
from .compat_handlers import (
    LoggingManager as LoggingManager,
)
from .compat_handlers import NullHandler as _CompatNullHandler
from .handlers import (
    FileHandler as FileHandler,
)
from .handlers import (
    HTTPHandler as HTTPHandler,
)
from .handlers import (
    MemoryHandler as MemoryHandler,
)
from .handlers import (
    OTLPHandler as OTLPHandler,
)
from .handlers import (
    RotatingFileHandler as RotatingFileHandler,
)
from .handlers import (
    StreamHandler as StreamHandler,
)

# Rust handlers (direct access)
RustFileHandler = _logxide_ext.FileHandler
RustStreamHandler = _logxide_ext.StreamHandler
RustRotatingFileHandler = _logxide_ext.RotatingFileHandler
RustHTTPHandler = _logxide_ext.HTTPHandler
RustOTLPHandler = _logxide_ext.OTLPHandler
RustMemoryHandler = _logxide_ext.MemoryHandler
NullHandler = _CompatNullHandler

# Rust formatters (direct access)
try:
    ColorFormatter = _logxide_ext.ColorFormatter
    RustFormatter = _logxide_ext.Formatter
except AttributeError:
    # Fallback if not yet built with new formatters
    pass

from .logger_wrapper import (
    basicConfig as basicConfig,
)
from .logger_wrapper import (
    getLogger as getLogger,
)
from .module_system import (
    _install as _install,
)
from .module_system import (
    logging as logging,
)
from .module_system import (
    uninstall as uninstall,
)

clear_handlers = logxide.logging.clear_handlers

flush = logxide.logging.flush
set_thread_name = logxide.logging.set_thread_name
PyLogger = logxide.logging.PyLogger
Logger = PyLogger
LogRecord = logxide.logging.LogRecord

if "pytest" not in sys.modules and "PYTEST_CURRENT_TEST" not in os.environ:
    _install()
    sys.modules["logging"] = logging
