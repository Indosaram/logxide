"""
Fast Logger Wrapper for LogXide

This module provides a Python-side wrapper around the Rust PyLogger that optimizes
the disabled logging fast path by checking log levels before crossing the PyO3 boundary.

This prevents the overhead of:
- PyObject creation for messages
- PyTuple creation for arguments
- PyDict creation for kwargs
- PyO3 boundary crossing

For disabled log calls, this provides a 2-5x speedup.
"""

from typing import Any, Optional

# Log level constants
DEBUG = 10
INFO = 20
WARNING = 30
ERROR = 40
CRITICAL = 50


class FastLoggerWrapper:
    """
    Optimized wrapper around Rust PyLogger that checks log level before
    crossing the PyO3 boundary.
    
    This wrapper intercepts logging calls and performs a fast level check
    on the Python side. If the log level is disabled, it returns immediately
    without creating Python objects or calling into Rust.
    
    For enabled log levels, it delegates to the underlying Rust logger.
    """
    
    __slots__ = ('_rust_logger', '_effective_level', '_name')
    
    def __init__(self, rust_logger):
        """
        Initialize the wrapper around a Rust PyLogger.
        
        Args:
            rust_logger: The underlying Rust PyLogger instance
        """
        self._rust_logger = rust_logger
        self._effective_level = None
        self._name = None
        self._update_cache()
    
    def _update_cache(self):
        """Update cached effective level from Rust logger."""
        try:
            self._effective_level = self._rust_logger.getEffectiveLevel()
            self._name = self._rust_logger.name
        except Exception:
            # Fallback to safe defaults
            self._effective_level = WARNING
            self._name = "root"
    
    def _is_enabled_for(self, level: int) -> bool:
        """
        Fast path level check without crossing into Rust.
        
        Args:
            level: The log level to check
            
        Returns:
            True if the level is enabled, False otherwise
        """
        # Use cached effective level for fast check
        if self._effective_level is None:
            self._update_cache()
        return level >= self._effective_level
    
    def debug(self, msg, *args, **kwargs):
        """Log a debug message (optimized fast path for disabled logs)."""
        if not self._is_enabled_for(DEBUG):
            return
        return self._rust_logger.debug(msg, *args, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        """Log an info message (optimized fast path for disabled logs)."""
        if not self._is_enabled_for(INFO):
            return
        return self._rust_logger.info(msg, *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        """Log a warning message (optimized fast path for disabled logs)."""
        if not self._is_enabled_for(WARNING):
            return
        return self._rust_logger.warning(msg, *args, **kwargs)
    
    def warn(self, msg, *args, **kwargs):
        """Alias for warning() for compatibility."""
        return self.warning(msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        """Log an error message (optimized fast path for disabled logs)."""
        if not self._is_enabled_for(ERROR):
            return
        return self._rust_logger.error(msg, *args, **kwargs)
    
    def critical(self, msg, *args, **kwargs):
        """Log a critical message (optimized fast path for disabled logs)."""
        if not self._is_enabled_for(CRITICAL):
            return
        return self._rust_logger.critical(msg, *args, **kwargs)
    
    def fatal(self, msg, *args, **kwargs):
        """Alias for critical() for compatibility."""
        return self.critical(msg, *args, **kwargs)
    
    def exception(self, msg, *args, exc_info=True, **kwargs):
        """
        Log an exception message (always uses ERROR level).
        
        This is typically called from an exception handler, so exc_info
        defaults to True to capture the current exception.
        """
        if not self._is_enabled_for(ERROR):
            return
        # exception() method in Rust requires Python GIL context
        # We need to call it directly without kwargs manipulation
        return self._rust_logger.exception(msg, *args)
    
    def log(self, level, msg, *args, **kwargs):
        """
        Log a message with explicit level.
        
        Args:
            level: Numeric log level or level name
            msg: Message format string
            *args: Arguments for message formatting
            **kwargs: Additional keyword arguments
        """
        if isinstance(level, str):
            level = _name_to_level.get(level.upper(), WARNING)
        
        if not self._is_enabled_for(level):
            return
        return self._rust_logger.log(level, msg, *args, **kwargs)
    
    def setLevel(self, level):
        """
        Set the logging level and update cached effective level.
        
        Args:
            level: The new logging level (int or string)
        """
        result = self._rust_logger.setLevel(level)
        self._update_cache()  # Update cache after level change
        return result
    
    def isEnabledFor(self, level):
        """
        Check if logger is enabled for a specific level.
        
        Args:
            level: The log level to check
            
        Returns:
            True if enabled, False otherwise
        """
        return self._is_enabled_for(level)
    
    def getEffectiveLevel(self):
        """Get the effective logging level."""
        if self._effective_level is None:
            self._update_cache()
        return self._effective_level
    
    def addHandler(self, handler):
        """Add a handler to the logger and invalidate cache."""
        result = self._rust_logger.addHandler(handler)
        self._update_cache()
        return result
    
    def removeHandler(self, handler):
        """Remove a handler from the logger and invalidate cache."""
        result = self._rust_logger.removeHandler(handler)
        self._update_cache()
        return result
    
    # Delegate all other attributes to the underlying Rust logger
    def __getattr__(self, name):
        """
        Delegate attribute access to the underlying Rust logger.
        
        This allows all other Logger methods and properties to work
        transparently while only optimizing the hot path logging methods.
        """
        return getattr(self._rust_logger, name)
    
    def __setattr__(self, name, value):
        """
        Handle attribute setting, updating cache when needed.
        """
        if name in ('_rust_logger', '_effective_level', '_name'):
            object.__setattr__(self, name, value)
        else:
            setattr(self._rust_logger, name, value)
            # If we're setting something that might affect level, update cache
            if name in ('level', 'parent', 'propagate'):
                self._update_cache()
    
    def __repr__(self):
        """Return string representation."""
        return f"<FastLoggerWrapper({self._name!r}, level={self._effective_level})>"


# Level name mapping for log() method
_name_to_level = {
    'CRITICAL': CRITICAL,
    'FATAL': CRITICAL,
    'ERROR': ERROR,
    'WARN': WARNING,
    'WARNING': WARNING,
    'INFO': INFO,
    'DEBUG': DEBUG,
    'NOTSET': 0,
}