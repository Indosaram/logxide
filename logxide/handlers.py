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


class MemoryHandler(logging.Handler):
    """
    High-performance memory handler for testing and log capture.
    Stores records in Rust native memory for maximum performance.
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
        """Returns all captured records as a list."""
        return self._inner.getRecords()

    def clear(self):
        """Clears all captured records."""
        self._inner.clear()

    def flush(self):
        pass

    def close(self):
        super().close()


class OTLPHandler(logging.Handler):
    """
    High-performance OpenTelemetry OTLP (protobuf) handler with batching and background transmission.
    Compatible with OTLP (OpenTelemetry Protocol) receivers.

    Args:
        url: OTLP HTTP endpoint URL (e.g., "http://localhost:4318/v1/logs")
        headers: HTTP headers dict (e.g., {"Authorization": "Bearer token"})
        service_name: Service name for OTLP resource attribute (default: "unknown_service")
        capacity: Max buffer capacity (default: 10000)
        batch_size: Records per batch (default: 1000)
        flush_interval: Seconds between auto-flush (default: 30)
        error_callback: Callable(error_msg) for HTTP failure handling
    """

    def __init__(
        self,
        url,
        headers=None,
        service_name="unknown_service",
        capacity=10000,
        batch_size=1000,
        flush_interval=30,
        error_callback=None,
    ):
        super().__init__()
        self._inner = logxide.OTLPHandler(
            url,
            headers=headers,
            service_name=service_name,
            capacity=capacity,
            batch_size=batch_size,
            flush_interval=flush_interval,
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


class MemoryHandler(logging.Handler):
    """
    High-performance memory handler for testing and log capture.
    Stores records in Rust native memory for maximum performance.
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
        """Returns all captured records as a list."""
        return self._inner.getRecords()

    def clear(self):
        """Clears all captured records."""
        self._inner.clear()

    def flush(self):
        pass

    def close(self):
        super().close()
