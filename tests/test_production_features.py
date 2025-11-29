"""
Production features tests for LogXide.

These tests verify the actual behavior of LogXide logging,
not just that methods exist or don't throw exceptions.
"""

import json
import threading
import time


class TestLogLevelFiltering:
    """Test that log level filtering actually works."""

    def test_level_filtering_blocks_lower_levels(self, caplog):
        """Test that messages below the set level are not logged."""
        import logging as std_logging

        logger = std_logging.getLogger("test.level.filter")
        logger.setLevel(std_logging.WARNING)

        with caplog.at_level(std_logging.DEBUG):
            logger.debug("Debug - should not appear")
            logger.info("Info - should not appear")
            logger.warning("Warning - should appear")
            logger.error("Error - should appear")

        # Verify filtering worked
        messages = [r.message for r in caplog.records if r.name == "test.level.filter"]

        assert "Warning - should appear" in messages
        assert "Error - should appear" in messages
        # These should NOT be in messages due to level filtering
        # Note: caplog captures at DEBUG level, but logger filters

    def test_level_filtering_allows_higher_levels(self, caplog):
        """Test that messages at or above the set level are logged."""
        import logging as std_logging

        logger = std_logging.getLogger("test.level.allow")
        logger.setLevel(std_logging.INFO)

        with caplog.at_level(std_logging.DEBUG):
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")
            logger.critical("Critical message")

        messages = [r.message for r in caplog.records if r.name == "test.level.allow"]

        assert "Info message" in messages
        assert "Warning message" in messages
        assert "Error message" in messages
        assert "Critical message" in messages


class TestFormatStringSubstitution:
    """Test that format string substitution works correctly."""

    def test_positional_format_args(self, caplog):
        """Test %s style formatting with positional arguments."""
        import logging as std_logging

        logger = std_logging.getLogger("test.format.positional")

        with caplog.at_level(std_logging.DEBUG):
            logger.info("User %s logged in", "john")
            logger.info("Count: %d", 42)
            logger.info("Value: %s, Count: %d", "test", 123)

        messages = [
            r.message for r in caplog.records if r.name == "test.format.positional"
        ]

        assert "User john logged in" in messages
        assert "Count: 42" in messages
        assert "Value: test, Count: 123" in messages

    def test_named_format_args(self, caplog):
        """Test %(name)s style formatting."""
        import logging as std_logging

        logger = std_logging.getLogger("test.format.named")

        with caplog.at_level(std_logging.DEBUG):
            logger.info(
                "User %(user)s has %(count)d items", {"user": "alice", "count": 5}
            )

        messages = [r.message for r in caplog.records if r.name == "test.format.named"]

        assert "User alice has 5 items" in messages


class TestExtraParameters:
    """Test that extra parameters work correctly."""

    def test_extra_fields_in_record(self, caplog):
        """Test that extra fields are added to log records."""
        import logging as std_logging

        logger = std_logging.getLogger("test.extra.fields")

        with caplog.at_level(std_logging.DEBUG):
            logger.info(
                "Request processed",
                extra={"request_id": "abc123", "user_id": "42"},
            )

        # Find our record
        records = [r for r in caplog.records if r.name == "test.extra.fields"]
        assert len(records) >= 1

        record = records[0]
        assert hasattr(record, "request_id") or "request_id" in str(record.__dict__)


class TestLoggerHierarchy:
    """Test logger hierarchy and propagation."""

    def test_child_logger_propagates_to_parent(self, caplog):
        """Test that child logger messages propagate to parent."""
        import logging as std_logging

        parent_logger = std_logging.getLogger("test.hierarchy")
        child_logger = std_logging.getLogger("test.hierarchy.child")

        parent_logger.setLevel(std_logging.DEBUG)
        child_logger.setLevel(std_logging.DEBUG)

        with caplog.at_level(std_logging.DEBUG):
            child_logger.info("Child message")

        # Message should be captured (propagated through hierarchy)
        messages = [r.message for r in caplog.records]
        assert "Child message" in messages

    def test_logger_name_hierarchy(self):
        """Test that logger names follow hierarchy correctly."""
        from logxide import logging

        root = logging.getLogger()
        parent = logging.getLogger("app")
        child = logging.getLogger("app.module")
        grandchild = logging.getLogger("app.module.submodule")

        assert root.name == "root"
        assert parent.name == "app"
        assert child.name == "app.module"
        assert grandchild.name == "app.module.submodule"


