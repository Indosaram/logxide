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
register_python_handler = logxide.logging.register_python_handler  # type: ignore[attr-defined]
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
    register_python_handler = staticmethod(register_python_handler)
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
        self.FileHandler = _std_logging.FileHandler
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

    This approach replaces the standard handlers with LogXide handlers,
    ensuring logs are processed once through the Rust backend while
    maintaining full caplog/pytest compatibility.

    Args:
        sentry: Enable/disable Sentry integration (None for auto-detect)

    This is called automatically when importing from logxide.
    """
    import logging as std_logging

    # Store the original getLogger function
    if not hasattr(std_logging, "_original_getLogger"):
        std_logging._original_getLogger = std_logging.getLogger  # type: ignore[attr-defined]

    # Create a LogXide handler that routes logs to Rust backend
    class LogXideHandler(std_logging.Handler):
        """Handler that routes logs to LogXide's Rust backend.
        
        This handler replaces standard StreamHandler for console output,
        routing logs through LogXide's async Rust backend for processing.
        """

        def __init__(self, level=std_logging.NOTSET):
            super().__init__(level)
            self._logxide_loggers = {}

        def emit(self, record):
            """Send log record to LogXide's Rust backend."""
            try:
                # Get or create LogXide logger for this record's logger name
                if record.name not in self._logxide_loggers:
                    self._logxide_loggers[record.name] = getLogger(record.name)

                logxide_logger = self._logxide_loggers[record.name]

                # Map log level to method
                level_to_method = {
                    std_logging.DEBUG: "debug",
                    std_logging.INFO: "info",
                    std_logging.WARNING: "warning",
                    std_logging.ERROR: "error",
                    std_logging.CRITICAL: "critical",
                }

                method_name = level_to_method.get(record.levelno, "info")
                method = getattr(logxide_logger, method_name, None)

                if method:
                    # Format the message using the record's getMessage()
                    msg = record.getMessage()
                    method(msg)
            except Exception:
                # Never let handler errors break the app
                pass

    # Create global LogXide handler instance
    if not hasattr(std_logging, "_logxide_handler"):
        std_logging._logxide_handler = LogXideHandler()  # type: ignore[attr-defined]

    # Replace getLogger - return standard logger but with LogXide handler
    def logxide_getLogger(name=None):
        """Get a logger with LogXide handler for output."""
        # Get the standard logger
        if hasattr(std_logging, "_original_getLogger"):
            logger = std_logging._original_getLogger(name)  # type: ignore[attr-defined]
        else:
            logger = (
                std_logging.Logger.manager.getLogger(name) if name else std_logging.root
            )

        # The LogXide handler is added to root logger, so child loggers inherit it
        return logger

    # Replace the getLogger function
    std_logging.getLogger = logxide_getLogger

    # Add LogXide handler to root logger (all loggers inherit from root)
    logxide_handler = std_logging._logxide_handler  # type: ignore[attr-defined]
    if logxide_handler not in std_logging.root.handlers:
        std_logging.root.addHandler(logxide_handler)

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

    # Set up default StreamHandler for the root logger
    # Get the LogXide root logger directly
    logxide_root = getLogger()

    # Check if LogXide root has handlers, if not add StreamHandler
    if hasattr(logxide_root, "handlers") and not logxide_root.handlers:
        from .compat_handlers import StreamHandler

        handler = StreamHandler()
        if hasattr(logxide_root, "addHandler"):
            logxide_root.addHandler(handler)

    # Also set up the standard root logger
    std_root = std_logging.root
    if not std_root.handlers:
        from .compat_handlers import StreamHandler

        handler = StreamHandler()
        std_root.addHandler(handler)  # type: ignore[arg-type]

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
