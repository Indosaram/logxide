"""
Module system and installation logic for LogXide.

This module handles the creation of the logging module interface and
the install/uninstall functionality for drop-in replacement.
"""

import builtins
import contextlib
import logging as _std_logging

try:
    from . import logxide
except ImportError:
    # Handle case where Rust extension is not available
    class logxide:  # type: ignore[no-redef]
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
    Formatter,
    Handler,
    LoggingManager,
    NullHandler,
    StreamHandler,
)
from .logger_wrapper import _migrate_existing_loggers, basicConfig, getLogger

# Get references to Rust functions
flush = logxide.logging.flush  # type: ignore[attr-defined]
set_thread_name = logxide.logging.set_thread_name  # type: ignore[attr-defined]
PyLogger = logxide.logging.PyLogger  # type: ignore[attr-defined]


class _LoggingModule:
    """Mock logging module that provides compatibility interface"""

    @staticmethod
    def getLogger(name=None):
        """Return logger compatible with caplog using monkey-patched standard logger"""
        # Ensure _install() has been called
        import logging as std_logging

        if not hasattr(std_logging, "_original_getLogger"):
            _install()

        # Return the monkey-patched standard logger (which works with caplog)
        return std_logging.getLogger(name)

    basicConfig = staticmethod(basicConfig)
    flush = staticmethod(flush)
    set_thread_name = staticmethod(set_thread_name)
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
    BASIC_FORMAT = "%(levelname)s:%(name)s:%(message)s"
    LogRecord = logxide.logging.LogRecord

    class Filter:
        """Basic Filter implementation for compatibility"""

        def __init__(self, name=""):
            self.name = name
            self.nlen = len(name)

        def filter(self, record):
            if self.nlen == 0:
                return True
            return (
                self.nlen <= len(record.name)
                and self.name == record.name[: self.nlen]
                and (record.name[self.nlen] == "." or len(record.name) == self.nlen)
            )

    class LoggerAdapter:
        """Basic LoggerAdapter implementation for compatibility"""

        def __init__(self, logger, extra=None):
            self.logger = logger
            self.extra = extra

        def process(self, msg, kwargs):
            if self.extra:
                if "extra" in kwargs:
                    kwargs["extra"].update(self.extra)
                else:
                    kwargs["extra"] = self.extra
            return msg, kwargs

        def debug(self, msg, *args, **kwargs):
            return self._log_with_extra("debug", msg, *args, **kwargs)

        def info(self, msg, *args, **kwargs):
            return self._log_with_extra("info", msg, *args, **kwargs)

        def warning(self, msg, *args, **kwargs):
            return self._log_with_extra("warning", msg, *args, **kwargs)

        def error(self, msg, *args, **kwargs):
            return self._log_with_extra("error", msg, *args, **kwargs)

        def critical(self, msg, *args, **kwargs):
            return self._log_with_extra("critical", msg, *args, **kwargs)

        def exception(self, msg, *args, **kwargs):
            return self._log_with_extra("exception", msg, *args, **kwargs)

        def log(self, level, msg, *args, **kwargs):
            return self._log_with_extra_level("log", level, msg, *args, **kwargs)

        def _log_with_extra(self, method_name, msg, *args, **kwargs):
            """Handle logging with extra parameter support"""
            # Extra parameter processing is now handled in Rust
            # Call the original logging method with all kwargs (including extra)
            method = getattr(self.logger, method_name)
            return method(msg, *args, **kwargs)

        def _log_with_extra_level(self, method_name, level, msg, *args, **kwargs):
            """Handle log method with level parameter and extra support"""
            # Extra parameter processing is now handled in Rust
            # Call the original logging method with all kwargs (including extra)
            method = getattr(self.logger, method_name)
            return method(level, msg, *args, **kwargs)

        def isEnabledFor(self, level):
            return self.logger.isEnabledFor(level)

    # Add compatibility functions
    addLevelName = staticmethod(addLevelName)
    getLevelName = staticmethod(getLevelName)
    disable = staticmethod(disable)
    getLoggerClass = staticmethod(getLoggerClass)
    setLoggerClass = staticmethod(setLoggerClass)
    LoggingManager = LoggingManager

    # Add missing attributes that uvicorn and other libraries expect
    def __init__(self):
        # Import standard logging to get missing attributes
        import threading
        import weakref

        # Module metadata attributes
        self.__spec__ = _std_logging.__spec__
        self.__path__ = _std_logging.__path__

        # Create mock internal logging state to avoid conflicts
        self._lock = threading.RLock()
        self._handlers = weakref.WeakValueDictionary()
        self._handlerList = []

        # Use standard logging's root logger and utility functions
        self.root = getLogger()
        # Import Rust native handlers from logxide
        from . import logxide as _logxide_ext

        self.FileHandler = _logxide_ext.FileHandler
        self.StreamHandler = _logxide_ext.StreamHandler
        self.RotatingFileHandler = _logxide_ext.RotatingFileHandler
        self.lastResort = NullHandler()
        self.raiseExceptions = True

        # Create mock shutdown function that delegates to standard logging
        def shutdown():
            # Flush all handlers
            logxide.logging.flush()  # type: ignore[attr-defined]  # Flush LogXide's internal buffers
            for handler in _std_logging.root.handlers:
                with contextlib.suppress(builtins.BaseException):
                    handler.flush()

        self.shutdown = shutdown

        # Create mock _checkLevel function that delegates to standard logging
        def _checkLevel(level):
            if isinstance(level, int):
                return level
            if isinstance(level, str):
                s = level.upper()
                if s in _std_logging._nameToLevel:
                    return _std_logging._nameToLevel[s]
            raise ValueError(f"Unknown level: {level}")

        self._checkLevel = _checkLevel

    def debug(self, msg, *args, **kwargs):
        return self._root_log_with_extra("debug", msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        return self._root_log_with_extra("info", msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        return self._root_log_with_extra("warning", msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        return self._root_log_with_extra("error", msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        return self._root_log_with_extra("critical", msg, *args, **kwargs)

    def _root_log_with_extra(self, method_name, msg, *args, **kwargs):
        """Handle root-level logging with extra parameter support"""
        # Extra parameter processing is now handled in Rust
        # Call the original logging method on root with all kwargs (including extra)
        method = getattr(self.root, method_name)
        return method(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        return self._root_log_with_extra("exception", msg, *args, **kwargs)

    def log(self, level, msg, *args, **kwargs):
        return self._root_log_with_extra_level(level, msg, *args, **kwargs)

    def _root_log_with_extra_level(self, level, msg, *args, **kwargs):
        """Handle root-level log method with level parameter and extra support"""
        # Extra parameter processing is now handled in Rust
        # Call the log method on root with all kwargs (including extra)
        return self.root.log(level, msg, *args, **kwargs)

    def fatal(self, msg, *args, **kwargs):
        return self._root_log_with_extra("fatal", msg, *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        return self._root_log_with_extra("warn", msg, *args, **kwargs)

    def captureWarnings(self, capture=True):
        _std_logging.captureWarnings(capture)

    def makeLogRecord(self, dict):
        """Create a LogRecord from a dictionary."""
        # Extract required fields with defaults
        name = dict.get("name", "unknown")
        levelno = dict.get("levelno", 0)
        pathname = dict.get("pathname", "")
        lineno = dict.get("lineno", 0)
        msg = dict.get("msg", "")
        args = dict.get("args")
        exc_info = dict.get("exc_info")
        func_name = dict.get("funcName", dict.get("func_name", ""))
        stack_info = dict.get("stack_info")

        # Create the LogRecord
        record = self.LogRecord(
            name=name,
            levelno=levelno,
            pathname=pathname,
            lineno=lineno,
            msg=msg,
            args=args,
            exc_info=exc_info,
            func_name=func_name,
            stack_info=stack_info,
        )

        # Set additional attributes from the dict
        for key, value in dict.items():
            if not hasattr(record, key):
                setattr(record, key, value)

        return record

    def getLogRecordFactory(self):
        return self.LogRecord

    def setLogRecordFactory(self, factory):
        pass

    def getLevelNamesMapping(self):
        return {
            "CRITICAL": CRITICAL,
            "FATAL": FATAL,
            "ERROR": ERROR,
            "WARNING": WARNING,
            "WARN": WARN,
            "INFO": INFO,
            "DEBUG": DEBUG,
            "NOTSET": NOTSET,
        }

    def getHandlerByName(self, name):
        return None

    def getHandlerNames(self):
        return []

    # Add logging submodules for compatibility
    @property
    def config(self):
        """Provide access to logging.config for compatibility"""
        return _std_logging.config  # type: ignore[attr-defined]

    @property
    def handlers(self):
        """Provide access to logging.handlers for compatibility"""
        return _std_logging.handlers  # type: ignore[attr-defined]


# Create the global logging manager instance
_manager = LoggingManager()

# Create the logging module instance
logging = _LoggingModule()


def _install(sentry=None):
    """
    Private function to install logxide as a drop-in replacement for logging.

    This function monkey-patches the logging module's getLogger function to
    return logxide loggers while keeping all other logging functionality intact.
    This preserves compatibility with uvicorn and other libraries that rely on
    the standard logging module's internal structure.

    Args:
        sentry: Enable/disable Sentry integration (None for auto-detect)

    This is called automatically when importing from logxide.
    """
    import logging as std_logging

    # Store the original getLogger function
    if not hasattr(std_logging, "_original_getLogger"):
        std_logging._original_getLogger = std_logging.getLogger  # type: ignore[attr-defined]

    # Replace getLogger with our version
    def logxide_getLogger(name=None):
        """Get a logxide logger that wraps the standard logger"""
        # Get the standard logger first
        if hasattr(std_logging, "_original_getLogger"):
            std_logger = std_logging._original_getLogger(name)  # type: ignore[attr-defined]
        else:
            # Fallback if _original_getLogger doesn't exist
            std_logger = (
                std_logging.Logger.manager.getLogger(name) if name else std_logging.root
            )

        def _replace_logger_methods(std_logger, name):
            """Replace standard logger methods with LogXide versions."""
            # Create a logxide logger
            logxide_logger = getLogger(name)

            # Store the PyLogger instance as an attribute for later access
            std_logger._logxide_pylogger = logxide_logger

            # Replace the standard logger's methods with logxide versions
            methods_to_replace = [
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

            for method in methods_to_replace:
                if hasattr(logxide_logger, method):
                    logxide_method = getattr(logxide_logger, method)
                    # Always use LogXide only (no double-calling)
                    setattr(std_logger, method, logxide_method)

            # Handle exception method specially - it's error + traceback
            if hasattr(std_logger, "exception"):
                std_logger.exception = logxide_logger.exception

        # Call the function to replace methods
        _replace_logger_methods(std_logger, name)

        # AFTER method replacement, wrap addHandler to sync handlers
        # Get the actual PyLogger instance from the stored attribute
        actual_pylogger = None
        if hasattr(std_logger, "_logxide_pylogger"):
            actual_pylogger = std_logger._logxide_pylogger
        elif hasattr(std_logger.info, "__self__"):
            actual_pylogger = std_logger.info.__self__

        if actual_pylogger is not None:
            original_addHandler = std_logger.addHandler

            def wrapped_addHandler(handler):
                # Add to stdlib logger (for compatibility)
                original_addHandler(handler)

                # Also add to the actual PyLogger that's handling the logging
                try:
                    # Get the current PyLogger instance from the stored attribute
                    current_pylogger = None
                    if hasattr(std_logger, "_logxide_pylogger"):
                        current_pylogger = std_logger._logxide_pylogger
                    elif hasattr(std_logger.info, "__self__"):
                        current_pylogger = std_logger.info.__self__

                    if current_pylogger is not None:
                        current_pylogger.addHandler(handler)
                except ValueError:
                    # Re-raise ValueError for invalid handlers
                    raise
                except Exception:
                    # Silently ignore other errors to avoid breaking compatibility
                    pass

            std_logger.addHandler = wrapped_addHandler

            # Wrap setLevel to sync level between stdlib and PyLogger
            original_setLevel = std_logger.setLevel

            def wrapped_setLevel(level):
                # Set on stdlib logger
                original_setLevel(level)
                # Also set on the actual PyLogger - get from stored attribute
                if hasattr(std_logger, "_logxide_pylogger"):
                    current_pylogger = std_logger._logxide_pylogger
                    current_pylogger.setLevel(level)
                elif hasattr(std_logger.info, "__self__"):
                    current_pylogger = std_logger.info.__self__
                    current_pylogger.setLevel(level)

            std_logger.setLevel = wrapped_setLevel

            # Wrap propagate property to sync between stdlib and PyLogger
            original_propagate = std_logger.propagate

            class PropagateProperty:
                def __get__(self, obj, objtype=None):
                    if hasattr(std_logger, "_logxide_pylogger"):
                        return std_logger._logxide_pylogger.propagate
                    return original_propagate

                def __set__(self, obj, value):
                    # Set on PyLogger
                    if hasattr(std_logger, "_logxide_pylogger"):
                        std_logger._logxide_pylogger.propagate = value
                    # Also set on stdlib logger for compatibility
                    std_logger.__dict__["propagate"] = value

            # Replace propagate with property descriptor
            type(std_logger).propagate = PropagateProperty()

            # Copy existing handlers from std_logger to the actual pylogger
            # This ensures handlers added before LogXide was configured work
            for handler in std_logger.handlers:
                import contextlib

                with contextlib.suppress(ValueError):
                    actual_pylogger.addHandler(handler)

            # Add hasHandlers method if PyLogger has it
            if hasattr(actual_pylogger, "hasHandlers"):

                def wrapped_hasHandlers():
                    # Check both stdlib handlers and PyLogger handlers
                    if std_logger.handlers:
                        return True
                    if hasattr(std_logger, "_logxide_pylogger"):
                        return std_logger._logxide_pylogger.hasHandlers()
                    return False

                std_logger.hasHandlers = wrapped_hasHandlers

        return std_logger

    # Replace the getLogger function
    std_logging.getLogger = logxide_getLogger

    # Also replace basicConfig to use logxide
    if not hasattr(std_logging, "_original_basicConfig"):
        std_logging._original_basicConfig = std_logging.basicConfig  # type: ignore[attr-defined]

    def logxide_basicConfig(**kwargs):
        """Use logxide basicConfig but also call original for compatibility"""
        import contextlib

        with contextlib.suppress(Exception):
            std_logging._original_basicConfig(**kwargs)  # type: ignore[attr-defined]
        return basicConfig(**kwargs)

    std_logging.basicConfig = logxide_basicConfig

    # Also add flush method if it doesn't exist
    if not hasattr(std_logging, "flush"):
        std_logging.flush = flush  # type: ignore[attr-defined]

    # Add set_thread_name method if it doesn't exist
    if not hasattr(std_logging, "set_thread_name"):
        std_logging.set_thread_name = set_thread_name  # type: ignore[attr-defined]

    # Migrate any loggers that might have been created before install()
    _migrate_existing_loggers()

    # Note: Handlers should be added via explicit basicConfig() call
    # We no longer add default handlers automatically to avoid unexpected output
    # This allows users to have full control over logging configuration

    # Auto-configure Sentry integration if available
    _auto_configure_sentry(sentry)


def uninstall():
    """
    Restore the standard logging module.

    This undoes the monkey-patching done by _install().
    """
    import logging as std_logging

    # Restore original getLogger if it exists
    if hasattr(std_logging, "_original_getLogger"):
        std_logging.getLogger = std_logging._original_getLogger  # type: ignore[attr-defined]
        delattr(std_logging, "_original_getLogger")

    # Restore original basicConfig if it exists
    if hasattr(std_logging, "_original_basicConfig"):
        std_logging.basicConfig = std_logging._original_basicConfig  # type: ignore[attr-defined]
        delattr(std_logging, "_original_basicConfig")


def _auto_configure_sentry(enable=None) -> None:
    """
    Automatically configure Sentry integration if available.

    Args:
        enable: Explicitly enable/disable Sentry (None for auto-detect)
    """
    try:
        from .sentry_integration import auto_configure_sentry

        # Try to configure Sentry handler
        sentry_handler = auto_configure_sentry(enable)

        if sentry_handler is not None:
            # Add to root logger
            root_logger = getLogger()
            if hasattr(root_logger, "addHandler"):
                root_logger.addHandler(sentry_handler)

            # Also add to standard root logger for compatibility
            import logging as std_logging

            std_logging.root.addHandler(sentry_handler)  # type: ignore[arg-type]

    except ImportError:
        # Sentry integration module not available (should not happen)
        pass
    except Exception:
        # Any other error in Sentry configuration - fail silently
        # to avoid breaking the application
        pass


""
