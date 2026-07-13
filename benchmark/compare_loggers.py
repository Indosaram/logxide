#!/usr/bin/env python3
"""
logxide vs stdlib vs picologging vs structlog with real file I/O.

Credibility-corrected rewrite (report section 5): every library runs in its own
fresh subprocess (stdlib/structlog never import logxide), missing optional
libraries are skipped cleanly, and every scenario VERIFIES the number of lines
written to the file before reporting DURABLE throughput (sink-confirmed records
/ total time incl. flush).

Usage:
    python benchmark/compare_loggers.py -n 50000
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _bench_common import count_lines, wait_until_count  # noqa: E402

THIS = os.path.abspath(__file__)
FMT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LIBRARIES = ["logging", "logxide", "picologging", "structlog"]
SCENARIOS = ["simple", "structured", "error"]


def _worker(library: str, scenario: str, n: int) -> int:
    try:
        confirmed, total = _measure(library, scenario, n)
    except ImportError as e:
        print(f"RESULT_JSON:{json.dumps({'skipped': True, 'reason': str(e)})}")
        return 0
    print(
        f"RESULT_JSON:{json.dumps({'confirmed': confirmed, 'total_s': total, 'expected': n})}"
    )
    return 0


def _measure(library: str, scenario: str, n: int):
    tmpdir = tempfile.mkdtemp(prefix=f"cmp_{library}_")
    log_file = os.path.join(tmpdir, "bench.log")

    if library == "logging":
        import logging

        assert "logxide" not in sys.modules
        logger = logging.getLogger("cmp_stdlib")
        logger.handlers.clear()
        logger.propagate = False
        h = logging.FileHandler(log_file)
        h.setFormatter(logging.Formatter(FMT))
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
        call = _stdlike_call(logger, scenario)
        t0 = time.perf_counter()
        for i in range(n):
            call(i)
        h.flush()
        h.close()
        return count_lines(log_file), time.perf_counter() - t0

    if library == "logxide":
        from logxide import logxide as lx

        lx.logging.clear_handlers()
        lx.logging.register_file_handler(log_file, 20, FMT, None)
        logger = lx.logging.getLogger("cmp_lx")
        logger.setLevel(20)
        call = _logxide_call(logger, scenario)
        t0 = time.perf_counter()
        for i in range(n):
            call(i)
        lx.logging.flush()
        confirmed = wait_until_count(lambda: count_lines(log_file), n)
        return confirmed, time.perf_counter() - t0

    if library == "picologging":
        import picologging  # ImportError -> skipped

        logger = picologging.getLogger("cmp_pico")
        logger.handlers.clear()
        logger.propagate = False
        h = picologging.FileHandler(log_file)
        h.setFormatter(picologging.Formatter(FMT))
        logger.addHandler(h)
        logger.setLevel(picologging.INFO)
        call = _stdlike_call(logger, scenario)
        t0 = time.perf_counter()
        for i in range(n):
            call(i)
        h.flush()
        h.close()
        return count_lines(log_file), time.perf_counter() - t0

    if library == "structlog":
        import structlog  # ImportError -> skipped

        assert "logxide" not in sys.modules
        stream = open(log_file, "w")  # noqa: SIM115
        try:
            structlog.configure(
                processors=[
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.add_log_level,
                    structlog.processors.JSONRenderer(),
                ],
                logger_factory=structlog.PrintLoggerFactory(file=stream),
                cache_logger_on_first_use=True,
            )
            log = structlog.get_logger("cmp_structlog")
            call = _structlog_call(log, scenario)
            t0 = time.perf_counter()
            for i in range(n):
                call(i)
            stream.flush()
            total = time.perf_counter() - t0
            confirmed = count_lines(log_file)
        finally:
            stream.close()
        return confirmed, total

    raise ImportError(f"unknown library {library}")


def _stdlike_call(logger, scenario):
    if scenario == "simple":
        return lambda i: logger.info("Simple log message")
    if scenario == "structured":
        return lambda i: logger.info(
            f"User action - user_id: {i}, action: login, status: success"
        )
    return lambda i: logger.error(f"Error occurred - error: boom, count: {i}")


def _logxide_call(logger, scenario):
    # logxide accepts the same %-style / plain calls as stdlib here.
    return _stdlike_call(logger, scenario)


def _structlog_call(log, scenario):
    if scenario == "simple":
        return lambda i: log.info("Simple log message")
    if scenario == "structured":
        return lambda i: log.info(
            "User action", user_id=i, action="login", status="success"
        )
    return lambda i: log.error("Error occurred", error="boom", count=i)


def _run(library: str, scenario: str, n: int, timeout: float) -> dict:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            THIS,
            "--worker",
            "--library",
            library,
            "--scenario",
            scenario,
            "-n",
            str(n),
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT_JSON:"):
            return json.loads(line[len("RESULT_JSON:") :])
    return {"skipped": True, "reason": (proc.stderr[-200:] or "worker failed")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", "--iterations", type=int, default=50_000)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--library", default="", help=argparse.SUPPRESS)
    parser.add_argument("--scenario", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker:
        return _worker(args.library, args.scenario, args.iterations)

    print("logxide vs stdlib vs picologging vs structlog (file I/O, sink-verified)")
    print(f"iterations={args.iterations:,}  metric=durable rec/s\n")
    all_results = {}
    for scenario in SCENARIOS:
        print(f"=== {scenario.upper()} ===")
        print(f"{'Library':<14}{'durable rec/s':>16}{'sink':>16}{'verify':>10}")
        print("-" * 56)
        all_results[scenario] = {}
        for library in LIBRARIES:
            r = _run(library, scenario, args.iterations, args.timeout)
            if r.get("skipped"):
                print(f"{library:<14}{'SKIPPED':>16}  ({r.get('reason', '')[:30]})")
                continue
            durable = r["confirmed"] / r["total_s"] if r["total_s"] else 0
            verify = "OK" if r["confirmed"] == r["expected"] else "MISMATCH"
            sink = f"{r['confirmed']}/{r['expected']}"
            print(f"{library:<14}{durable:>16,.0f}{sink:>16}{verify:>10}")
            all_results[scenario][library] = {
                "durable_rec_per_sec": durable,
                "confirmed": r["confirmed"],
                "expected": r["expected"],
            }
        print()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(
        Path(THIS).parent, f"logger_comparison_file_io_{timestamp}.json"
    )
    with open(path, "w") as f:
        json.dump({"iterations": args.iterations, "results": all_results}, f, indent=2)
    print(f"Results saved to {path}")
    print("Numbers are machine-specific; see benchmark/README.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
