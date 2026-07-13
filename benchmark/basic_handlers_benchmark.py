#!/usr/bin/env python3
"""
Credibility-corrected basic-handlers benchmark for logxide and peers.

This is a full rewrite that fixes the seven benchmark defects catalogued in
``docs/performance-bottleneck-report-2026-07-13.md`` section 5. See
``benchmark/README.md`` for the methodology and its rationale. In short:

* Defect 1 (cross-contamination): every (library, scenario) pair runs in its
  OWN fresh subprocess. The stdlib / structlog workers NEVER import logxide, so
  logxide's monkey-patching of ``logging.getLogger``/``basicConfig`` cannot
  contaminate the baseline.
* Defect 2 (closed devnull): stream sinks are captured with a real file that
  stays open for the handler's whole lifetime (no ``with open(...) : pass``).
* Defect 3 (no sink verification): after every run we count the records the
  sink actually received and report **durable throughput** = confirmed / time.
  Async handlers additionally report emitted / sink_acknowledged /
  queue_dropped / delivery_failed / in_flight and assert the accounting
  identity.
* Defect 4 (uncontrolled Rust stderr): logxide StreamHandler output is captured
  by redirecting the OS-level stdout file descriptor to a real file, not by
  swapping Python's ``sys.stderr`` object.
* Defect 5 (fake rotation): the logxide rotating scenario uses a real
  ``RotatingFileHandler`` with a real filename and verifies that rotation
  happened (rotated files, retained line count, total bytes).
* Defect 6 (handler accumulation): each scenario is a brand-new process with a
  fresh logger; handlers are explicitly cleared.
* Defect 7 (reporting): separate "durable throughput" and "producer latency"
  (p50/p95/p99) tables, sync vs async split, full async accounting.

Usage (orchestrator):
    python benchmark/basic_handlers_benchmark.py -n 2000

Optional libraries (loguru / logbook / structlog / picologging) are skipped
cleanly when not installed. logxide + stdlib always run.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _bench_common import (  # noqa: E402
    LatencyStats,
    RedirectedFD,
    ScenarioResult,
    count_lines,
    emit_result,
    measure_calls,
    run_worker,
    wait_until_count,
)

THIS = os.path.abspath(__file__)

FMT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Sync handler scenarios run for every library.
SYNC_SCENARIOS = ["file", "stream", "rotating"]

# Async scenarios are logxide-only (queueing handlers with delivery accounting).
ASYNC_SCENARIOS = ["http_block", "http_drop"]

# Library id -> human label. "python" == stdlib logging (baseline, no logxide).
LIBRARIES = ["python", "logxide", "loguru", "logbook", "structlog", "picologging"]
LABELS = {
    "python": "Python logging",
    "logxide": "LogXide",
    "loguru": "Loguru",
    "logbook": "Logbook",
    "structlog": "Structlog",
    "picologging": "Picologging",
}


# ========================================================================== #
# WORKER SIDE  (runs in an isolated subprocess; imports only what it needs)
# ========================================================================== #
def worker_main(args: argparse.Namespace) -> int:
    library = args.library
    scenario = args.scenario
    n = args.iterations
    warmup = args.warmup

    result = ScenarioResult(library=library, scenario=scenario, iterations=n)

    try:
        if library == "logxide":
            _run_logxide(result, scenario, n, warmup)
        elif library == "python":
            _run_stdlib(result, scenario, n, warmup)
        elif library == "loguru":
            _run_loguru(result, scenario, n, warmup)
        elif library == "logbook":
            _run_logbook(result, scenario, n, warmup)
        elif library == "structlog":
            _run_structlog(result, scenario, n, warmup)
        elif library == "picologging":
            _run_picologging(result, scenario, n, warmup)
        else:
            result.error = f"unknown library {library}"
    except _SkipScenario as e:
        result.skipped = True
        result.error = str(e)
    except ImportError as e:
        result.skipped = True
        result.error = f"missing library: {e}"
    except Exception as e:  # noqa: BLE001
        import traceback

        result.ok = False
        result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-600:]}"

    emit_result(result)
    return 0


class _SkipScenario(Exception):
    """Raised when a (library, scenario) combination is not applicable."""


def _finish_sync(result: ScenarioResult, expected: int, confirmed: int) -> None:
    result.sink_expected = expected
    result.sink_confirmed = confirmed
    result.ok = True


# --- logxide ------------------------------------------------------------- #
def _run_logxide(result: ScenarioResult, scenario: str, n: int, warmup: int) -> None:
    # Importing logxide patches stdlib logging in this (isolated) process only.
    import logxide  # noqa: F401
    from logxide import logxide as lx

    tmpdir = tempfile.mkdtemp(prefix="lx_bench_")

    if scenario == "file":
        from logxide.handlers import FileHandler

        log_file = os.path.join(tmpdir, "logxide_file.log")
        logger = lx.logging.getLogger(f"lx_file_{time.time_ns()}")
        _clear(logger)
        logger.propagate = False
        handler = FileHandler(log_file)
        handler.setLevel(20)
        logger.addHandler(handler)
        logger.setLevel(20)

        t_total0 = time.perf_counter()
        producer_elapsed, lat = measure_calls(
            lambda i: logger.info("benchmark message %d", i), n, warmup
        )
        handler.flush()
        lx.logging.flush()
        expected = warmup + n
        confirmed = wait_until_count(lambda: count_lines(log_file), expected)
        result.total_elapsed_s = time.perf_counter() - t_total0
        result.producer_elapsed_s = producer_elapsed
        result.latency = LatencyStats.from_samples(lat)
        # warmup + n lines were written to the same file.
        _finish_sync(result, expected=expected, confirmed=confirmed)

    elif scenario == "stream":
        cap = os.path.join(tmpdir, "logxide_stream.out")
        with RedirectedFD(cap, "stdout"):
            lx.logging.clear_handlers()
            lx.logging.register_stream_handler("stdout", 20, "%(message)s", None)
            logger = lx.logging.getLogger(f"lx_stream_{time.time_ns()}")
            logger.setLevel(20)
            t_total0 = time.perf_counter()
            producer_elapsed, lat = measure_calls(
                lambda i: logger.info("benchmark message %d", i), n, warmup
            )
            lx.logging.flush()
            expected = warmup + n
            confirmed = wait_until_count(lambda: count_lines(cap), expected)
            total_elapsed = time.perf_counter() - t_total0
        result.total_elapsed_s = total_elapsed
        result.producer_elapsed_s = producer_elapsed
        result.latency = LatencyStats.from_samples(lat)
        _finish_sync(result, expected=expected, confirmed=confirmed)

    elif scenario == "rotating":
        from logxide.handlers import RotatingFileHandler

        log_file = os.path.join(tmpdir, "logxide_rot.log")
        max_bytes = 64 * 1024
        backup_count = 50  # large enough to retain everything at small n
        logger = lx.logging.getLogger(f"lx_rot_{time.time_ns()}")
        _clear(logger)
        logger.propagate = False
        handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count
        )
        handler.setLevel(20)
        logger.addHandler(handler)
        logger.setLevel(20)

        t_total0 = time.perf_counter()
        producer_elapsed, lat = measure_calls(
            lambda i: logger.info("benchmark message %d", i), n, warmup
        )
        handler.flush()
        lx.logging.flush()
        expected = warmup + n
        confirmed = wait_until_count(
            lambda: _verify_rotation(log_file + "*")["total_lines"], expected
        )
        result.total_elapsed_s = time.perf_counter() - t_total0
        result.producer_elapsed_s = producer_elapsed
        result.latency = LatencyStats.from_samples(lat)
        result.rotation = _verify_rotation(log_file + "*")
        _finish_sync(result, expected=expected, confirmed=confirmed)

    elif scenario in ("http_block", "http_drop"):
        _run_logxide_async(result, scenario, n, warmup)
    else:
        raise _SkipScenario(f"logxide has no scenario {scenario}")


def _run_logxide_async(
    result: ScenarioResult, scenario: str, n: int, warmup: int
) -> None:
    """Async HTTP handler: durable (block) vs lossy (drop_newest) accounting."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from logxide import logxide as lx

    received = {"n": 0}
    lock = threading.Lock()

    class _Sink(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("content-length", 0) or 0)
            self.rfile.read(length)
            time.sleep(0.002)  # slow sink so the queue saturates
            with lock:
                received["n"] += 1
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):  # silence
            return

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Sink)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    overflow = "block" if scenario == "http_block" else "drop_newest"
    handler = lx.HTTPHandler(
        f"http://127.0.0.1:{port}/",
        capacity=256,
        batch_size=1,
        flush_interval=60,
        overflow=overflow,
    )
    logger = lx.logging.getLogger(f"lx_{scenario}_{time.time_ns()}")
    _clear(logger)
    logger.propagate = False
    logger.addHandler(handler)
    logger.setLevel(20)

    result.is_async = True
    t_total0 = time.perf_counter()
    producer_elapsed, lat = measure_calls(
        lambda i: logger.info("item-%d", i), n, warmup=0
    )
    handler.flush()
    # Durability boundary: clock stops once nothing is in flight (drained).
    deadline = time.perf_counter() + 8.0
    while time.perf_counter() < deadline:
        m = handler.get_metrics()
        if m["in_flight"] == 0:
            break
        time.sleep(0.005)
    result.total_elapsed_s = time.perf_counter() - t_total0
    result.producer_elapsed_s = producer_elapsed
    result.latency = LatencyStats.from_samples(lat)

    metrics = handler.get_metrics()
    result.metrics = dict(metrics)
    result.metrics["server_received"] = received["n"]
    result.sink_expected = n
    result.sink_confirmed = metrics["sink_acknowledged"]
    # accounting identity after flush
    identity_ok = (
        metrics["emitted"]
        == metrics["sink_acknowledged"]
        + metrics["queue_dropped"]
        + metrics["delivery_failed"]
    ) and metrics["in_flight"] == 0
    result.metrics["identity_ok"] = identity_ok
    result.ok = True
    with contextlib.suppress(Exception):  # noqa: BLE001
        handler.shutdown()
    srv.shutdown()


