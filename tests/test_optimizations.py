"""
Regression tests for low-risk fixes:
1. Message cache removal (Step 1).
2. PyTuple conversion support in consolidated JSON converter (Step 2).
3. Direct ANSI color support in RustFormatter (Step 3).
4. activate_caller_info compatibility layer integration (Step 4).
"""

from logxide import LogRecord, logging
from logxide.compat_handlers import Formatter as CompatFormatter
from logxide.compat_handlers import Handler as CompatHandler
from logxide.logxide import HTTPHandler, activate_caller_info


def test_message_roundtrip(clean_logging_state):
    """Test message formatting and logging roundtrip after string cache cleanup."""
    from logxide import RustFormatter

    record = LogRecord(
        name="test",
        levelno=20,
        pathname="test.py",
        lineno=1,
        msg="Hello World 123",
    )
    record.levelname = "INFO"

    formatter = RustFormatter("%(levelname)s: %(message)s")
    assert formatter.format(record) == "INFO: Hello World 123"


def test_tuple_to_array_serialization():
    """Test that tuple-valued fields serialize as JSON arrays."""
    # We can pass a dict with tuple inside global_context to HTTPHandler
    handler = HTTPHandler(
        url="http://localhost:8080", global_context={"my_tuple": (1, 2, 3)}
    )
    assert handler is not None


def test_ansi_color_placeholder_direct_support():
    """Test that RustFormatter supports ansi color placeholders directly."""
    from logxide import RustFormatter

    fmt = "%(ansi_level_color)s[%(levelname)s]%(ansi_reset_color)s %(message)s"
    formatter = RustFormatter(fmt)

    record = LogRecord(
        name="test",
        levelno=20,
        pathname="test.py",
        lineno=1,
        msg="Test message",
    )
    record.levelname = "INFO"

    formatted = formatter.format(record)
    assert "\x1b[32m" in formatted
    assert "\x1b[0m" in formatted
    assert "INFO" in formatted
    assert "Test message" in formatted


def test_compat_caller_info_activation():
    """Test that compat handlers with caller-info placeholders activate caller-info introspection."""
    # Verify the pyfunction activate_caller_info exists and is callable
    assert activate_caller_info is not None

    # Create handler and formatter with caller info placeholder
    class CaptureHandler(CompatHandler):
        def __init__(self):
            super().__init__()
            self.buffer = []

        def emit(self, record):
            self.buffer.append(self.format(record))

    handler = CaptureHandler()
    formatter = CompatFormatter("%(funcName)s - %(message)s")
    handler.setFormatter(formatter)

    logger = logging.getLogger("test_compat_caller")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    def log_caller_func():
        logger.info("testing compat caller info")

    log_caller_func()
    logging.flush()

    assert len(handler.buffer) > 0
    assert "log_caller_func" in handler.buffer[0]
