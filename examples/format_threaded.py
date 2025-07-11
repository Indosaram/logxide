import threading
import time

from logxide import logging

print("=== Multi-threaded Logging ===")
thread_format = (
    "[%(asctime)s] %(threadName)-10s | %(name)-15s | %(levelname)-8s | %(message)s"
)
logging.basicConfig(format=thread_format, datefmt="%H:%M:%S")


def worker(worker_id):
    # Set thread name
    threading.current_thread().name = f"Worker-{worker_id}"

    logger = logging.getLogger(f"worker.{worker_id}")
    logger.setLevel(logging.INFO)

    for i in range(3):
        logger.info(f"Processing task {i + 1}")
        time.sleep(0.1)  # Simulate work

    logger.info("Worker completed all tasks")


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
