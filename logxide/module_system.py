"""
Module system and installation logic for LogXide.
"""

import builtins
import contextlib
import logging as _std_logging
import types
import threading
import weakref
import sys
import os

try:
    from . import logxide
except ImportError:

    class logxide:
        class logging:
            @staticmethod
            def getLogger(name=None):
                return object()

            @staticmethod
            def basicConfig(**kwargs):
                pass

            @staticmethod
            def flush():
                pass

            @staticmethod
            def set_thread_name(name):
                pass

            PyLogger = object
            LogRecord = object


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
    BASIC_FORMAT,
    CRITICAL,
    DEBUG,
    ERROR,
    FATAL,
    Filter,
    INFO,
    LogRecord as PyLogRecord,
    LoggingManager,
    NOTSET,
    PercentStyle,
    StrFormatStyle,
    StringTemplateStyle,
    WARN,
    WARNING,
    Formatter,
    Handler,
    NullHandler,
    _STYLES,
)
from .compat_handlers import StreamHandler as _StreamHandler
from .logger_wrapper import _migrate_existing_loggers, basicConfig, getLogger

# Get references to Rust functions
flush_fn = logxide.logging.flush
set_thread_name_fn = logxide.logging.set_thread_name
PyLogger = logxide.logging.PyLogger


class _LoggingModule(types.ModuleType):
    """
    Compatibility module that mirrors the standard logging module interface.
    """

    def __init__(self):
        super().__init__("logging")
        (
            self.CRITICAL,
            self.DEBUG,
            self.INFO,
            self.NOTSET,
            self.WARN,
            self.WARNING,
            self.ERROR,
            self.FATAL,
        ) = CRITICAL, DEBUG, INFO, NOTSET, WARN, WARNING, ERROR, FATAL

        (
            self.NullHandler,
            self.Formatter,
            self.Handler,
            self.StreamHandler,
            self.Logger,
            self.LogRecord,
            self.Filter,
        ) = (
            NullHandler,
            Formatter,
            Handler,
            _StreamHandler,
            PyLogger,
            PyLogRecord,
            Filter,
        )

        self.PercentStyle = PercentStyle
        self.StrFormatStyle = StrFormatStyle
        self.StringTemplateStyle = StringTemplateStyle
        self._STYLES = _STYLES
        self.BASIC_FORMAT = BASIC_FORMAT

        self._lock, self._handlers, self._handlerList = (
            threading.RLock(),
            weakref.WeakValueDictionary(),
            [],
        )
        self.root = _std_logging.root

        from . import logxide as _ext

        self.FileHandler = _ext.FileHandler
        self.RotatingFileHandler = _ext.RotatingFileHandler
        self.BufferedHTTPHandler = _ext.BufferedHTTPHandler
        self.lastResort, self.raiseExceptions = _std_logging.lastResort, True

        import logging.config, logging.handlers

        self.config, self.handlers = logging.config, logging.handlers

    def getLogger(self, name=None):
        if not hasattr(_std_logging, "_original_getLogger"):
            _install()
        # Return the patched logger from standard logging
        return _std_logging.getLogger(name)

    def basicConfig(self, **kwargs):
        return basicConfig(**kwargs)

    def flush(self):
        return flush_fn()

    def set_thread_name(self, name):
        return set_thread_name_fn(name)

    addLevelName = staticmethod(addLevelName)
    getLevelName = staticmethod(getLevelName)
    disable = staticmethod(disable)
    getLoggerClass = staticmethod(getLoggerClass)
    setLoggerClass = staticmethod(setLoggerClass)
    captureWarnings = staticmethod(captureWarnings)
    makeLogRecord = staticmethod(makeLogRecord)
    getLogRecordFactory = staticmethod(getLogRecordFactory)
    setLogRecordFactory = staticmethod(setLogRecordFactory)
    getLevelNamesMapping = staticmethod(getLevelNamesMapping)
    getHandlerByName = staticmethod(getHandlerByName)
    getHandlerNames = staticmethod(getHandlerNames)

    def debug(self, msg, *args, **kwargs):
        self.getLogger().debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.getLogger().info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.getLogger().warning(msg, *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        self.getLogger().warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.getLogger().error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.getLogger().critical(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        self.getLogger().exception(msg, *args, **kwargs)

    def log(self, level, msg, *args, **kwargs):
        self.getLogger().log(level, msg, *args, **kwargs)

    def fatal(self, msg, *args, **kwargs):
        self.getLogger().critical(msg, *args, **kwargs)

    def shutdown(self):
        """Cleanly shutdown the logging system."""
        flush_fn()
        for h in _std_logging.root.handlers:
            with contextlib.suppress(builtins.BaseException):
                h.flush()


# Create the singleton instance
logging = _LoggingModule()


def _install(sentry=None):
    """
    Install LogXide patches into the standard logging module.
    """
    import logging as std_logging

    if hasattr(std_logging, "_logxide_installed"):
        return
    std_logging._logxide_installed = True

    if not hasattr(std_logging, "_original_getLogger"):
        std_logging._original_getLogger = std_logging.getLogger

    def logxide_getLogger(name=None):
        std_logger = std_logging._original_getLogger(name)
        if (
            "pytest" in sys.modules
            and name
            and (name.startswith("_pytest") or name.startswith("pytest"))
        ):
            return std_logger

        if hasattr(std_logger, "_logxide_pylogger"):
            return std_logger

        logxide_logger = getLogger(name)
        std_logger._logxide_pylogger = logxide_logger

        methods = [
            "debug",
            "info",
            "warning",
            "error",
            "critical",
            "exception",
            "log",
            "fatal",
            "warn",
        ]
        for m in methods:
            if hasattr(logxide_logger, m):
                setattr(std_logger, m, getattr(logxide_logger, m))

        original_setLevel = std_logger.setLevel

        def wrapped_setLevel(level):
            original_setLevel(level)
            target = getattr(std_logger, "_logxide_pylogger", logxide_logger)
            if hasattr(target, "setLevel"):
                target.setLevel(level)

        std_logger.setLevel = wrapped_setLevel

        original_add = std_logger.addHandler

        def wrapped_add(hdlr):
            original_add(hdlr)
            target = getattr(std_logger, "_logxide_pylogger", logxide_logger)
            if hasattr(hdlr, "_inner"):
                target.addHandler(hdlr._inner)
            else:
                try:
                    target.addHandler(hdlr)
                except Exception:
                    pass

        std_logger.addHandler = wrapped_add

        return std_logger

    std_logging.getLogger = logxide_getLogger

    if not hasattr(std_logging, "_original_basicConfig"):
        std_logging._original_basicConfig = std_logging.basicConfig

    def logxide_basicConfig(**kwargs):
        with contextlib.suppress(Exception):
            std_logging._original_basicConfig(**kwargs)
        return basicConfig(**kwargs)

    std_logging.basicConfig = logxide_basicConfig

    if not hasattr(std_logging, "flush"):
        std_logging.flush = flush_fn
    if not hasattr(std_logging, "set_thread_name"):
        std_logging.set_thread_name = set_thread_name_fn

    _migrate_existing_loggers()
    # Sentry auto-config disabled for build stability
    # _auto_configure_sentry(sentry)


def uninstall():
    import logging as std_logging

    if hasattr(std_logging, "_original_getLogger"):
        std_logging.getLogger = std_logging._original_getLogger
        delattr(std_logging, "_original_getLogger")
    if hasattr(std_logging, "_original_basicConfig"):
        std_logging.basicConfig = std_logging._original_basicConfig
        delattr(std_logging, "_original_basicConfig")
    if hasattr(std_logging, "_logxide_installed"):
        delattr(std_logging, "_logxide_installed")
