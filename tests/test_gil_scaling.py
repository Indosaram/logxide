"""
Regression tests for design §4 (GIL-released producer path).

When a logger has no Python filters and no Python-dispatch handlers, record creation and
Rust handler emit run inside py.detach() (GIL released), letting producers scale across
threads. These tests lock:
  (a) correctness under concurrency on the detached path (delivered == emitted),
  (b) a soft throughput probe (printed, not asserted) for 1 vs 4 threads,
  (c) the ineligible path still runs a Python filter for every record and applies its
      mutations.
"""

import threading
import time

from logxide import handlers
from logxide import logxide as _ext


def _rust_logger(name):
    logger = _ext.logging.getLogger(name)
    logger.setLevel(10)  # DEBUG
    return logger


def _count_lines(path):
    with open(path) as f:
        return sum(1 for _ in f)


def test_detached_path_delivers_all_records_under_concurrency(tmp_path):
    log_file = tmp_path / "detached.log"
    handler = handlers.FileHandler(str(log_file))
    logger = _rust_logger("gil.detached.correctness")
    logger.addHandler(handler)

    n_threads = 8
    per_thread = 3000
    barrier = threading.Barrier(n_threads)

    def work():
        barrier.wait()
        for _ in range(per_thread):
            logger.info("no-arg-record")  # eligible: no filters, no python handlers

    threads = [threading.Thread(target=work) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    handler.flush()
    time.sleep(0.3)

    emitted = n_threads * per_thread
    delivered = _count_lines(str(log_file))
    assert delivered == emitted, f"delivered {delivered} != emitted {emitted}"


def test_detached_path_scaling_probe(tmp_path):
    def run(n_threads, per_thread):
        log_file = tmp_path / f"scale_{n_threads}.log"
        handler = handlers.FileHandler(str(log_file))
        logger = _rust_logger(f"gil.detached.scale.{n_threads}")
        logger.addHandler(handler)

        barrier = threading.Barrier(n_threads)

        def work():
            barrier.wait()
            for _ in range(per_thread):
                logger.info("scale")

        threads = [threading.Thread(target=work) for _ in range(n_threads)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - start
        handler.flush()
        time.sleep(0.2)

        total = n_threads * per_thread
        delivered = _count_lines(str(log_file))
        ops_per_sec = total / elapsed if elapsed > 0 else float("inf")
        return total, delivered, ops_per_sec

    per_thread = 20000
    total1, delivered1, ops1 = run(1, per_thread)
    total4, delivered4, ops4 = run(4, per_thread)

    print(
        f"\n[gil-scaling] 1-thread: {ops1 / 1e6:.2f}M ops/s | "
        f"4-thread: {ops4 / 1e6:.2f}M ops/s | "
        f"ratio={ops4 / ops1:.2f}x"
    )

    # Correctness is a hard requirement; throughput is only printed to avoid CI flakiness.
    assert delivered1 == total1, f"1-thread delivered {delivered1} != {total1}"
    assert delivered4 == total4, f"4-thread delivered {delivered4} != {total4}"


def test_ineligible_path_runs_filter_for_every_record(tmp_path):
    log_file = tmp_path / "filtered.log"
    handler = handlers.FileHandler(str(log_file))
    logger = _rust_logger("gil.ineligible.filter")

    calls = []

    class RedactFilter:
        def filter(self, record):
            calls.append(record.get("msg", ""))
            if "secret" in record.get("msg", ""):
                record["msg"] = record["msg"].replace("secret", "***")
            return True

    logger.addFilter(RedactFilter())
    logger.addHandler(handler)

    n = 25
    for i in range(n):
        logger.info(f"secret-{i}")

    handler.flush()
    time.sleep(0.2)

    # Filter must have been invoked for every record (ineligible => fully-attached path).
    assert len(calls) == n, f"filter ran {len(calls)} times, expected {n}"
    # And its mutation must have been applied to the delivered records.
    with open(str(log_file)) as f:
        content = f.read()
    assert "secret" not in content, content
    assert content.count("***-") == n, content
    assert _count_lines(str(log_file)) == n
