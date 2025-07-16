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
        # Ensure install() has been called
        import logging as std_logging

        if not hasattr(std_logging, "_original_getLogger"):
            install()

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
            self.logger.debug(msg, *args, **kwargs)

        def info(self, msg, *args, **kwargs):
            self.logger.info(msg, *args, **kwargs)

        def warning(self, msg, *args, **kwargs):
            self.logger.warning(msg, *args, **kwargs)

        def error(self, msg, *args, **kwargs):
            self.logger.error(msg, *args, **kwargs)

        def critical(self, msg, *args, **kwargs):
            self.logger.critical(msg, *args, **kwargs)

        def exception(self, msg, *args, **kwargs):
            self.logger.exception(msg, *args, **kwargs)

        def log(self, level, msg, *args, **kwargs):
            self.logger.log(level, msg, *args, **kwargs)

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
        self.root.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.root.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.root.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.root.error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.root.critical(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        self.root.exception(msg, *args, **kwargs)

    def log(self, level, msg, *args, **kwargs):
        self.root.log(level, msg, *args, **kwargs)

    def fatal(self, msg, *args, **kwargs):
        self.root.fatal(msg, *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        self.root.warn(msg, *args, **kwargs)

    def captureWarnings(self, capture=True):
        _std_logging.captureWarnings(capture)

    def makeLogRecord(self, dict):
        return self.LogRecord()

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


def install():
    """
    Install logxide as a drop-in replacement for the standard logging module.

    This function monkey-patches the logging module's getLogger function to
    return logxide loggers while keeping all other logging functionality intact.
    This preserves compatibility with uvicorn and other libraries that rely on
    the standard logging module's internal structure.

    Call this function early in your application, before importing any
    third-party libraries that use logging.

    Example:
        import logxide
        logxide.install()

        # Now all libraries will use logxide for logging
        import requests  # requests will use logxide for logging
        import sqlalchemy  # sqlalchemy will use logxide for logging
    """
    import logging as std_logging

    # Store the original getLogger function
    if not hasattr(std_logging, "_original_getLogger"):
        std_logging._original_getLogger = std_logging.getLogger  # type: ignore[attr-defined]

    # Replace getLogger with our version
    def logxide_getLogger(name=None):
        """Get a logxide logger that wraps the standard logger"""
        # Get the standard logger first
        std_logger = std_logging._original_getLogger(name)  # type: ignore[attr-defined]

        # Create a logxide logger
        logxide_logger = getLogger(name)

        # Replace the standard logger's methods with logxide versions
        # But also ensure they still work with caplog by calling the original methods
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
                # Create a wrapper that calls both LogXide and original logging
                original_method = getattr(std_logger, method)
                logxide_method = getattr(logxide_logger, method)

                def create_wrapper(orig_method, logxide_method):
                    def wrapper(*args, **kwargs):
                        # Call the original method first (for caplog compatibility)
                        import contextlib

                        with contextlib.suppress(Exception):
                            orig_method(*args, **kwargs)
                        # Then call LogXide method (for performance)
                        with contextlib.suppress(Exception):
                            logxide_method(*args, **kwargs)

                    return wrapper

                setattr(
                    std_logger, method, create_wrapper(original_method, logxide_method)
                )

        # Handle exception method specially - it's error + traceback
        if hasattr(std_logger, "exception"):

            def exception_wrapper(msg, *args, **kwargs):
                # Use logxide error method for exception logging
                logxide_logger.exception(msg, *args, **kwargs)

            std_logger.exception = exception_wrapper

        # Copy handlers from std_logger to logxide_logger
        # This ensures handlers added to Python logger work with LogXide
        # Only copy callable handlers as LogXide requires handlers to be callable
        if hasattr(logxide_logger, "addHandler"):
            for handler in std_logger.handlers:
                if callable(handler) and handler not in getattr(
                    logxide_logger, "handlers", []
                ):
                    import contextlib

                    with contextlib.suppress(ValueError):
                        logxide_logger.addHandler(handler)

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
        std_root.addHandler(handler)


def uninstall():
    """
    Restore the standard logging module.

    This undoes the monkey-patching done by install().
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


""
