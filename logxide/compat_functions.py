"""
Compatibility functions for LogXide.

This module provides utility functions that maintain compatibility with
Python's standard logging module.
"""


def addLevelName(level, levelName):
    """Add a level name - compatibility function"""
    pass


def getLevelName(level):
    """Get level name - compatibility function"""
    level_names = {10: "DEBUG", 20: "INFO", 30: "WARNING", 40: "ERROR", 50: "CRITICAL"}
    return level_names.get(level, f"Level {level}")


def disable(level):
    """Disable logging below the specified level - compatibility function"""
    # For compatibility - not fully implemented
    pass


def getLoggerClass():
    """Get the logger class - compatibility function"""
    # Import here to avoid circular imports
    from . import logxide

    return logxide.logging.PyLogger


def setLoggerClass(klass):
    """Set the logger class - compatibility function"""
    # For compatibility - not implemented
    pass
