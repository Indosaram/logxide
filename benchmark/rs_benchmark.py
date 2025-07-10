import threading
import time
from datetime import datetime

from logxide import logging

MESSAGE = (
    "This is a test message to benchmark passing a string from Python to Rust. "
    "It contains approximately 200 characters to simulate a realistic use case."
)
DURATION = 10  # Duration in seconds for the benchmark


def cpu_intensive_task(stop_event):
    n = 1000
    while not stop_event.is_set():
        result = 1
        for i in range(1, n + 1):
            result *= i


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    rust_logger = logging.getLogger()
    stop_event = threading.Event()
    background_thread = threading.Thread(target=cpu_intensive_task, args=(stop_event,))
    background_thread.start()

    print(f"Running Rust benchmark for {DURATION} seconds")
    start_time = time.time()
    rust_count = 0
    while time.time() - start_time < DURATION:
        rust_logger.info(f"[Rs]: {MESSAGE}")
        rust_count += 1

    print(f"Rust benchmark emitted {rust_count} logs in {DURATION} seconds")

    stop_event.set()
    background_thread.join()

    current_time = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    result_file_name = f"benchmark_results_{current_time}.txt"
    with open(result_file_name, "a") as result_file:
        result_file.write(
            f"Rust benchmark emitted {rust_count} logs in {DURATION} seconds\n"
        )


if __name__ == "__main__":
    main()
