#!/usr/bin/env python3
"""
logxide producer micro-benchmarks with per-scenario process isolation.

Rewritten to fix defect 6 of docs/performance-bottleneck-report-2026-07-13.md
section 5: the previous version registered a fresh MemoryHandler in the SAME
process for every scenario, so (because of bottleneck P0-1, which dispatches a
Python ``handle()`` for every globally-registered handler) later scenarios paid
an ever-growing dispatch cost. Here every scenario runs in its OWN fresh
subprocess and clears handlers before measuring, so scenarios cannot
contaminate each other.

Each scenario also VERIFIES its sink:
  * file / threaded  -> number of lines written == emitted
  * memory / args    -> len(MemoryHandler.records) == emitted
  * filtered (NOOP)  -> len(records) == 0 (nothing should reach the handler)

We report producer throughput (ops/s) AND durable throughput (sink-confirmed /
total time incl. flush) AND producer latency p50/p95/p99, following the
measurement rigor of report section 7 (warmup, GC disabled during timing).

Usage:
    python benchmark/perf_micro.py -n 20000
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _bench_common import (  # noqa: E402
    LatencyStats,
    ScenarioResult,
    count_lines,
    emit_result,
    measure_calls,
    run_worker,
    wait_until_count,
)

THIS = os.path.abspath(__file__)
FMT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

SCENARIOS = [
    "file_info",
    "memory_info",
    "filtered_debug",
    "info_args",
    "threaded_file",
]
SCENARIO_LABELS = {
    "file_info": "FileHandler info()+fmt",
    "memory_info": "MemoryHandler info()",
    "filtered_debug": "Filtered debug() (NOOP)",
    "info_args": "info() with %s args",
    "threaded_file": "FileHandler 4 threads",
}


# ========================================================================== #
# WORKER SIDE
# ========================================================================== #
def worker_main(args: argparse.Namespace) -> int:
    scenario = args.scenario
    n = args.iterations
    warmup = args.warmup
    result = ScenarioResult(library="logxide", scenario=scenario, iterations=n)
    try:
        _dispatch(result, scenario, n, warmup, args.runs, args.threads)
    except Exception as e:  # noqa: BLE001
        import traceback

        result.ok = False
        result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-600:]}"
    emit_result(result)
    return 0


def _clear(logger) -> None:
    while getattr(logger, "handlers", None):
        logger.removeHandler(logger.handlers[0])


def _dispatch(
    result: ScenarioResult, scenario: str, n: int, warmup: int, runs: int, threads: int
) -> None:
    from logxide import logxide as lx

    lx.logging.clear_handlers()

    if scenario == "file_info":
        tmpdir = tempfile.mkdtemp(prefix="pm_file_")
        log_file = os.path.join(tmpdir, "bench.log")
        lx.logging.register_file_handler(log_file, 20, FMT, None)
        logger = lx.logging.getLogger(f"micro_file_{time.time_ns()}")
        logger.setLevel(20)
        _timed_gcoff(
            result,
            lambda i: logger.info("hello world from the bench"),
            n,
            warmup,
            flush=lx.logging.flush,
            counter=lambda: count_lines(log_file),
            expected=n,
        )

    elif scenario == "memory_info":
        logger, handler = _fresh_memory_logger(lx)
        _timed_gcoff(
            result,
            lambda i: logger.info("hello memory"),
            n,
            warmup,
            flush=lx.logging.flush,
            counter=lambda: len(handler.records),
            expected=n,
            reset=handler.clear,
        )

    elif scenario == "info_args":
        logger, handler = _fresh_memory_logger(lx)
        _timed_gcoff(
            result,
            lambda i: logger.info("user %s did %s", "alice", "login"),
            n,
            warmup,
            flush=lx.logging.flush,
            counter=lambda: len(handler.records),
            expected=n,
            reset=handler.clear,
        )

    elif scenario == "filtered_debug":
        logger, handler = _fresh_memory_logger(lx, level=30)
        _timed_gcoff(
            result,
            lambda i: logger.debug("filtered out"),
            n,
            warmup,
            flush=lx.logging.flush,
            counter=lambda: len(handler.records),
            expected=0,
            reset=handler.clear,
        )

    elif scenario == "threaded_file":
        _run_threaded(result, lx, n, threads, runs)

    else:
        result.ok = False
        result.error = f"unknown scenario {scenario}"


def _fresh_memory_logger(lx, level: int = 20):
    logger = lx.logging.getLogger(f"micro_mem_{time.time_ns()}")
    _clear(logger)
    logger.propagate = False
    handler = lx.MemoryHandler()
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger, handler


def _timed_gcoff(result, call, n, warmup, flush, counter, expected, reset=None) -> None:
    """Single measured run with GC disabled during the timed loop.

    Warmup records are excluded from sink verification: either the handler is
    reset to a known-zero baseline (``reset``), or we wait for the warmup
    records to drain and snapshot that as the baseline.
    """
    for i in range(warmup):
        call(i)
    flush()
    if reset is not None:
        reset()
        baseline = 0
    else:
        wait_until_count(counter, warmup, timeout=5.0)
        baseline = counter()
    gc.collect()
    gc.disable()
    try:
        t_total0 = time.perf_counter()
        producer_elapsed, lat = measure_calls(call, n, warmup=0)
        flush()
        confirmed = wait_until_count(counter, baseline + expected) - baseline
        total_elapsed = time.perf_counter() - t_total0
    finally:
        gc.enable()
    result.producer_elapsed_s = producer_elapsed
    result.total_elapsed_s = total_elapsed
    result.latency = LatencyStats.from_samples(lat)
    result.sink_expected = expected
    result.sink_confirmed = confirmed
    result.ok = True


def _run_threaded(result, lx, n, threads, runs) -> None:
    tmpdir = tempfile.mkdtemp(prefix="pm_thr_")
    log_file = os.path.join(tmpdir, "bench_thread.log")
    lx.logging.clear_handlers()
    lx.logging.register_file_handler(log_file, 20, FMT, None)
    logger = lx.logging.getLogger(f"micro_thr_{time.time_ns()}")
    logger.setLevel(20)

    per_thread = n // threads
    total = per_thread * threads
    gc.collect()
    gc.disable()
    try:
        barrier = threading.Barrier(threads + 1)

        def work():
            barrier.wait()
            for _ in range(per_thread):
                logger.info("threaded message")

        ts = [threading.Thread(target=work) for _ in range(threads)]
        for t in ts:
            t.start()
        barrier.wait()
        t0 = time.perf_counter()
        for t in ts:
            t.join()
        producer_elapsed = time.perf_counter() - t0
        lx.logging.flush()
        confirmed = wait_until_count(lambda: count_lines(log_file), total)
        total_elapsed = time.perf_counter() - t0
    finally:
        gc.enable()
    result.iterations = total
    result.producer_elapsed_s = producer_elapsed
    result.total_elapsed_s = total_elapsed
    result.sink_expected = total
    result.sink_confirmed = confirmed
    result.metrics = {"threads": threads}
    result.ok = True


# ========================================================================== #
# ORCHESTRATOR SIDE
# ========================================================================== #
def orchestrator_main(args: argparse.Namespace) -> int:
    print("=" * 78)
    print("logxide perf micro — per-scenario subprocess isolation")
    print("=" * 78)
    print(f"iterations={args.iterations:,}  warmup={args.warmup:,}  runs={args.runs}")
    print("Each scenario runs in a fresh process (no handler accumulation).")
    print("Throughput reported as DURABLE (sink-confirmed / total time incl. flush).")
    print("=" * 78)

    results: list[ScenarioResult] = []
    for scenario in SCENARIOS:
        extra = ["--runs", str(args.runs)]
        if scenario == "threaded_file":
            extra += ["--threads", str(args.threads)]
        r = run_worker(
            THIS,
            "logxide",
            scenario,
            args.iterations,
            args.warmup,
            extra_args=extra,
            timeout=args.timeout,
        )
        results.append(r)
        _print_line(r)

    _print_table(results)
    _save(results, args)
    print("\nNumbers are machine-specific; see benchmark/README.md.")
    return 0


def _print_line(r: ScenarioResult) -> None:
    label = SCENARIO_LABELS.get(r.scenario, r.scenario)
    if not r.ok:
        print(f"  {label:<26} ERROR ({(r.error or '').splitlines()[0][:60]})")
        return
    verify = "OK" if r.sink_confirmed == r.sink_expected else "MISMATCH"
    print(
        f"  {label:<26} producer={r.producer_throughput:>12,.0f} ops/s  "
        f"durable={r.durable_throughput:>12,.0f} rec/s  "
        f"sink={r.sink_confirmed}/{r.sink_expected} [{verify}]"
    )


def _print_table(results: list[ScenarioResult]) -> None:
    print("\n" + "=" * 78)
    print("SUMMARY  (producer ops/s, durable rec/s, producer latency ns, sink verify)")
    print("=" * 78)
    print(
        f"{'Scenario':<26}{'producer/s':>13}{'durable/s':>13}"
        f"{'p50':>9}{'p99':>9}{'sink':>14}{'verify':>10}"
    )
    print("-" * 94)
    for r in results:
        if not r.ok:
            print(f"{SCENARIO_LABELS.get(r.scenario, r.scenario):<26}  ERROR")
            continue
        verify = "OK" if r.sink_confirmed == r.sink_expected else "MISMATCH"
        print(
            f"{SCENARIO_LABELS.get(r.scenario, r.scenario):<26}"
            f"{r.producer_throughput:>13,.0f}{r.durable_throughput:>13,.0f}"
            f"{r.latency.p50_ns:>9,.0f}{r.latency.p99_ns:>9,.0f}"
            f"{f'{r.sink_confirmed}/{r.sink_expected}':>14}{verify:>10}"
        )


def _save(results: list[ScenarioResult], args: argparse.Namespace) -> None:
    out_dir = Path(THIS).parent / "perf_results"
    out_dir.mkdir(exist_ok=True)
    payload = {
        "label": args.label,
        "timestamp": datetime.now().isoformat(),
        "iterations": args.iterations,
        "warmup": args.warmup,
        "runs": args.runs,
        "scenarios": {r.scenario: json.loads(r.to_json()) for r in results},
    }
    out_file = (
        out_dir / f"micro_{args.label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    out_file.write_text(json.dumps(payload, indent=2))
    print(f"\nResults: {out_file}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-n",
        "--iterations",
        type=int,
        default=20_000,
        help="calls per scenario (default: 20000; keep small for quick runs)",
    )
    parser.add_argument("-w", "--warmup", type=int, default=2_000)
    parser.add_argument("-r", "--runs", type=int, default=1)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--label", default="unlabeled")
    parser.add_argument("--timeout", type=float, default=300.0)
    # worker plumbing
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--library", default="logxide", help=argparse.SUPPRESS)
    parser.add_argument("--scenario", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker:
        return worker_main(args)
    return orchestrator_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
