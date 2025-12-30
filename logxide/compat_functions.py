"""
Compatibility functions for LogXide.

This module provides utility functions that maintain compatibility with
Python's standard logging module.
"""

import warnings

# Global level name registry
_levelToName = {
    50: "CRITICAL",
    40: "ERROR",
    30: "WARNING",
    20: "INFO",
    10: "DEBUG",
    0: "NOTSET",
}
_nameToLevel = {
    "CRITICAL": 50,
    "FATAL": 50,
    "ERROR": 40,
    "WARN": 30,
    "WARNING": 30,
    "INFO": 20,
    "DEBUG": 10,
    "NOTSET": 0,
}


def addLevelName(level, levelName):
    """Add a level name - compatibility function"""
    global _levelToName, _nameToLevel
    _levelToName[level] = levelName
    _nameToLevel[levelName.upper()] = level


def getLevelName(level):
    """Get level name - compatibility function"""
    global _levelToName, _nameToLevel

    # If it's a string, return the corresponding level number
    if isinstance(level, str):
        return _nameToLevel.get(level.upper(), f"Level {level}")

    # If it's a number, return the corresponding level name
    return _levelToName.get(level, f"Level {level}")


def disable(level):
    """Disable logging below the specified level - compatibility function"""
    # For compatibility - not fully implemented
    pass


def getLoggerClass():
    """Get the logger class - compatibility function"""
    # Import here to avoid circular imports
    try:
        from . import logxide

        return logxide.logging.PyLogger
    except ImportError:
        return object  # type: ignore[return-value]


def setLoggerClass(klass):
    """Set the logger class - compatibility function"""
    # For compatibility - not implemented
    pass


# Global warning capture state
_warnings_showwarning = None


def captureWarnings(capture):
    """
    If capture is true, redirect all warnings to the logging package.
    If capture is False, ensure that warnings are not redirected to logging
    but to their original destinations.

    This function maintains full compatibility with Python's logging.captureWarnings.
    """
    global _warnings_showwarning

    if capture:
        if _warnings_showwarning is None:
            _warnings_showwarning = warnings.showwarning

        def showwarning(message, category, filename, lineno, file=None, line=None):
            """
            Implementation of showwarning which redirects to logging.
            """
            from . import logging

            if file is not None:
                if _warnings_showwarning is not None:
                    _warnings_showwarning(
                        message, category, filename, lineno, file, line
                    )
            else:
                s = warnings.formatwarning(message, category, filename, lineno, line)
                logger = logging.getLogger("py.warnings")
                logger.warning("%s", s)

        warnings.showwarning = showwarning
    else:
        if _warnings_showwarning is not None:
            warnings.showwarning = _warnings_showwarning
            _warnings_showwarning = None


def makeLogRecord(dict_):
    """
    Make a LogRecord whose attributes are defined by the specified dictionary.

    This function is useful for converting a logging event received over
    a socket connection (which is sent as a dictionary) into a LogRecord
    instance.

    Args:
        dict_: Dictionary containing log record attributes

    Returns:
        A LogRecord-like object (or dict for LogXide compatibility)
    """

    # For LogXide, we can return the dictionary itself or create a simple object
    # that has the required attributes
    class LogRecordCompat:
        def __init__(self, d):
            self.__dict__.update(d)

    return LogRecordCompat(dict_)


# Global log record factory
_logRecordFactory = None


def getLogRecordFactory():
    """
    Return the factory to be used for creating log records.

    Returns:
        The current log record factory function, or None if using default
    """
    return _logRecordFactory


def setLogRecordFactory(factory):
    """
    Set the factory to be used for creating log records.

    Args:
        factory: A callable that creates LogRecord instances
    """
    global _logRecordFactory
    _logRecordFactory = factory


def getLevelNamesMapping():
    """
    Return a mapping of level names to level numbers.

    This function returns a copy of the internal mapping used for
    level name to number conversions.

    Returns:
        dict: A dictionary mapping level names to level numbers
    """
    global _nameToLevel
    return _nameToLevel.copy()


# Global handler registry
_handlers = {}


def getHandlerByName(name):
    """
    Get a handler by its name.

    Args:
        name: The name of the handler to retrieve

    Returns:
        The handler with the given name, or None if not found
    """
    return _handlers.get(name)


def getHandlerNames():
    """
    Return a list of all registered handler names.

    Returns:
        list: A list of handler names
    """
    return list(_handlers.keys())


def _registerHandler(name, handler):
    """
    Internal function to register a handler.

    This is not part of the public API but is used internally
    to track handlers by name.

    Args:
        name: The name to register the handler under
        handler: The handler instance to register
    """
    _handlers[name] = handler


def _unregisterHandler(name):
    """
    Internal function to unregister a handler.

    Args:
        name: The name of the handler to unregister
    """
    if name in _handlers:
        del _handlers[name]
