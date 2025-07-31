"""
Compatibility functions for LogXide.

This module provides utility functions that maintain compatibility with
Python's standard logging module.
"""

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