def _clear(logger) -> None:
    while getattr(logger, "handlers", None):
        logger.removeHandler(logger.handlers[0])


def _verify_rotation(pattern: str) -> dict:
    import glob

    files = sorted(glob.glob(pattern))
    total_lines = 0
    total_bytes = 0
    per_file = []
    for f in files:
        lines = count_lines(f)
        size = os.path.getsize(f)
        total_lines += lines
        total_bytes += size
        per_file.append({"file": os.path.basename(f), "lines": lines, "bytes": size})
    return {
        "files": len(files),
        "rotations": max(0, len(files) - 1),
        "total_lines": total_lines,
        "total_bytes": total_bytes,
        "per_file": per_file,
    }


# --- stdlib logging (baseline; MUST NOT import logxide) ------------------- #
def _run_stdlib(result: ScenarioResult, scenario: str, n: int, warmup: int) -> None:
    import logging
    import logging.handlers

    assert "logxide" not in sys.modules, "stdlib worker must not import logxide"

    tmpdir = tempfile.mkdtemp(prefix="std_bench_")
    logger = logging.getLogger(f"std_{scenario}_{time.time_ns()}")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)

    if scenario == "file":
        log_file = os.path.join(tmpdir, "std_file.log")
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter(FMT))
        logger.addHandler(handler)
        t0 = time.perf_counter()
        producer_elapsed, lat = measure_calls(
            lambda i: logger.info("benchmark message %d", i), n, warmup
        )
        handler.flush()
        handler.close()
        result.total_elapsed_s = time.perf_counter() - t0
        result.producer_elapsed_s = producer_elapsed
        result.latency = LatencyStats.from_samples(lat)
        _finish_sync(result, expected=warmup + n, confirmed=count_lines(log_file))

    elif scenario == "stream":
        cap = os.path.join(tmpdir, "std_stream.out")
        stream = open(cap, "w")  # kept open for handler lifetime  # noqa: SIM115
        try:
            handler = logging.StreamHandler(stream)
            handler.setFormatter(logging.Formatter(FMT))
            logger.addHandler(handler)
            t0 = time.perf_counter()
            producer_elapsed, lat = measure_calls(
                lambda i: logger.info("benchmark message %d", i), n, warmup
            )
            handler.flush()
            stream.flush()
        finally:
            stream.close()
        result.total_elapsed_s = time.perf_counter() - t0
        result.producer_elapsed_s = producer_elapsed
        result.latency = LatencyStats.from_samples(lat)
        _finish_sync(result, expected=warmup + n, confirmed=count_lines(cap))

    elif scenario == "rotating":
        log_file = os.path.join(tmpdir, "std_rot.log")
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=64 * 1024, backupCount=50
        )
        handler.setFormatter(logging.Formatter(FMT))
        logger.addHandler(handler)
        t0 = time.perf_counter()
        producer_elapsed, lat = measure_calls(
            lambda i: logger.info("benchmark message %d", i), n, warmup
        )
        handler.flush()
        handler.close()
        result.total_elapsed_s = time.perf_counter() - t0
        result.producer_elapsed_s = producer_elapsed
        result.latency = LatencyStats.from_samples(lat)
        result.rotation = _verify_rotation(log_file + "*")
        _finish_sync(
            result, expected=warmup + n, confirmed=result.rotation["total_lines"]
        )
    else:
        raise _SkipScenario(f"stdlib has no scenario {scenario}")


