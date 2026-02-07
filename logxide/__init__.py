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
                f"❌ FATAL: Python Version Mismatch\nCompiled: {compiled_version}, Runtime: {runtime_version}\n"
            )
            sys.exit(1)


_check_python_version()

from . import logxide

__version__ = "0.1.6"

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
from .compat_handlers import NullHandler as _CompatNullHandler
from .handlers import (
    FileHandler,
    StreamHandler,
    RotatingFileHandler,
    HTTPHandler,
    OTLPHandler,
    MemoryHandler,
)
from . import logxide as _logxide_ext

RustFileHandler = _logxide_ext.FileHandler
RustStreamHandler = _logxide_ext.StreamHandler
RustRotatingFileHandler = _logxide_ext.RotatingFileHandler
RustHTTPHandler = _logxide_ext.HTTPHandler
RustOTLPHandler = _logxide_ext.OTLPHandler
RustMemoryHandler = _logxide_ext.MemoryHandler
NullHandler = _CompatNullHandler

from .logger_wrapper import basicConfig, getLogger
from .module_system import _install, logging, uninstall

clear_handlers = logxide.logging.clear_handlers

flush = logxide.logging.flush
set_thread_name = logxide.logging.set_thread_name
PyLogger = logxide.logging.PyLogger
Logger = PyLogger
LogRecord = logxide.logging.LogRecord

if "pytest" not in sys.modules and "PYTEST_CURRENT_TEST" not in os.environ:
    _install()
    sys.modules["logging"] = logging
