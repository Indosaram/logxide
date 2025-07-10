"""
Simplified basic logging functionality tests.
Focus on functionality rather than output capture.
"""
import threading
import time

import pytest

from logxide import logging


class TestBasicLoggingSimple:
    """Test basic logging functionality without output capture."""

    @pytest.mark.unit
    def test_logger_creation(self, clean_logging_state):
        """Test that loggers can be created."""
        logger = logging.getLogger("test.logger")
        assert logger is not None
        assert logger.name == "test.logger"

    @pytest.mark.unit
    def test_logger_hierarchy(self, clean_logging_state):
        """Test logger hierarchy."""
        parent_logger = logging.getLogger("parent")
        child_logger = logging.getLogger("parent.child")
        grandchild_logger = logging.getLogger("parent.child.grandchild")

        assert parent_logger.name == "parent"
        assert child_logger.name == "parent.child"
        assert grandchild_logger.name == "parent.child.grandchild"

    @pytest.mark.unit
    def test_log_levels(self, clean_logging_state):
        """Test log level constants."""
        assert logging.DEBUG == 10
        assert logging.INFO == 20
        assert logging.WARNING == 30
        assert logging.ERROR == 40
        assert logging.CRITICAL == 50

    @pytest.mark.unit
    def test_logger_set_level(self, clean_logging_state):
        """Test setting logger level."""
        logger = logging.getLogger("test.level")
        logger.setLevel(logging.WARNING)
        assert logger.getEffectiveLevel() == logging.WARNING

        logger.setLevel(logging.DEBUG)
        assert logger.getEffectiveLevel() == logging.DEBUG

        logger.setLevel(logging.CRITICAL)
        assert logger.getEffectiveLevel() == logging.CRITICAL

    @pytest.mark.unit
    def test_basic_config(self, clean_logging_state):
        """Test basic configuration."""
        # Should not raise any exceptions
        logging.basicConfig()
        logging.basicConfig(level=logging.INFO)
        logging.basicConfig(format="%(levelname)s: %(message)s")
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(message)s", datefmt="%H:%M:%S"
        )

    @pytest.mark.unit
    def test_flush_functionality(self, clean_logging_state):
        """Test flush functionality."""
        logging.basicConfig()
        logger = logging.getLogger("test.flush")
        logger.setLevel(logging.INFO)

        # Should not raise any exceptions
        logger.info("Test message")
        logging.flush()

    @pytest.mark.unit
    def test_logging_methods_no_exceptions(self, clean_logging_state):
        """Test that all logging methods work without exceptions."""
        logging.basicConfig()
        logger = logging.getLogger("test.methods")
        logger.setLevel(logging.DEBUG)

        # All these should execute without exceptions
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        logging.flush()

    @pytest.mark.unit
    def test_multiple_loggers(self, clean_logging_state):
        """Test multiple loggers working together."""
        logging.basicConfig()

        logger1 = logging.getLogger("app.database")
        logger2 = logging.getLogger("app.api")
        logger3 = logging.getLogger("app.cache")

        logger1.setLevel(logging.INFO)
        logger2.setLevel(logging.WARNING)
        logger3.setLevel(logging.ERROR)

        # Should all work without exceptions
        logger1.info("Database message")
        logger2.warning("API message")
        logger3.error("Cache message")

        logging.flush()

        # Check that levels are set correctly
        assert logger1.getEffectiveLevel() == logging.INFO
        assert logger2.getEffectiveLevel() == logging.WARNING
        assert logger3.getEffectiveLevel() == logging.ERROR

    @pytest.mark.unit
    def test_logger_names_uniqueness(self, clean_logging_state):
        """Test that loggers with same name return same instance."""
        logger1 = logging.getLogger("same.name")
        logger2 = logging.getLogger("same.name")

        # Should be the same instance (or at least have same properties)
        assert logger1.name == logger2.name

        # Setting level on one should affect the other
        logger1.setLevel(logging.WARNING)
        assert logger2.getEffectiveLevel() == logging.WARNING

    @pytest.mark.unit
    def test_different_format_configurations(self, clean_logging_state):
        """Test different format configurations."""
        logger = logging.getLogger("test.format")
        logger.setLevel(logging.INFO)

        # Test various format configurations
        formats = [
            "%(levelname)s: %(message)s",
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "[%(levelname)s] %(name)s: %(message)s",
            "%(threadName)s | %(name)s | %(message)s",
            '{"level":"%(levelname)s","message":"%(message)s"}',
        ]

        for fmt in formats:
            logging.basicConfig(format=fmt)
            logger.info(f"Testing format: {fmt}")
            logging.flush()

    @pytest.mark.unit
    def test_thread_names(self, clean_logging_state):
        """Test thread naming functionality."""
        # Test setting and getting thread names
        logging.set_thread_name("TestThread")
        assert logging.get_thread_name() == "TestThread"

        logging.set_thread_name("AnotherThread")
        assert logging.get_thread_name() == "AnotherThread"

        # Test with logging
        logging.basicConfig(format="%(threadName)s: %(message)s")
        logger = logging.getLogger("test.threadname")
        logger.setLevel(logging.INFO)

        logging.set_thread_name("MainTestThread")
        logger.info("Message from main thread")
        logging.flush()