# --- loguru -------------------------------------------------------------- #
def _run_loguru(result: ScenarioResult, scenario: str, n: int, warmup: int) -> None:
    from loguru import logger as log  # ImportError -> skipped

    tmpdir = tempfile.mkdtemp(prefix="loguru_bench_")
    fmt = "{time:YYYY-MM-DD HH:mm:ss} - {name} - {level} - {message}"

    if scenario == "file":
        log_file = os.path.join(tmpdir, "loguru_file.log")
        log.remove()
        sink_id = log.add(log_file, format=fmt)
        t0 = time.perf_counter()
        producer_elapsed, lat = measure_calls(
            lambda i: log.info("benchmark message {}", i), n, warmup
        )
        log.remove(sink_id)  # flushes and closes
        result.total_elapsed_s = time.perf_counter() - t0
        result.producer_elapsed_s = producer_elapsed
        result.latency = LatencyStats.from_samples(lat)
        _finish_sync(result, expected=warmup + n, confirmed=count_lines(log_file))

    elif scenario == "stream":
        cap = os.path.join(tmpdir, "loguru_stream.out")
        stream = open(cap, "w")  # noqa: SIM115
        try:
            log.remove()
            sink_id = log.add(stream, format=fmt)
            t0 = time.perf_counter()
            producer_elapsed, lat = measure_calls(
                lambda i: log.info("benchmark message {}", i), n, warmup
            )
            log.remove(sink_id)
            stream.flush()
        finally:
            stream.close()
        result.total_elapsed_s = time.perf_counter() - t0
        result.producer_elapsed_s = producer_elapsed
        result.latency = LatencyStats.from_samples(lat)
        _finish_sync(result, expected=warmup + n, confirmed=count_lines(cap))

    elif scenario == "rotating":
        log_file = os.path.join(tmpdir, "loguru_rot.log")
        log.remove()
        sink_id = log.add(log_file, format=fmt, rotation="64 KB")
        t0 = time.perf_counter()
        producer_elapsed, lat = measure_calls(
            lambda i: log.info("benchmark message {}", i), n, warmup
        )
        log.remove(sink_id)
        result.total_elapsed_s = time.perf_counter() - t0
        result.producer_elapsed_s = producer_elapsed
        result.latency = LatencyStats.from_samples(lat)
        result.rotation = _verify_rotation(os.path.join(tmpdir, "loguru_rot*"))
        _finish_sync(
            result, expected=warmup + n, confirmed=result.rotation["total_lines"]
        )
    else:
        raise _SkipScenario(f"loguru has no scenario {scenario}")


