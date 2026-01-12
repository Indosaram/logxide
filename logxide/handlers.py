"""
Compatibility handlers for LogXide.

These classes provide a bridge between Python's standard logging handlers
and LogXide's Rust-native handlers. They inherit from standard logging classes
to satisfy isinstance checks (e.g. in dictConfig) while delegating actual
work to the high-performance Rust implementation.
"""

import logging
import logging.handlers
import sys
from . import logxide


class FileHandler(logging.FileHandler):
    """
    Shim for FileHandler that wraps the Rust implementation.
    """

    def __init__(self, filename, mode="a", encoding=None, delay=False, errors=None):
        # Initialize the Python handler for compatibility/attributes
        # We don't want it to actually open the file if possible, or we close it immediately?
        # Standard FileHandler opens the file in __init__.
        # If we let it open, we have two file handles.
        # Rust handler opens its own file.
        # This is suboptimal but necessary for isinstance(h, logging.FileHandler).
        # To avoid double writing, we can set the python stream to a dummy or close it.
        super().__init__(filename, mode, encoding, delay, errors)

        # Close the python file handle immediately as we won't use it
        self.close()

        # Create the Rust handler
        self._inner = logxide.FileHandler(filename)

    def setLevel(self, level):
        super().setLevel(level)
        self._inner.setLevel(level)

    def emit(self, record):
        # This method shouldn't be called if wired correctly to PyLogger,
        # but if called by legacy stdlib logger, we should delegate?
        # Converting stdlib record to Rust record is expensive.
        # Ideally we avoid this path.
        pass


class StreamHandler(logging.StreamHandler):
    """
    Shim for StreamHandler that wraps the Rust implementation.
    """

    def __init__(self, stream=None):
        super().__init__(stream)

        target = "stderr"
        if stream is None or stream is sys.stderr:
            target = "stderr"
        elif stream is sys.stdout:
            target = "stdout"
        else:
            target = None

        if target:
            self._inner = logxide.StreamHandler(target)
        else:
            self._inner = logxide.StreamHandler("stderr")

    def setLevel(self, level):
        super().setLevel(level)
        self._inner.setLevel(level)


class RotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    Shim for RotatingFileHandler that wraps the Rust implementation.
    """

    def __init__(
        self,
        filename,
        mode="a",
        maxBytes=0,
        backupCount=0,
        encoding=None,
        delay=False,
        errors=None,
    ):
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
        self.close()

        self._inner = logxide.RotatingFileHandler(filename, maxBytes, backupCount)

    def setLevel(self, level):
        super().setLevel(level)
        self._inner.setLevel(level)
