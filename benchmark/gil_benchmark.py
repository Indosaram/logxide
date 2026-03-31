import contextlib
import logging as std_logging
import os
import tempfile
import threading
import time

from logxide import logging as lx_logging


def logging_task(logger, num_messages, thread_id):
    """Log messages rapidly inside a worker thread."""
    for i in range(num_messages):
        logger.info(f"[Thread-{thread_id}] Processing request {i}")


def run_throughput_benchmark(logger_mod, name):
    print(f"--- Running Throughput Benchmark for {name} ---")

    fd, temp_path = tempfile.mkstemp(suffix=".log")
    os.close(fd)

    logger = logger_mod.getLogger(f"bench_{name}")
    logger.setLevel(logger_mod.INFO)
    for h in list(logger.handlers):
        logger.removeHandler(h)

    if name == "LogXide":
        handler = logger_mod.FileHandler(temp_path)
    else:
        handler = logger_mod.FileHandler(temp_path)
        formatter = logger_mod.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)

    logger.addHandler(handler)

    TOTAL = 100_000
    start_time = time.perf_counter()

    for i in range(TOTAL):
        logger.info(f"Processing sequential request {i} to test throughput.")

    duration = time.perf_counter() - start_time
    throughput = TOTAL / max(duration, 0.001)

    for h in list(logger.handlers):
        logger.removeHandler(h)
        if hasattr(h, "close"):
            h.close()
    with contextlib.suppress(OSError):
        os.remove(temp_path)

    print(f"Total Time: {duration:.4f}s for {TOTAL:,} msgs")
    print(f"Throughput: {throughput:,.0f} msgs/sec\n")

    return throughput, duration


if __name__ == "__main__":
    print("Warming up benchmark...")
    time.sleep(0.5)

    std_throughput, std_time = run_throughput_benchmark(std_logging, "Stdlib")
    lx_throughput, lx_time = run_throughput_benchmark(lx_logging, "LogXide")

    print("=== Conclusion ===")
    speedup = lx_throughput / max(std_throughput, 1)
    print(f"LogXide sustains {speedup:.1f}x higher throughput.")