# --- logbook ------------------------------------------------------------- #
def _run_logbook(result: ScenarioResult, scenario: str, n: int, warmup: int) -> None:
    import logbook  # ImportError -> skipped

    tmpdir = tempfile.mkdtemp(prefix="logbook_bench_")
    fmt = (
        "{record.time:%Y-%m-%d %H:%M:%S} - {record.channel} - "
        "{record.level_name} - {record.message}"
    )
    logger = logbook.Logger(f"logbook_{scenario}_{time.time_ns()}")

    if scenario == "file":
        log_file = os.path.join(tmpdir, "logbook_file.log")
        handler = logbook.FileHandler(log_file, bubble=False)
        handler.format_string = fmt
        with handler.applicationbound():
            t0 = time.perf_counter()
            producer_elapsed, lat = measure_calls(
                lambda i: logger.info("benchmark message {}", i), n, warmup
            )
        handler.close()
        result.total_elapsed_s = time.perf_counter() - t0
        result.producer_elapsed_s = producer_elapsed
        result.latency = LatencyStats.from_samples(lat)
        _finish_sync(result, expected=warmup + n, confirmed=count_lines(log_file))

    elif scenario == "stream":
        cap = os.path.join(tmpdir, "logbook_stream.out")
        stream = open(cap, "w")  # noqa: SIM115
        try:
            handler = logbook.StreamHandler(stream, bubble=False)
            handler.format_string = fmt
            with handler.applicationbound():
                t0 = time.perf_counter()
                producer_elapsed, lat = measure_calls(
                    lambda i: logger.info("benchmark message {}", i), n, warmup
                )
            stream.flush()
        finally:
            stream.close()
        result.total_elapsed_s = time.perf_counter() - t0
        result.producer_elapsed_s = producer_elapsed
        result.latency = LatencyStats.from_samples(lat)
        _finish_sync(result, expected=warmup + n, confirmed=count_lines(cap))
    else:
        raise _SkipScenario(f"logbook has no scenario {scenario}")


