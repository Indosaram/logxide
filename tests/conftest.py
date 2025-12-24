"""
Test configuration and fixtures for logxide tests.
"""

import contextlib
import io
import sys
import threading
import time
from contextlib import contextmanager

import pytest

from logxide import logging


@pytest.fixture(autouse=True)
def cleanup_logxide():
    """Ensure proper cleanup of logxide handlers after each test."""
    import gc
    from logxide import logging
    
    # BEFORE test: flush any pending logs
    with contextlib.suppress(BaseException):
        logging.flush()
    
    # Clear Python-side logger handlers (but not Rust global handlers)
    try:
        import logging as std_logging
        
        # Clear all logger handlers
        if hasattr(std_logging.Logger, "manager") and hasattr(std_logging.Logger.manager, "loggerDict"):
            for logger_name, logger_obj in list(std_logging.Logger.manager.loggerDict.items()):
                if hasattr(logger_obj, "handlers"):
                    logger_obj.handlers.clear()
                # Also clear the _logxide_pylogger attribute to force re-wrapping
                if hasattr(logger_obj, "_logxide_pylogger"):
                    delattr(logger_obj, "_logxide_pylogger")
        
        # Clear root logger
        if hasattr(std_logging, "root") and hasattr(std_logging.root, "handlers"):
            std_logging.root.handlers.clear()
            if hasattr(std_logging.root, "_logxide_pylogger"):
                delattr(std_logging.root, "_logxide_pylogger")
    except:
        pass
    
    # Also clear LogXide's root logger
    try:
        root = logging.getLogger()
        if hasattr(root, "handlers"):
            root.handlers.clear()
        if hasattr(root, "_logxide_pylogger"):
            delattr(root, "_logxide_pylogger")
    except:
        pass
    
    # Force garbage collection before test
    gc.collect()
    
    yield

    # AFTER test: cleanup
    with contextlib.suppress(BaseException):
        logging.flush()

    # Small delay to let any active operations complete
    time.sleep(0.05)

    # Complete reset again after test
    try:
        import logging as std_logging
        
        # Clear all logger handlers
        if hasattr(std_logging.Logger, "manager") and hasattr(std_logging.Logger.manager, "loggerDict"):
            for logger_name, logger_obj in list(std_logging.Logger.manager.loggerDict.items()):
                if hasattr(logger_obj, "handlers"):
                    logger_obj.handlers.clear()
                # Clear the _logxide_pylogger attribute
                if hasattr(logger_obj, "_logxide_pylogger"):
                    delattr(logger_obj, "_logxide_pylogger")
        
        # Clear root logger
        if hasattr(std_logging, "root") and hasattr(std_logging.root, "handlers"):
            std_logging.root.handlers.clear()
            if hasattr(std_logging.root, "_logxide_pylogger"):
                delattr(std_logging.root, "_logxide_pylogger")
    except:
        pass

    # Clear LogXide's root logger
    try:
        root = logging.getLogger()
        if hasattr(root, "handlers"):
            root.handlers.clear()
        if hasattr(root, "_logxide_pylogger"):
            delattr(root, "_logxide_pylogger")
    except:
        pass

    # Force garbage collection
    gc.collect()


@pytest.fixture
def clean_logging_state():
    """Clean logging state before and after each test."""
    # Clear any existing thread names
    current_thread_id = threading.current_thread().ident

    # Store original state
    original_handlers = []

    yield

    # Flush any remaining messages
    logging.flush()

    # Reset thread name
    threading.current_thread().name = "TestThread"


@pytest.fixture
def capture_logs():
    """Capture log output for testing."""

    class LogCapture:
        def __init__(self):
            self.records = []
            self.output = io.StringIO()

        def setup(self, format_str=None):
            if format_str:
                logging.basicConfig(format=format_str)
            else:
                logging.basicConfig()

        def get_output(self):
            logging.flush()
            return self.output.getvalue()

        def clear(self):
            self.records.clear()
            self.output = io.StringIO()

    return LogCapture()


@pytest.fixture
def thread_safe_logger():
    """Create a thread-safe logger for testing."""

    def _create_logger(name: str):
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        return logger

    return _create_logger


@pytest.fixture
def sample_log_messages():
    """Sample log messages for testing."""
    return {
        "debug": "This is a debug message",
        "info": "This is an info message",
        "warning": "This is a warning message",
        "error": "This is an error message",
        "critical": "This is a critical message",
    }


@pytest.fixture
def format_test_cases():
    """Test cases for different log formats."""
    return [
        {
            "name": "simple",
            "format": "%(levelname)s: %(name)s - %(message)s",
            "expected_pattern": r"INFO: test\.logger - Test message",
        },
        {
            "name": "detailed",
            "format": "%(asctime)s | %(name)s | %(levelname)-8s | %(message)s",
            "expected_pattern": r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| test\.logger \| INFO\s+\| Test message",
        },
        {
            "name": "json",
            "format": '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
            "expected_pattern": r'{"timestamp":"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}","level":"INFO","logger":"test\.logger","message":"Test message"}',
        },
        {
            "name": "debug_with_thread",
            "format": "[%(asctime)s] %(threadName)-10s | %(name)-15s | %(levelname)-8s | %(message)s",
            "expected_pattern": r"\[\d{2}:\d{2}:\d{2}\] \w+\s+\| test\.logger\s+\| INFO\s+\| Test message",
        },
    ]


@pytest.fixture
def threading_test_config():
    """Configuration for threading tests."""
    return {
        "num_threads": 3,
        "messages_per_thread": 5,
        "thread_names": ["Worker-0", "Worker-1", "Worker-2"],
        "logger_names": ["worker.0", "worker.1", "worker.2"],
    }


@contextmanager
def capture_stdout():
    """Context manager to capture stdout output."""
    old_stdout = sys.stdout
    sys.stdout = captured_output = io.StringIO()
    try:
        yield captured_output
    finally:
        sys.stdout = old_stdout


class LogOutputCapture:
    """Helper class to capture and analyze log output."""

    def __init__(self):
        self.output = io.StringIO()
        self.original_stdout = None
        self.original_stderr = None

    def start_capture(self):
        """Start capturing output."""
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        sys.stdout = self.output
        sys.stderr = self.output

    def stop_capture(self):
        """Stop capturing output."""
        if self.original_stdout:
            sys.stdout = self.original_stdout
        if self.original_stderr:
            sys.stderr = self.original_stderr
        logging.flush()
        # Small delay to ensure async logging completes
        time.sleep(0.05)
        return self.output.getvalue()

    def get_lines(self):
        """Get captured output as lines."""
        return self.output.getvalue().strip().split("\n")

    def clear(self):
        """Clear captured output."""
        self.output = io.StringIO()


@pytest.fixture
def log_output_capture():
    """Fixture that provides log output capturing functionality."""
    capture = LogOutputCapture()
    yield capture
    # Cleanup
    if capture.original_stdout:
        sys.stdout = capture.original_stdout
    if capture.original_stderr:
        sys.stderr = capture.original_stderr


def wait_for_async_logging(timeout: float = 1.0):
    """Wait for async logging to complete."""
    logging.flush()
    time.sleep(0.01)  # Small delay to ensure async processing


@pytest.fixture
def async_wait():
    """Fixture that provides async logging wait functionality."""
    return wait_for_async_logging


# Test markers for categorizing tests
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow
pytest.mark.threading = pytest.mark.threading
pytest.mark.formatting = pytest.mark.formatting