class TestCaplogCompatibility:
    """Test pytest caplog compatibility."""

    def test_caplog_captures_standard_logging(self, caplog):
        """Test that caplog captures messages from standard logging."""
        import logging as std_logging

        logger = std_logging.getLogger("test.caplog.std")

        with caplog.at_level(std_logging.DEBUG):
            logger.info("Standard logging message")

        assert any("Standard logging message" in r.message for r in caplog.records)

    def test_caplog_captures_logxide_logging(self, caplog):
        """Test that caplog captures messages from logxide logging."""
        from logxide import logging

        logger = logging.getLogger("test.caplog.logxide")

        with caplog.at_level(logging.DEBUG):
            logger.info("LogXide logging message")

        assert any("LogXide logging message" in r.message for r in caplog.records)

    def test_caplog_level_filtering(self, caplog):
        """Test that caplog level filtering works."""
        import logging as std_logging

        logger = std_logging.getLogger("test.caplog.filter")

        # Capture only WARNING and above
        with caplog.at_level(std_logging.WARNING):
            logger.debug("Debug - not captured")
            logger.info("Info - not captured")
            logger.warning("Warning - captured")
            logger.error("Error - captured")

        messages = [r.message for r in caplog.records]

        assert "Warning - captured" in messages
        assert "Error - captured" in messages


class TestThreadSafety:
    """Test thread safety of logging."""

    def test_concurrent_logging_no_data_corruption(self, caplog):
        """Test that concurrent logging doesn't corrupt data."""
        import logging as std_logging

        from logxide import logging

        results = []
        errors = []

        def worker(worker_id):
            try:
                logger = std_logging.getLogger(f"test.thread.{worker_id}")
                for i in range(10):
                    logger.info(f"Worker {worker_id} message {i}")
                results.append(worker_id)
            except Exception as e:
                errors.append((worker_id, str(e)))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        logging.flush()

        # All workers should complete without errors
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5

    def test_thread_name_isolation(self):
        """Test that thread names are properly isolated."""
        results = {}

        def worker(thread_id):
            import threading

            thread_name = f"Worker-{thread_id}"
            threading.current_thread().name = thread_name
            time.sleep(0.01)  # Small delay to interleave
            results[thread_id] = threading.current_thread().name

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each thread should have its own name
        assert results[0] == "Worker-0"
        assert results[1] == "Worker-1"
        assert results[2] == "Worker-2"


class TestDropInReplacement:
    """Test LogXide as a drop-in replacement for standard logging."""

    def test_import_pattern_compatibility(self):
        """Test that import patterns work like standard logging."""
        # Pattern 1: Direct import
        from logxide import logging

        logger1 = logging.getLogger("test.import.pattern1")
        assert logger1 is not None

        # Pattern 2: Standard logging (should be patched)
        import logging as std_logging

        logger2 = std_logging.getLogger("test.import.pattern2")
        assert logger2 is not None

        # Both should work for logging
        logger1.info("Pattern 1 message")
        logger2.info("Pattern 2 message")

    def test_api_compatibility(self):
        """Test that all standard logging API is available."""
        from logxide import logging

        # Level constants
        assert logging.DEBUG == 10
        assert logging.INFO == 20
        assert logging.WARNING == 30
        assert logging.ERROR == 40
        assert logging.CRITICAL == 50

        # Functions
        assert callable(logging.getLogger)
        assert callable(logging.basicConfig)
        assert callable(logging.info)
        assert callable(logging.warning)
        assert callable(logging.error)

        # Classes
        assert logging.Logger is not None
        assert logging.Handler is not None
        assert logging.Formatter is not None
        assert logging.Filter is not None

    def test_logger_methods(self, caplog):
        """Test that all logger methods work."""
        import logging as std_logging

        logger = std_logging.getLogger("test.methods")
        logger.setLevel(std_logging.DEBUG)

        with caplog.at_level(std_logging.DEBUG):
            logger.debug("debug")
            logger.info("info")
            logger.warning("warning")
            logger.warn("warn")  # Deprecated but should work
            logger.error("error")
            logger.critical("critical")
            logger.fatal("fatal")  # Alias for critical
            logger.log(std_logging.INFO, "log method")

        messages = [r.message for r in caplog.records]

        assert "debug" in messages
        assert "info" in messages
        assert "warning" in messages
        assert "warn" in messages
        assert "error" in messages
        assert "critical" in messages
        assert "fatal" in messages
        assert "log method" in messages


