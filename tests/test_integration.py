"""
Integration tests for logxide.
Tests real-world scenarios without output capture complexity.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from logxide import logging


class TestDropInReplacement:
    """Test logxide as a drop-in replacement for Python logging."""

    @pytest.mark.integration
    def test_python_logging_compatibility(self, clean_logging_state):
        """Test that logxide works like Python's logging module."""
        # This should work exactly like Python's logging module
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Create loggers like in standard Python logging
        root_logger = logging.getLogger()
        app_logger = logging.getLogger("myapp")
        db_logger = logging.getLogger("myapp.database")
        api_logger = logging.getLogger("myapp.api")

        # Set levels
        app_logger.setLevel(logging.DEBUG)
        db_logger.setLevel(logging.INFO)
        api_logger.setLevel(logging.WARNING)

        # Test hierarchy and level inheritance
        root_logger.info("Root logger message")
        app_logger.debug("App debug message")
        app_logger.info("App info message")
        db_logger.info("Database connected")
        api_logger.warning("API warning")

        logging.flush()

        # Verify levels are set correctly
        assert app_logger.getEffectiveLevel() == logging.DEBUG
        assert db_logger.getEffectiveLevel() == logging.INFO
        assert api_logger.getEffectiveLevel() == logging.WARNING

    @pytest.mark.integration
    def test_logger_hierarchy_behavior(self, clean_logging_state):
        """Test complex logger hierarchy behavior."""
        logging.basicConfig(format="%(name)s [%(levelname)s]: %(message)s")

        # Create a hierarchy
        root_logger = logging.getLogger()
        app_logger = logging.getLogger("myapp")
        service_logger = logging.getLogger("myapp.service")
        db_logger = logging.getLogger("myapp.service.database")
        api_logger = logging.getLogger("myapp.service.api")

        # Set different levels
        root_logger.setLevel(logging.WARNING)
        app_logger.setLevel(logging.INFO)
        service_logger.setLevel(logging.DEBUG)
        db_logger.setLevel(logging.ERROR)
        # api_logger inherits from service_logger (DEBUG)

        # Test level inheritance
        assert app_logger.getEffectiveLevel() == logging.INFO
        assert service_logger.getEffectiveLevel() == logging.DEBUG
        assert db_logger.getEffectiveLevel() == logging.ERROR
        # API logger should inherit from service logger if not explicitly set

        # Test logging operations don't cause errors
        root_logger.warning("Root warning")
        app_logger.info("App info")
        service_logger.debug("Service debug")
        db_logger.error("DB error")
        api_logger.debug("API debug")

        logging.flush()

    @pytest.mark.integration
    def test_configuration_persistence(self, clean_logging_state):
        """Test that logging configuration persists across operations."""
        # Configure once
        logging.basicConfig(
            format="[%(levelname)s] %(name)s: %(message)s", level=logging.WARNING
        )

        logger1 = logging.getLogger("persistent.test1")
        logger2 = logging.getLogger("persistent.test2")

        # First batch of messages
        logger1.info("Info message 1")  # Should be filtered
        logger1.warning("Warning message 1")  # Should appear
        logger2.error("Error message 1")  # Should appear

        # Second batch of messages
        logger1.warning("Warning message 2")  # Should appear
        logger2.critical("Critical message 1")  # Should appear
        logger1.info("Info message 2")  # Should be filtered

        logging.flush()