# --- structlog (stdlib backend; MUST NOT import logxide) ----------------- #
def _run_structlog(result: ScenarioResult, scenario: str, n: int, warmup: int) -> None:
    import structlog  # ImportError -> skipped

    assert "logxide" not in sys.modules, "structlog worker must not import logxide"

    tmpdir = tempfile.mkdtemp(prefix="structlog_bench_")

    def configure(stream):
        structlog.configure(
            processors=[
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            logger_factory=structlog.PrintLoggerFactory(file=stream),
            cache_logger_on_first_use=True,
        )
        return structlog.get_logger(f"structlog_{scenario}")

    if scenario in ("file", "stream"):
        cap = os.path.join(tmpdir, f"structlog_{scenario}.out")
        stream = open(cap, "w")  # kept open for lifetime  # noqa: SIM115
        try:
            log = configure(stream)
            t0 = time.perf_counter()
            producer_elapsed, lat = measure_calls(
                lambda i: log.info("benchmark message", i=i), n, warmup
            )
            stream.flush()
        finally:
            stream.close()
        result.total_elapsed_s = time.perf_counter() - t0
        result.producer_elapsed_s = producer_elapsed
        result.latency = LatencyStats.from_samples(lat)
        _finish_sync(result, expected=warmup + n, confirmed=count_lines(cap))
    else:
        raise _SkipScenario(f"structlog has no scenario {scenario}")


# --- picologging ---------------------------------------------------------- #
def _run_picologging(
    result: ScenarioResult, scenario: str, n: int, warmup: int
) -> None:
    import picologging  # ImportError -> skipped

    tmpdir = tempfile.mkdtemp(prefix="pico_bench_")
    logger = picologging.getLogger(f"pico_{scenario}_{time.time_ns()}")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(picologging.INFO)

    if scenario == "file":
        log_file = os.path.join(tmpdir, "pico_file.log")
        handler = picologging.FileHandler(log_file)
        handler.setFormatter(picologging.Formatter(FMT))
        logger.addHandler(handler)
        t0 = time.perf_counter()
        producer_elapsed, lat = measure_calls(
            lambda i: logger.info("benchmark message %d", i), n, warmup
        )
        handler.flush()
        handler.close()
        result.total_elapsed_s = time.perf_counter() - t0
        result.producer_elapsed_s = producer_elapsed
        result.latency = LatencyStats.from_samples(lat)
        _finish_sync(result, expected=warmup + n, confirmed=count_lines(log_file))

    elif scenario == "stream":
        cap = os.path.join(tmpdir, "pico_stream.out")
        stream = open(cap, "w")  # noqa: SIM115
        try:
            handler = picologging.StreamHandler(stream)
            handler.setFormatter(picologging.Formatter(FMT))
            logger.addHandler(handler)
            t0 = time.perf_counter()
            producer_elapsed, lat = measure_calls(
                lambda i: logger.info("benchmark message %d", i), n, warmup
            )
            handler.flush()
            stream.flush()
        finally:
            stream.close()
        result.total_elapsed_s = time.perf_counter() - t0
        result.producer_elapsed_s = producer_elapsed
        result.latency = LatencyStats.from_samples(lat)
        _finish_sync(result, expected=warmup + n, confirmed=count_lines(cap))
    else:
        raise _SkipScenario(f"picologging has no scenario {scenario}")


# ========================================================================== #
# ORCHESTRATOR SIDE
# ========================================================================== #
def orchestrator_main(args: argparse.Namespace) -> int:
    print("=" * 78)
    print("Basic Handlers Benchmark - credibility-corrected harness")
    print("=" * 78)
    print(f"Platform      : {platform.platform()}")
    print(f"Python        : {sys.version.split()[0]}")
    print(f"Iterations    : {args.iterations:,}  Warmup: {args.warmup:,}")
    print("Isolation     : one fresh subprocess per (library, scenario)")
    print("Throughput    : DURABLE (sink-confirmed records / total time incl. flush)")
    print("=" * 78)

    all_results: list[ScenarioResult] = []

    # --- sync scenarios for every library --- #
    for scenario in SYNC_SCENARIOS:
        print(f"\n### SYNC scenario: {scenario}")
        for library in LIBRARIES:
            r = run_worker(
                THIS,
                library,
                scenario,
                args.iterations,
                args.warmup,
                timeout=args.timeout,
            )
            all_results.append(r)
            _print_run_line(r)

    # --- async scenarios (logxide only) --- #
    for scenario in ASYNC_SCENARIOS:
        print(f"\n### ASYNC scenario: {scenario} (logxide)")
        r = run_worker(
            THIS,
            "logxide",
            scenario,
            args.iterations,
            args.warmup,
            timeout=args.timeout,
        )
        all_results.append(r)
        _print_run_line(r)

    _print_durable_tables(all_results)
    _print_latency_tables(all_results)
    _print_async_accounting(all_results)

    _save(all_results, args)
    print("\nDone. Numbers are machine-specific; see benchmark/README.md.")
    return 0


def _print_run_line(r: ScenarioResult) -> None:
    tag = f"  {LABELS.get(r.library, r.library):<15} {r.scenario:<12}"
    if r.skipped:
        print(f"{tag} SKIPPED ({r.error.splitlines()[0] if r.error else 'n/a'})")
    elif not r.ok:
        print(f"{tag} ERROR ({(r.error or '').splitlines()[0][:60]})")
    elif r.is_async:
        m = r.metrics
        print(
            f"{tag} emitted={m.get('emitted')} ack={m.get('sink_acknowledged')} "
            f"drop={m.get('queue_dropped')} fail={m.get('delivery_failed')} "
            f"inflight={m.get('in_flight')} identity_ok={m.get('identity_ok')}"
        )
    else:
        verified = "OK" if r.sink_confirmed == r.sink_expected else "MISMATCH"
        print(
            f"{tag} durable={r.durable_throughput:>12,.0f} rec/s  "
            f"sink={r.sink_confirmed}/{r.sink_expected} [{verified}]  "
            f"p50={r.latency.p50_ns:,.0f}ns p99={r.latency.p99_ns:,.0f}ns"
        )


def _print_durable_tables(results: list[ScenarioResult]) -> None:
    print("\n" + "=" * 78)
    print("DURABLE THROUGHPUT  (sink-confirmed records / total wall time incl. flush)")
    print("=" * 78)
    for scenario in SYNC_SCENARIOS:
        rows = [
            r for r in results if r.scenario == scenario and r.ok and not r.is_async
        ]
        if not rows:
            continue
        rows.sort(key=lambda r: r.durable_throughput, reverse=True)
        print(f"\n{scenario.upper()}")
        print(
            f"{'Library':<16}{'Durable rec/s':>16}{'Sink':>14}"
            f"{'Verify':>10}{'Total s':>10}"
        )
        print("-" * 66)
        for r in rows:
            verify = "OK" if r.sink_confirmed == r.sink_expected else "MISMATCH"
            print(
                f"{LABELS.get(r.library, r.library):<16}"
                f"{r.durable_throughput:>16,.0f}"
                f"{f'{r.sink_confirmed}/{r.sink_expected}':>14}"
                f"{verify:>10}{r.total_elapsed_s:>10.4f}"
            )


def _print_latency_tables(results: list[ScenarioResult]) -> None:
    print("\n" + "=" * 78)
    print("PRODUCER LATENCY  (per-call, nanoseconds)")
    print("=" * 78)
    for scenario in SYNC_SCENARIOS + ASYNC_SCENARIOS:
        rows = [r for r in results if r.scenario == scenario and r.ok]
        if not rows:
            continue
        rows.sort(key=lambda r: r.latency.p50_ns)
        print(f"\n{scenario.upper()}")
        print(
            f"{'Library':<16}{'p50':>12}{'p95':>12}{'p99':>12}{'mean':>12}{'max':>14}"
        )
        print("-" * 78)
        for r in rows:
            lt = r.latency
            print(
                f"{LABELS.get(r.library, r.library):<16}"
                f"{lt.p50_ns:>12,.0f}{lt.p95_ns:>12,.0f}{lt.p99_ns:>12,.0f}"
                f"{lt.mean_ns:>12,.0f}{lt.max_ns:>14,.0f}"
            )


def _print_async_accounting(results: list[ScenarioResult]) -> None:
    rows = [r for r in results if r.is_async and r.ok]
    if not rows:
        return
    print("\n" + "=" * 78)
    print("ASYNC DELIVERY ACCOUNTING  (after flush; in_flight must be 0)")
    print("identity: emitted == sink_acknowledged + queue_dropped + delivery_failed")
    print("=" * 78)
    print(
        f"{'Scenario':<14}{'emitted':>9}{'ack':>8}{'drop':>8}{'fail':>8}"
        f"{'inflt':>7}{'srv_rx':>8}{'ident':>8}{'p99 ns':>12}"
    )
    print("-" * 82)
    for r in rows:
        m = r.metrics
        print(
            f"{r.scenario:<14}{m.get('emitted', 0):>9}{m.get('sink_acknowledged', 0):>8}"
            f"{m.get('queue_dropped', 0):>8}{m.get('delivery_failed', 0):>8}"
            f"{m.get('in_flight', 0):>7}{m.get('server_received', 0):>8}"
            f"{str(m.get('identity_ok')):>8}{r.latency.p99_ns:>12,.0f}"
        )
    print(
        "\nInterpretation: 'block' overflow keeps producer latency high but loses"
        " nothing;\n'drop_newest' returns instantly but queue_dropped accounts for"
        " the lost records."
    )


def _save(results: list[ScenarioResult], args: argparse.Namespace) -> None:
    out = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "platform": platform.platform(),
            "python_version": sys.version,
            "iterations": args.iterations,
            "warmup": args.warmup,
            "methodology": "durable throughput; per-scenario subprocess isolation",
        },
        "results": [],
    }
    for r in results:
        d = json.loads(r.to_json())
        out["results"].append(d)
    fname = f"basic_handlers_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path = os.path.join(os.path.dirname(THIS), fname)
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults saved to: {path}")


# ========================================================================== #
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-n",
        "--iterations",
        type=int,
        default=2000,
        help="log messages per scenario (default: 2000; keep small for quick runs)",
    )
    parser.add_argument("-w", "--warmup", type=int, default=200)
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="per-subprocess timeout in seconds",
    )
    # worker plumbing
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--library", default="", help=argparse.SUPPRESS)
    parser.add_argument("--scenario", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker:
        return worker_main(args)
    return orchestrator_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
