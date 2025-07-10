import threading
import time

from logxide import logging

# --- Comprehensive example using logxide as a drop-in replacement for Python's logging ---

# If logxide is installed as a drop-in, you can simply import logging as usual.
# (e.g., via `import logxide.logging as logging` or monkey-patching sys.modules["logging"])
# For this example, we assume `import logging` uses logxide.


def test_default_format():
    """Test 1: Default Python logging format"""
    print("=== Test 1: Default Format ===")
    logging.basicConfig()

    logger = logging.getLogger("myapp")
    logger.setLevel(logging.INFO)

    logger.debug("This debug message will not be shown (level=INFO).")
    logger.info("Hello from logxide (INFO)!")
    logger.warning("This is a warning.")
    logger.error("This is an error.")
    logger.critical("This is critical.")

    # Hierarchical logger example
    sublogger = logging.getLogger("myapp.module.submodule")
    sublogger.info("Logging from a submodule logger.")

    # Demonstrate propagation and root logger
    root_logger = logging.getLogger()
    root_logger.info("Root logger message.")
    logging.flush()  # Ensure all log messages are processed
    print()


def test_simple_format():
    """Test 2: Simple format"""
    print("=== Test 2: Simple Format ===")
    logging.basicConfig(format="%(levelname)s: %(name)s - %(message)s")

    logger = logging.getLogger("simple")
    logger.setLevel(logging.INFO)
    logger.info("Simple format message")
    logger.warning("Warning in simple format")
    logger.error("Error in simple format")
    logging.flush()  # Ensure all log messages are processed
    print()


def test_detailed_format():
    """Test 3: Detailed format with timestamp and thread info"""
    print("=== Test 3: Detailed Format with Thread Info ===")
    detailed_format = (
        "%(asctime)s | %(name)s | %(levelname)-8s | Thread-%(thread)d | %(message)s"
    )
    logging.basicConfig(format=detailed_format, datefmt="%Y-%m-%d %H:%M:%S")

    logger = logging.getLogger("detailed")
    logger.setLevel(logging.DEBUG)
    logger.debug("Debug message with detailed format")
    logger.info("Info message with detailed format")
    logger.warning("Warning message with detailed format")
    logger.error("Error message with detailed format")
    logging.flush()  # Ensure all log messages are processed
    print()


def test_json_format():
    """Test 4: JSON-like structured format"""
    print("=== Test 4: JSON-like Structured Format ===")
    json_format = '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","thread":%(thread)d,"process":%(process)d,"message":"%(message)s"}'
    logging.basicConfig(format=json_format, datefmt="%Y-%m-%dT%H:%M:%S")

    logger = logging.getLogger("api.service")
    logger.setLevel(logging.INFO)
    logger.info("User authentication successful")
    logger.warning("Rate limit approaching for user")
    logger.error("Database connection timeout")
    logging.flush()  # Ensure all log messages are processed
    print()


def test_debug_format():
    """Test 5: Development/Debug format with all available fields"""
    print("=== Test 5: Development/Debug Format ===")
    debug_format = (
        "[%(asctime)s.%(msecs)03d] %(name)s:%(levelname)s:%(thread)d - %(message)s"
    )
    logging.basicConfig(format=debug_format, datefmt="%H:%M:%S")

    logger = logging.getLogger("debug.module")
    logger.setLevel(logging.DEBUG)
    logger.debug("Debug trace information")
    logger.info("Application state info")
    logger.warning("Performance warning")
    logger.error("Runtime error occurred")
    logger.critical("Critical system failure")
    logging.flush()  # Ensure all log messages are processed
    print()


def test_multithreaded_format():
    """Test 6: Multi-threaded logging with thread names"""
    print("=== Test 6: Multi-threaded Logging ===")
    thread_format = (
        "[%(asctime)s] %(threadName)-10s | %(name)-15s | %(levelname)-8s | %(message)s"
    )
    logging.basicConfig(format=thread_format, datefmt="%H:%M:%S")

    def worker(worker_id):
        # Set thread name for logging
        logging.set_thread_name(f"Worker-{worker_id}")

        logger = logging.getLogger(f"worker.{worker_id}")
        logger.setLevel(logging.INFO)

        for i in range(3):
            logger.info(f"Processing task {i+1}")
            time.sleep(0.1)  # Simulate work

        logger.info("Worker completed all tasks")

    # Set main thread name
    logging.set_thread_name("MainThread")

    # Create main logger
    main_logger = logging.getLogger("main")
    main_logger.setLevel(logging.INFO)
    main_logger.info("Starting multi-threaded example")

    # Start worker threads
    threads = []
    for i in range(3):
        t = threading.Thread(target=worker, args=[i])
        threads.append(t)
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    main_logger.info("All worker threads completed")
    logging.flush()  # Ensure all log messages are processed
    print()


def test_production_format():
    """Test 7: Production-ready format"""
    print("=== Test 7: Production Format ===")
    prod_format = (
        "%(asctime)s [%(process)d:%(thread)d] %(levelname)s %(name)s: %(message)s"
    )
    logging.basicConfig(format=prod_format, datefmt="%Y-%m-%d %H:%M:%S")

    # Simulate different application components
    components = [
        "auth.service",
        "db.connection",
        "api.gateway",
        "cache.redis",
        "queue.processor",
    ]

    for component in components:
        logger = logging.getLogger(component)
        logger.setLevel(logging.INFO)
        logger.info(f"{component} initialized successfully")
        if component == "db.connection":
            logger.warning("Connection pool at 80% capacity")
        elif component == "cache.redis":
            logger.error("Cache miss rate high")
    logging.flush()  # Ensure all log messages are processed
    print()


def test_minimal_format():
    """Test 8: Minimal format for clean output"""
    print("=== Test 8: Minimal Format ===")
    logging.basicConfig(format="%(message)s")

    logger = logging.getLogger("clean")
    logger.setLevel(logging.INFO)
    logger.info("Clean message without metadata")
    logger.warning("Warning: Clean format warning")
    logger.error("Error: Something went wrong")
    logging.flush()  # Ensure all log messages are processed
    print()


def main():
    """Run comprehensive formatting tests and examples"""
    print("🚀 Testing logxide formatting capabilities\n")

    # Run all test functions
    test_default_format()
    test_simple_format()
    test_detailed_format()
    test_json_format()
    test_debug_format()
    test_multithreaded_format()
    test_production_format()
    test_minimal_format()


if __name__ == "__main__":
    main()
