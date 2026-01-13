"""
Compatibility handlers for LogXide.
"""

import logging
import logging.handlers
import sys
from . import logxide


class FileHandler(logging.FileHandler):
    def __init__(self, filename, mode="a", encoding=None, delay=False, errors=None):
        super().__init__(filename, mode, encoding, delay, errors)
        self.close()
        self._inner = logxide.FileHandler(filename)

    def setLevel(self, level):
        super().setLevel(level)
        self._inner.setLevel(level)

    def emit(self, record):
        pass


class StreamHandler(logging.StreamHandler):
    def __init__(self, stream=None):
        super().__init__(stream)
        target = "stdout" if stream is sys.stdout else "stderr"
        self._inner = logxide.StreamHandler(target)

    def setLevel(self, level):
        super().setLevel(level)
        self._inner.setLevel(level)

    def emit(self, record):
        pass


class RotatingFileHandler(logging.handlers.RotatingFileHandler):
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

    def emit(self, record):
        pass


class BufferedHTTPHandler(logging.Handler):
    """
    High-performance HTTP handler with batching and background transmission.

    Args:
        url: HTTP endpoint URL
        headers: HTTP headers dict (e.g., {"Authorization": "Bearer token"})
        capacity: Max buffer capacity (default: 10000)
        batch_size: Records per batch (default: 1000)
        flush_interval: Seconds between auto-flush (default: 30)
        global_context: Dict of fields added to every record
        transform_callback: Callable(records) -> transformed_records for custom JSON
        context_provider: Callable() -> dict for dynamic context per batch
        error_callback: Callable(error_msg) for HTTP failure handling
    """

    def __init__(
        self,
        url,
        headers=None,
        capacity=10000,
        batch_size=1000,
        flush_interval=30,
        global_context=None,
        transform_callback=None,
        context_provider=None,
        error_callback=None,
    ):
        super().__init__()
        self._inner = logxide.BufferedHTTPHandler(
            url,
            headers=headers,
            capacity=capacity,
            batch_size=batch_size,
            flush_interval=flush_interval,
            global_context=global_context,
            transform_callback=transform_callback,
            context_provider=context_provider,
            error_callback=error_callback,
        )

    def setLevel(self, level):
        super().setLevel(level)
        self._inner.setLevel(level)

    def emit(self, record):
        pass

    def flush(self):
        self._inner.flush()

    def close(self):
        self._inner.shutdown()
        super().close()
