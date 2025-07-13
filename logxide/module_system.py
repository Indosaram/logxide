"""
Module system and installation logic for LogXide.

This module handles the creation of the logging module interface and
the install/uninstall functionality for drop-in replacement.
"""

import sys
import logging as _std_logging
from types import ModuleType
from typing import cast

from .logger_wrapper import getLogger, basicConfig, _migrate_existing_loggers
from .compat_handlers import (
    NullHandler, Formatter, Handler, StreamHandler, LoggingManager,
    DEBUG, INFO, WARNING, WARN, ERROR, CRITICAL, FATAL, NOTSET
)
from .compat_functions import addLevelName, getLevelName, disable, getLoggerClass, setLoggerClass
from . import logxide


# Get references to Rust functions
flush = logxide.logging.flush
register_python_handler = logxide.logging.register_python_handler
set_thread_name = logxide.logging.set_thread_name
PyLogger = logxide.logging.PyLogger


class _LoggingModule:
    """Mock logging module that provides compatibility interface"""
    
    getLogger = staticmethod(getLogger)
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
        self.root = _std_logging.root
        self.FileHandler = _std_logging.FileHandler
        
        # Create mock shutdown function that delegates to standard logging
        def mock_shutdown():
            try:
                _std_logging.shutdown()
            except:
                pass
        self.shutdown = mock_shutdown
        
        # Create mock _checkLevel function that delegates to standard logging
        def mock_checkLevel(level):
            try:
                return _std_logging._checkLevel(level)
            except:
                return level
        self._checkLevel = mock_checkLevel
    
    # Add logging submodules for compatibility
    @property
    def config(self):
        """Provide access to logging.config for compatibility"""
        return _std_logging.config
    
    @property  
    def handlers(self):
        """Provide access to logging.handlers for compatibility"""
        return _std_logging.handlers


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
    if not hasattr(std_logging, '_original_getLogger'):
        std_logging._original_getLogger = std_logging.getLogger
    
    # Replace getLogger with our version
    def logxide_getLogger(name=None):
        """Get a logxide logger that wraps the standard logger"""
        # Get the standard logger first
        std_logger = std_logging._original_getLogger(name)
        
        # Create a logxide logger
        logxide_logger = getLogger(name)
        
        # Replace the standard logger's methods with logxide versions
        # Only replace methods that exist in both loggers
        methods_to_replace = ['debug', 'info', 'warning', 'error', 'critical']
        
        for method in methods_to_replace:
            if hasattr(logxide_logger, method):
                setattr(std_logger, method, getattr(logxide_logger, method))
        
        # Handle exception method specially - it's error + traceback
        if hasattr(std_logger, 'exception'):
            def exception_wrapper(msg, *args, **kwargs):
                # Use logxide error method for exception logging
                logxide_logger.error(msg, *args, **kwargs)
            std_logger.exception = exception_wrapper
        
        return std_logger
    
    # Replace the getLogger function
    std_logging.getLogger = logxide_getLogger
    
    # Also replace basicConfig to use logxide
    if not hasattr(std_logging, '_original_basicConfig'):
        std_logging._original_basicConfig = std_logging.basicConfig
    
    def logxide_basicConfig(**kwargs):
        """Use logxide basicConfig but also call original for compatibility"""
        try:
            std_logging._original_basicConfig(**kwargs)
        except:
            pass  # Ignore errors in standard basicConfig
        return basicConfig(**kwargs)
    
    std_logging.basicConfig = logxide_basicConfig
    
    # Also add flush method if it doesn't exist
    if not hasattr(std_logging, 'flush'):
        std_logging.flush = flush
    
    # Add set_thread_name method if it doesn't exist
    if not hasattr(std_logging, 'set_thread_name'):
        std_logging.set_thread_name = set_thread_name
    
    # Migrate any loggers that might have been created before install()
    _migrate_existing_loggers()


def uninstall():
    """
    Restore the standard logging module.

    This undoes the monkey-patching done by install().
    """
    import logging as std_logging
    
    # Restore original getLogger if it exists
    if hasattr(std_logging, '_original_getLogger'):
        std_logging.getLogger = std_logging._original_getLogger
        delattr(std_logging, '_original_getLogger')
    
    # Restore original basicConfig if it exists
    if hasattr(std_logging, '_original_basicConfig'):
        std_logging.basicConfig = std_logging._original_basicConfig
        delattr(std_logging, '_original_basicConfig')