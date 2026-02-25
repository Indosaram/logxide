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


class HTTPHandler(logging.Handler):
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
        self._inner = logxide.HTTPHandler(
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

    def setFlushLevel(self, level):
        """
        Set the flush level. Records at or above this level trigger immediate flush.
        Default is ERROR (40).
        
        Args:
            level: Log level (e.g., logging.ERROR, logging.CRITICAL)
        """
        self._inner.setFlushLevel(level)

    def getFlushLevel(self):
        """
        Get the current flush level.
        
        Returns:
            int: Current flush level (e.g., 40 for ERROR)
        """
        return self._inner.getFlushLevel()

class OTLPHandler(logging.Handler):
    """
    High-performance OTLP (OpenTelemetry) handler for log export.
    
    Args:
        url: OTLP endpoint URL (e.g., http://localhost:4318/v1/logs)
        service_name: Service name for OTLP logs
        headers: Optional HTTP headers dict
    """

    def __init__(
        self,
        url,
        service_name,
        headers=None,
    ):
        super().__init__()
        self._inner = logxide.OTLPHandler(url, service_name, headers=headers)

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


class MemoryHandler(logging.Handler):
    """
    High-performance memory handler for testing and log capture.
    Stores records in Rust native memory for maximum performance.
    
    Provides pytest caplog-compatible properties:
    - `.records`: List of LogRecord objects
    - `.text`: All messages joined with newlines
    - `.record_tuples`: List of (logger_name, level, message) tuples
    """

    def __init__(self):
        super().__init__()
        self._inner = logxide.MemoryHandler()

    def setLevel(self, level):
        super().setLevel(level)
        self._inner.setLevel(level)

    def emit(self, record):
        pass

    def get_records(self):
        """Returns all captured records as a list (deprecated: use .records property)."""
        return self._inner.records

    @property
    def records(self):
        """
        All captured log records.
        
        Returns:
            List of LogRecord objects.
        """
        return self._inner.records

    @property
    def text(self):
        """
        All captured log messages as a single newline-separated string.
        
        Compatible with pytest caplog.text.
        
        Returns:
            str: All messages joined with newlines.
        """
        return self._inner.text

    @property
    def record_tuples(self):
        """
        Captured records as tuples.
        
        Compatible with pytest caplog.record_tuples.
        
        Returns:
            List of (logger_name, level_number, message) tuples.
        """
        return self._inner.record_tuples

    def clear(self):
        """Clear all captured records."""
        self._inner.clear()

    def flush(self):
        pass

    def close(self):
        super().close()
