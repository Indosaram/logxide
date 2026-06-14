#!/usr/bin/env python3
from __future__ import annotations

import gc
import json
import os
import statistics
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

ITERATIONS = 200_000
WARMUP = 5_000
RUNS = 5


def configure_file_handler_with_format(log_file: str):
    from logxide import logxide as lx

    lx.logging.clear_handlers()
    lx.logging.register_file_handler(
        log_file,
        20,
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        None,
    )
    logger = lx.logging.getLogger(f"micro_file_{time.time_ns()}")
    logger.setLevel(20)
    return logger


def configure_memory_handler():
    from logxide import logxide as lx

    logger = lx.logging.getLogger(f"micro_mem_{time.time_ns()}")
    while hasattr(logger, "handlers") and logger.handlers:
        logger.removeHandler(logger.handlers[0])
    logger.propagate = False
    handler = lx.logging.MemoryHandler()
    logger.addHandler(handler)
    logger.setLevel(20)
    return logger, handler


def configure_filtered_logger():
    from logxide import logxide as lx

    logger = lx.logging.getLogger(f"micro_filtered_{time.time_ns()}")
    while hasattr(logger, "handlers") and logger.handlers:
        logger.removeHandler(logger.handlers[0])
    logger.propagate = False
    logger.addHandler(lx.logging.MemoryHandler())
    logger.setLevel(30)
    return logger


def bench(fn, iterations: int, warmup: int, runs: int) -> dict:
    for _ in range(warmup):
        fn()
    times = []
    for _ in range(runs):
        gc.collect()
        gc.disable()
        t0 = time.perf_counter()
        for _ in range(iterations):
            fn()
        elapsed = time.perf_counter() - t0
        gc.enable()
        times.append(elapsed)
    mean = statistics.mean(times)
    return {
        "mean_s": mean,
        "min_s": min(times),
        "max_s": max(times),
        "std_s": statistics.stdev(times) if len(times) > 1 else 0.0,
        "ops_per_sec": iterations / mean,
        "iterations": iterations,
        "runs": runs,
    }


def bench_threaded(setup_fn, iterations: int, num_threads: int, runs: int) -> dict:
    times = []
    per_thread = iterations // num_threads
    for _ in range(runs):
        logger = setup_fn()
        gc.collect()
        gc.disable()
        barrier = threading.Barrier(num_threads + 1)

        def worker(logger=logger, barrier=barrier, per_thread=per_thread):
            barrier.wait()
            for _ in range(per_thread):
                logger.info("threaded message")

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        barrier.wait()
        t0 = time.perf_counter()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - t0
        gc.enable()
        times.append(elapsed)
        try:
            from logxide import logxide as lx

            lx.logging.flush()
        except Exception:
            pass
    mean = statistics.mean(times)
    return {
        "mean_s": mean,
        "min_s": min(times),
        "max_s": max(times),
        "std_s": statistics.stdev(times) if len(times) > 1 else 0.0,
        "ops_per_sec": iterations / mean,
        "iterations": iterations,
        "runs": runs,
        "threads": num_threads,
    }


def run_scenario_file_handler_info(results):
    with tempfile.TemporaryDirectory() as td:
        log_file = os.path.join(td, "bench.log")
        logger = configure_file_handler_with_format(log_file)

        def info_call():
            logger.info("hello world from the bench")

        r = bench(info_call, ITERATIONS, WARMUP, RUNS)
        from logxide import logxide as lx

        lx.logging.flush()
        results["scenarios"]["file_handler_info"] = r
        print(
            f"FileHandler info()+fmt     : {r['ops_per_sec']:>14,.0f} ops/s "
            f"(mean {r['mean_s']:.4f}s ± {r['std_s']:.4f}s)"
        )


def run_scenario_memory_info(results):
    logger, handler = configure_memory_handler()

    def info_call_mem():
        logger.info("hello memory")

    r = bench(info_call_mem, ITERATIONS, WARMUP, RUNS)
    results["scenarios"]["memory_handler_info"] = r
    print(
        f"MemoryHandler info()       : {r['ops_per_sec']:>14,.0f} ops/s "
        f"(mean {r['mean_s']:.4f}s ± {r['std_s']:.4f}s)"
    )
    handler.clear()


def run_scenario_filtered_debug(results):
    logger = configure_filtered_logger()

    def debug_call():
        logger.debug("filtered out")

    r = bench(debug_call, ITERATIONS, WARMUP, RUNS)
    results["scenarios"]["filtered_debug"] = r
    print(
        f"Filtered debug() (NOOP)    : {r['ops_per_sec']:>14,.0f} ops/s "
        f"(mean {r['mean_s']:.4f}s ± {r['std_s']:.4f}s)"
    )


def run_scenario_info_with_args(results):
    logger, handler = configure_memory_handler()

    def info_args_call():
        logger.info("user %s did %s", "alice", "login")

    r = bench(info_args_call, ITERATIONS, WARMUP, RUNS)
    results["scenarios"]["info_with_args"] = r
    print(
        f"info() with %s args        : {r['ops_per_sec']:>14,.0f} ops/s "
        f"(mean {r['mean_s']:.4f}s ± {r['std_s']:.4f}s)"
    )
    handler.clear()


def run_scenario_threaded(results):
    with tempfile.TemporaryDirectory() as td:
        log_file = os.path.join(td, "bench_thread.log")

        def setup_t():
            return configure_file_handler_with_format(log_file)

        r = bench_threaded(setup_t, 100_000, num_threads=4, runs=3)
        results["scenarios"]["file_handler_threaded_4"] = r
        print(
            f"FileHandler 4 threads      : {r['ops_per_sec']:>14,.0f} ops/s "
            f"(mean {r['mean_s']:.4f}s ± {r['std_s']:.4f}s)"
        )


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "unlabeled"
    results = {
        "label": label,
        "timestamp": datetime.now().isoformat(),
        "iterations": ITERATIONS,
        "warmup": WARMUP,
        "runs": RUNS,
        "scenarios": {},
    }

    print(f"\n{'=' * 72}")
    print(f"logxide perf micro — label: {label}")
    print(f"  iter={ITERATIONS}  warmup={WARMUP}  runs={RUNS}")
    print(f"{'=' * 72}\n")

    run_scenario_file_handler_info(results)
    run_scenario_memory_info(results)
    run_scenario_filtered_debug(results)
    run_scenario_info_with_args(results)
    run_scenario_threaded(results)

    out_dir = Path(__file__).parent / "perf_results"
    out_dir.mkdir(exist_ok=True)
    out_file = (
        out_dir / f"micro_{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    out_file.write_text(json.dumps(results, indent=2))
    print(f"\nResults: {out_file}")


if __name__ == "__main__":
    main()