class TestRealWorldScenarios:
    """Test real-world application scenarios."""

    @pytest.mark.integration
    @pytest.mark.threading
    def test_web_application_simulation(self, clean_logging_state):
        """Simulate a web application with multiple components."""
        # Configure logging for a web application
        logging.basicConfig(
            format="%(asctime)s [%(threadName)-12s] %(levelname)-8s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            level=logging.INFO,
        )

        # Simulate web server
        def web_server():
            # Thread name set via threading.current_thread().name
            logger = logging.getLogger("app.web")
            logger.info("Web server starting")

            for i in range(3):
                logger.info(f"Handling request {i + 1}")
                time.sleep(0.01)

            logger.info("Web server shutting down")

        # Simulate database connection pool
        def db_pool():
            # Thread name set via threading.current_thread().name
            logger = logging.getLogger("app.database.pool")
            logger.info("Database pool initializing")
            logger.warning("Pool utilization high: 80%")
            logger.info("Database pool ready")

        # Simulate background task processor
        def task_processor():
            # Thread name set via threading.current_thread().name
            logger = logging.getLogger("app.tasks")
            logger.info("Task processor starting")

            for i in range(2):
                logger.info(f"Processing background task {i + 1}")
                if i == 1:
                    logger.error("Task failed, will retry")
                time.sleep(0.01)

            logger.info("Task processor finished")

        # Main application thread
        # Thread name set via threading.current_thread().name
        main_logger = logging.getLogger("app.main")

        main_logger.info("Application startup initiated")

        # Start all components
        threads = [
            threading.Thread(target=web_server),
            threading.Thread(target=db_pool),
            threading.Thread(target=task_processor),
        ]

        for t in threads:
            t.start()

        main_logger.info("All components started")

        for t in threads:
            t.join()

        main_logger.info("Application shutdown complete")
        logging.flush()

    @pytest.mark.integration
    @pytest.mark.slow
    def test_high_throughput_logging(self, clean_logging_state):
        """Test logging system under high throughput."""
        logging.basicConfig(format="%(threadName)s-%(name)s: %(message)s")

        def high_throughput_worker(worker_id):
            # Thread name set via threading.current_thread().name
            logger = logging.getLogger(f"throughput.worker.{worker_id}")
            logger.setLevel(logging.INFO)

            for i in range(50):  # 50 messages per worker
                logger.info(f"High throughput message {i}")
                if i % 25 == 0:
                    logger.warning(f"Checkpoint {i}")

        # Start 10 workers, 500 total messages
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(high_throughput_worker, i) for i in range(10)]
            for future in as_completed(futures):
                future.result()  # Wait for completion

        logging.flush()

    @pytest.mark.integration
    def test_error_handling_and_recovery(self, clean_logging_state):
        """Test error handling and system recovery."""
        logging.basicConfig(format="%(levelname)s: %(name)s - %(message)s")

        logger = logging.getLogger("error.handling")
        logger.setLevel(logging.DEBUG)

        # Simulate various error scenarios
        logger.info("System starting normally")

        try:
            # Simulate an error
            raise ValueError("Simulated error")
        except ValueError as e:
            logger.error(f"Caught error: {e}")
            logger.debug("Error details logged")

        logger.warning("Attempting recovery")
        logger.info("System recovered successfully")

        # Test that system continues to work after errors
        logger.critical("Critical issue detected")
        logger.info("But system is still functional")

        logging.flush()


class TestFormatReconfiguration:
    """Test format reconfiguration scenarios."""

    @pytest.mark.integration
    def test_runtime_format_changes(self, clean_logging_state):
        """Test changing formats during runtime."""
        logger = logging.getLogger("format.switch")
        logger.setLevel(logging.INFO)

        # Phase 1: Simple format
        logging.basicConfig(format="SIMPLE: %(message)s")
        logger.info("Message in simple format")
        logging.flush()

        # Phase 2: Detailed format
        logging.basicConfig(
            format="DETAILED: %(asctime)s - %(levelname)s - %(message)s"
        )
        logger.info("Message in detailed format")
        logging.flush()

        # Phase 3: JSON format
        logging.basicConfig(format='{"level":"%(levelname)s","msg":"%(message)s"}')
        logger.info("Message in JSON format")
        logging.flush()

        # Phase 4: Production format
        logging.basicConfig(
            format="%(asctime)s [%(process)d:%(thread)d] %(levelname)s %(name)s: %(message)s"
        )
        logger.info("Message in production format")
        logging.flush()

    @pytest.mark.integration
    def test_complex_format_combinations(self, clean_logging_state):
        """Test various complex format combinations."""
        logger = logging.getLogger("complex.formats")
        logger.setLevel(logging.INFO)
        # Thread name set via threading.current_thread().name

        formats = [
            # Production-like format
            "%(asctime)s [%(process)d:%(thread)d] %(levelname)s %(name)s: %(message)s",
            # Debug format with milliseconds
            "[%(asctime)s.%(msecs)03d] %(name)s:%(levelname)s:%(thread)d - %(message)s",
            # Detailed format with padding
            "%(asctime)s | %(name)s | %(levelname)-8s | Thread-%(thread)d | %(message)s",
            # Multi-threaded format
            "[%(asctime)s] %(threadName)-15s | %(name)-20s | %(levelname)-8s | %(message)s",
            # JSON-like format
            '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","thread":"%(threadName)s","msg":"%(message)s"}',
        ]

        for i, fmt in enumerate(formats):
            logging.basicConfig(format=fmt, datefmt="%Y-%m-%d %H:%M:%S")
            logger.info(f"Testing format combination {i + 1}")
            logging.flush()


