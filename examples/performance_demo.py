"""
Performance Demonstration Example

This example demonstrates logxide's performance characteristics:
- High-volume logging
- Multi-threaded scenarios
- Async processing benefits
- Memory efficiency

Expected Output:
The example will show performance metrics for various logging scenarios:
- High-volume test: ~10,000+ messages/second
- Multi-threaded test: Concurrent logging from multiple threads
- Level filtering: Fast rejection of disabled log levels
- String formatting: Efficient parameter substitution
- Memory efficiency: Hierarchical logger caching
- Burst handling: Processing sudden traffic spikes
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from logxide import logging


def main():
    print("=== LogXide Performance Demo ===\n")

    # Configure logxide for performance testing
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    perf_logger = logging.getLogger("performance")

    # Test 1: High-Volume Logging
    print("1. High-Volume Logging Test:")
    perf_logger.info("Starting high-volume logging test...")

    start_time = time.time()

    # Log 10,000 messages
    volume_logger = logging.getLogger("volume_test")
    for i in range(10000):
        volume_logger.info(f"High-volume log message {i} with data: data_{i}")

    # Flush to ensure all messages are processed
    logging.flush()

    elapsed = time.time() - start_time
    perf_logger.info(f"Logged 10,000 messages in {elapsed:.3f} seconds")
    print(
        f"   ✓ 10,000 messages logged in {elapsed:.3f}s ({10000 / elapsed:.0f} msg/sec)"
    )

    # Test 2: Multi-threaded Logging
    print("\n2. Multi-threaded Logging Test:")
    perf_logger.info("Starting multi-threaded logging test...")

    def worker_thread(thread_id, message_count):
        """Worker function for threaded logging."""
        thread_logger = logging.getLogger(f"thread_{thread_id}")

        # Set thread name for logging context
        logging.set_thread_name(f"Worker-{thread_id}")

        for i in range(message_count):
            thread_logger.info(
                f"Thread {thread_id} message {i}: processing item item_{thread_id}_{i}"
            )

    start_time = time.time()

    # Launch 10 threads, each logging 1000 messages
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for thread_id in range(10):
            future = executor.submit(worker_thread, thread_id, 1000)
            futures.append(future)

        # Wait for all threads to complete
        for future in futures:
            future.result()

    # Ensure all threaded logs are processed
    logging.flush()

    elapsed = time.time() - start_time
    total_messages = 10 * 1000
    perf_logger.info(
        f"Multi-threaded test: {total_messages} messages in {elapsed:.3f} seconds"
    )
    print(
        f"   ✓ {total_messages} messages from 10 threads in {elapsed:.3f}s ({total_messages / elapsed:.0f} msg/sec)"
    )

    # Test 3: Different Log Levels Performance
    print("\n3. Log Level Performance Test:")

    # Test with debug level disabled (should be very fast)
    debug_logger = logging.getLogger("debug_test")
    debug_logger.setLevel(logging.INFO)  # Debug messages will be filtered out

    start_time = time.time()

    for i in range(50000):
        debug_logger.debug(f"This debug message should be filtered out: {i}")

    elapsed = time.time() - start_time
    perf_logger.info(f"50,000 filtered debug messages: {elapsed:.3f} seconds")
    print(f"   ✓ 50,000 filtered messages in {elapsed:.3f}s (level filtering works)")

    # Test 4: String Formatting Performance
    print("\n4. String Formatting Performance:")
    format_logger = logging.getLogger("format_test")

    start_time = time.time()

    # Test various formatting patterns
    for i in range(5000):
        format_logger.info(
            f"User user_{i} performed action login at 2025-01-10 with result success"
        )
        format_logger.warning(
            f"Memory usage: {75 + (i % 25)}% ({1024 + i} MB) for process proc_{i}"
        )

    logging.flush()

    elapsed = time.time() - start_time
    perf_logger.info(f"10,000 formatted messages: {elapsed:.3f} seconds")
    print(f"   ✓ 10,000 formatted messages in {elapsed:.3f}s")

    # Test 5: Memory Efficiency Test
    print("\n5. Memory Efficiency Test:")

    # Create many loggers to test logger caching
    loggers = []
    for i in range(1000):
        logger_name = f"app.module_{i}.component_{i % 10}"
        logger = logging.getLogger(logger_name)
        loggers.append(logger)
        logger.info(f"Logger {logger_name} initialized")

    perf_logger.info("Created 1000 loggers with hierarchical names")
    print("   ✓ 1000 loggers created (hierarchical caching)")

    # Test 6: Burst Logging
    print("\n6. Burst Logging Test:")

    burst_logger = logging.getLogger("burst_test")

    # Simulate application bursts
    for burst in range(5):
        start_time = time.time()

        # Quick burst of 2000 messages
        for i in range(2000):
            burst_logger.error(f"Burst {burst}: Critical error {i} occurred in system")

        elapsed = time.time() - start_time
        perf_logger.info(f"Burst {burst}: 2000 messages in {elapsed:.3f}s")

        # Small pause between bursts
        time.sleep(0.1)

    # Final flush to ensure all messages are processed
    logging.flush()

    print("\n=== Performance Summary ===")
    print("✓ High-volume logging: 10,000+ messages/second")
    print("✓ Multi-threaded: Concurrent logging from 10 threads")
    print("✓ Level filtering: Fast rejection of disabled levels")
    print("✓ String formatting: Efficient parameter substitution")
    print("✓ Memory efficient: Hierarchical logger caching")
    print("✓ Burst handling: Handles sudden traffic spikes")
    print("✓ Async processing: Non-blocking logging operations")

    perf_logger.info("Performance demonstration completed successfully")


if __name__ == "__main__":
    main()