class TestBasicFormats:
    """Test basic format functionality without output capture."""

    @pytest.mark.formatting
    def test_format_specifiers_no_errors(self, clean_logging_state):
        """Test that format specifiers don't cause errors."""
        logger = logging.getLogger("test.specifiers")
        logger.setLevel(logging.INFO)

        # Test various format specifiers
        specifiers = [
            "%(asctime)s",
            "%(name)s",
            "%(levelname)s",
            "%(levelno)d",
            "%(message)s",
            "%(thread)d",
            "%(threadName)s",
            "%(process)d",
            "%(msecs)d",
        ]

        for spec in specifiers:
            logging.basicConfig(format=f"{spec}: %(message)s")
            logger.info(f"Testing {spec}")
            logging.flush()

    @pytest.mark.formatting
    def test_padding_formats_no_errors(self, clean_logging_state):
        """Test that padding formats don't cause errors."""
        logger = logging.getLogger("test.padding")
        logger.setLevel(logging.INFO)

        # Test various padding formats
        padding_formats = [
            "%(levelname)-8s",
            "%(name)-15s",
            "%(threadName)-10s",
            "%(msecs)03d",
        ]

        for fmt in padding_formats:
            logging.basicConfig(format=f"{fmt}: %(message)s")
            logger.info(f"Testing {fmt}")
            logging.flush()

    @pytest.mark.formatting
    def test_complex_formats_no_errors(self, clean_logging_state):
        """Test complex format combinations."""
        logger = logging.getLogger("test.complex")
        logger.setLevel(logging.INFO)

        complex_formats = [
            "%(asctime)s [%(process)d:%(thread)d] %(levelname)s %(name)s: %(message)s",
            "[%(asctime)s.%(msecs)03d] %(name)s:%(levelname)s:%(thread)d - %(message)s",
            "%(asctime)s | %(name)s | %(levelname)-8s | Thread-%(thread)d | %(message)s",
            "[%(asctime)s] %(threadName)-10s | %(name)-15s | %(levelname)-8s | %(message)s",
        ]

        for fmt in complex_formats:
            logging.basicConfig(format=fmt, datefmt="%Y-%m-%d %H:%M:%S")
            logger.info("Testing complex format")
            logging.flush()


class TestThreadingSimple:
    """Test threading functionality without output capture."""

    @pytest.mark.threading
    def test_multithreaded_logging_no_errors(self, clean_logging_state):
        """Test that multi-threaded logging doesn't cause errors."""
        logging.basicConfig(format="%(threadName)s: %(name)s - %(message)s")

        def worker(worker_id):
            logging.set_thread_name(f"Worker-{worker_id}")
            logger = logging.getLogger(f"worker.{worker_id}")
            logger.setLevel(logging.INFO)

            for i in range(5):
                logger.info(f"Message {i}")
                time.sleep(0.001)  # Small delay

        # Start multiple threads
        threads = []
        for i in range(3):
            t = threading.Thread(target=worker, args=[i])
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        logging.flush()

    @pytest.mark.threading
    def test_thread_isolation(self, clean_logging_state):
        """Test that thread names are isolated."""
        results = {}

        def worker(thread_id):
            thread_name = f"IsolatedWorker-{thread_id}"
            logging.set_thread_name(thread_name)
            results[thread_id] = logging.get_thread_name()

        threads = []
        for i in range(3):
            t = threading.Thread(target=worker, args=[i])
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Check that each thread had its own name
        assert results[0] == "IsolatedWorker-0"
        assert results[1] == "IsolatedWorker-1"
        assert results[2] == "IsolatedWorker-2"
