import logging
import sys
import threading
import time
from datetime import datetime
from logging import (
    Filter,
    Formatter,
    Handler,
    LogRecord,
    StreamHandler,
)

MESSAGE = (
    "This is a test message to benchmark passing a string from Python to Rust. "
    "It contains approximately 200 characters to simulate a realistic use case."
)

DURATION = 10  # Duration in seconds for each benchmark
NUM_THREADS = 100


def cpu_intensive_task(stop_event):
    n = 1000
    while not stop_event.is_set():
        result = 1
        for i in range(1, n + 1):
            result *= i


class CustomFilter(Filter):
    def filter(self, record: LogRecord) -> LogRecord:
        record.msg = record.msg.replace("benchmark", "random")
        return record


def benchmark_python(stop_event, logger):
    while not stop_event.is_set():
        logger.info(f"[Py]: {MESSAGE}")


if __name__ == "__main__":
    # --- Python Benchmark ---
    root_logger = logging.getLogger("python_benchmark")
    console_handler: Handler = logging.FileHandler("python.log")
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        Formatter(
            "%(asctime)s - %(process)d %(threadName)s %(name)s %(levelname)s %(message)s"
        )
    )
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.INFO)
    root_logger.addFilter(CustomFilter())

    stderr_handler = StreamHandler(stream=sys.stderr)
    root_logger.addHandler(stderr_handler)

    stop_event = threading.Event()
    background_thread = threading.Thread(target=cpu_intensive_task, args=(stop_event,))
    python_threads = [
        threading.Thread(target=benchmark_python, args=(stop_event, root_logger))
        for _ in range(NUM_THREADS)
    ]

    background_thread.start()
    start_time = time.time()
    for thread in python_threads:
        thread.start()

    while time.time() - start_time < DURATION:
        time.sleep(0.1)

    stop_event.set()
    for thread in python_threads:
        thread.join()
    background_thread.join()
    time.sleep(5)

    with open("python.log") as python_log:
        total_logs_python = len(python_log.readlines())

    print(
        f"Python benchmark with NUM_THREADS={NUM_THREADS} emitted {total_logs_python} logs in {DURATION} seconds"
    )

    current_time = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    result_file_name = f"python_benchmark_results_{current_time}.txt"
    with open(result_file_name, "a") as result_file:
        result_file.write(
            f"Python benchmark with NUM_THREADS={NUM_THREADS} emitted {total_logs_python} logs in {DURATION} seconds\n"
        )