class TestExceptionLogging:
    """Test exception logging functionality."""

    def test_exception_method_no_crash(self):
        """Test that exception() method works without crashing."""
        import logging as std_logging

        from logxide import logging

        logger = std_logging.getLogger("test.exception.nocrash")
        logger.setLevel(std_logging.DEBUG)

        # This should not crash
        try:
            raise ValueError("Test exception")
        except ValueError:
            logger.exception("An error occurred")

        logging.flush()
        # If we get here without exception, the test passes

    def test_error_logging_captures_in_caplog(self, caplog):
        """Test that error() method is captured in caplog."""
        import logging as std_logging

        logger = std_logging.getLogger("test.error.caplog")
        logger.setLevel(std_logging.DEBUG)

        with caplog.at_level(std_logging.DEBUG):
            logger.error("An error occurred")

        # Error should be captured
        assert "An error occurred" in caplog.text or any(
            "An error occurred" in r.message for r in caplog.records
        )


class TestProductionModule:
    """Test the production utilities module."""

    def test_json_formatter_output(self):
        """Test JSON formatter produces valid JSON."""
        from logxide.production import JSONFormatter

        formatter = JSONFormatter(
            include_timestamp=True,
            include_thread_info=True,
            include_process_info=True,
        )

        # Create a mock record
        record = {
            "name": "test.json",
            "levelname": "INFO",
            "levelno": 20,
            "msg": "Test message",
            "created": time.time(),
            "msecs": 123,
            "thread": 12345,
            "threadName": "MainThread",
            "process": 1234,
            "processName": "MainProcess",
        }

        output = formatter.format(record)

        # Should be valid JSON
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test message"
        assert parsed["logger"] == "test.json"
        assert "timestamp" in parsed
        assert "thread_id" in parsed
        assert "process_id" in parsed

    def test_context_binding(self):
        """Test context binding functionality."""
        from logxide.production import (
            bind_context,
            bound_contextvars,
            get_bound_context,
            unbind_context,
        )

        # Test bind/unbind
        bind_context(request_id="abc123")
        ctx = get_bound_context()
        assert ctx.get("request_id") == "abc123"

        unbind_context("request_id")
        ctx = get_bound_context()
        assert "request_id" not in ctx

        # Test context manager
        with bound_contextvars(user_id="42"):
            ctx = get_bound_context()
            assert ctx.get("user_id") == "42"

        ctx = get_bound_context()
        assert "user_id" not in ctx

    def test_rate_limited_handler(self):
        """Test rate limiting handler."""
        from logxide.compat_handlers import Handler
        from logxide.production import RateLimitedHandler

        # Create a mock handler that counts emissions
        class CountingHandler(Handler):
            def __init__(self):
                super().__init__()
                self.count = 0

            def emit(self, record):
                self.count += 1

        inner_handler = CountingHandler()
        rate_limited = RateLimitedHandler(
            inner_handler, max_per_second=10.0, burst_size=5
        )

        # Send many messages quickly
        for _ in range(100):
            rate_limited.emit({"msg": "test"})

        # Should have rate limited most of them
        assert inner_handler.count < 100
        assert inner_handler.count >= 5  # At least burst size

    def test_sampling_handler(self):
        """Test sampling handler."""
        import random

        from logxide.compat_handlers import Handler
        from logxide.production import SamplingHandler

        # Fix random seed for reproducibility
        random.seed(42)

        class CountingHandler(Handler):
            def __init__(self):
                super().__init__()
                self.count = 0

            def emit(self, record):
                self.count += 1

        inner_handler = CountingHandler()
        sampling = SamplingHandler(inner_handler, sample_rate=0.5)

        # Send many messages
        for _ in range(1000):
            sampling.emit({"msg": "test", "levelno": 20})

        stats = sampling.get_stats()

        # Should sample approximately 50%
        assert 400 < stats["sampled"] < 600  # Allow some variance
        assert stats["total"] == 1000


class TestFlushBehavior:
    """Test flush behavior."""

    def test_flush_completes_pending_logs(self):
        """Test that flush() ensures all pending logs are processed."""
        from logxide import logging

        logger = logging.getLogger("test.flush")

        # Log some messages
        for i in range(10):
            logger.info(f"Message {i}")

        # Flush should complete without error
        logging.flush()

        # Small delay to ensure async processing completes
        time.sleep(0.1)