class TestThreadSafety:
    """Test thread safety and concurrency."""

    @pytest.mark.threading
    @pytest.mark.integration
    def test_concurrent_configuration_changes(self, clean_logging_state):
        """Test concurrent logging with configuration changes."""

        def config_changer():
            """Thread that changes logging configuration."""
            # Thread name set via threading.current_thread().name
            formats = [
                "CONFIG1: %(threadName)s - %(message)s",
                "CONFIG2: %(levelname)s:%(threadName)s - %(message)s",
                "CONFIG3: [%(threadName)s] %(name)s: %(message)s",
            ]

            for i, fmt in enumerate(formats):
                logging.basicConfig(format=fmt)
                time.sleep(0.02)

        def message_logger(worker_id):
            """Thread that logs messages."""
            # Thread name set via threading.current_thread().name
            logger = logging.getLogger(f"concurrent.{worker_id}")
            logger.setLevel(logging.INFO)

            for i in range(10):
                logger.info(f"Message {i} from worker {worker_id}")
                time.sleep(0.01)

        # Start config changer and multiple loggers concurrently
        config_thread = threading.Thread(target=config_changer)
        logger_threads = [
            threading.Thread(target=message_logger, args=[i]) for i in range(3)
        ]

        config_thread.start()
        for t in logger_threads:
            t.start()

        config_thread.join()
        for t in logger_threads:
            t.join()

        logging.flush()

    @pytest.mark.threading
    @pytest.mark.integration
    def test_stress_test_many_threads(self, clean_logging_state):
        """Stress test with many threads logging concurrently."""
        logging.basicConfig(format="%(threadName)s-%(name)s-%(levelname)s: %(message)s")

        def stress_worker(worker_id):
            # Thread name set via threading.current_thread().name
            logger = logging.getLogger(f"stress.{worker_id % 5}")  # Shared loggers
            logger.setLevel(logging.INFO)

            for i in range(20):
                if i % 10 == 0:
                    logger.warning(f"Worker {worker_id} checkpoint {i}")
                else:
                    logger.info(f"Worker {worker_id} message {i}")

                # Random small delays to create contention
                time.sleep(0.001 + (worker_id % 3) * 0.001)

        # Start many threads
        thread_count = 20
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = [executor.submit(stress_worker, i) for i in range(thread_count)]
            for future in as_completed(futures):
                future.result()

        logging.flush()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.integration
    def test_empty_and_special_messages(self, clean_logging_state):
        """Test logging with empty and special messages."""
        logging.basicConfig(format='%(levelname)s: "%(message)s"')
        logger = logging.getLogger("edge.cases")
        logger.setLevel(logging.DEBUG)

        # Test edge cases
        logger.info("")  # Empty message
        logger.info("   ")  # Whitespace only
        logger.info("Message with\nnewlines\nand\ttabs")
        logger.info("Message with unicode: 🚀 ✅ 💡")
        logger.info("Message with quotes: 'single' and \"double\"")
        logger.info("Message with special chars: !@#$%^&*()")
        logger.info("Very " + "long " * 100 + "message")  # Very long message

        logging.flush()

    @pytest.mark.integration
    def test_rapid_level_changes(self, clean_logging_state):
        """Test rapid level changes."""
        logging.basicConfig(format="%(levelname)s: %(message)s")
        logger = logging.getLogger("level.changes")

        levels = [
            logging.DEBUG,
            logging.INFO,
            logging.WARNING,
            logging.ERROR,
            logging.CRITICAL,
        ]

        for i in range(50):  # Rapid changes
            level = levels[i % len(levels)]
            logger.setLevel(level)
            logger.info(f"Message {i} at level {level}")

            # Also test logging at different levels
            logger.debug(f"Debug {i}")
            logger.warning(f"Warning {i}")
            logger.error(f"Error {i}")

        logging.flush()

    @pytest.mark.integration
    def test_logger_name_edge_cases(self, clean_logging_state):
        """Test edge cases in logger names."""
        logging.basicConfig(format="%(name)s: %(message)s")

        # Test various logger name patterns
        edge_names = [
            "",  # Empty name (root logger)
            "a",  # Single character
            "very.long.logger.name.with.many.dots.and.segments",
            "logger-with-dashes",
            "logger_with_underscores",
            "logger123with456numbers",
            "UPPERCASE.LOGGER",
            "MiXeD.cAsE.LoGgEr",
        ]

        for name in edge_names:
            logger = logging.getLogger(name)
            logger.setLevel(logging.INFO)
            logger.info(f"Message from logger: '{name}'")

        logging.flush()
