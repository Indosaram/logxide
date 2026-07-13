#!/usr/bin/env python3
"""
logxide vs stdlib file-logging throughput, with sink verification.

Report section-5 fixes applied here:
* stdlib runs in its own subprocess (it already did) and never imports logxide.
* logxide runs in a SEPARATE subprocess too, so neither side contaminates the
  other and this launcher process stays neutral.
* Both sides VERIFY the file line count and report DURABLE throughput
  (sink-confirmed records / total time incl. flush), not blind call-rate.

Usage:
    python benchmark/perf_vs_stdlib.py -n 50000
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
SCENARIOS = ["simple", "structured", "args"]


def _emit(call, n):
    t0 = time.perf_counter()
    for i in range(n):
        call(i)
    return time.perf_counter() - t0, t0


def _worker(library: str, scenario: str, n: int) -> int:
    tmpdir = tempfile.mkdtemp(prefix=f"vs_{library}_")
    log_file = os.path.join(tmpdir, "bench.log")

    if library == "stdlib":
        import logging

        assert "logxide" not in sys.modules
        logger = logging.getLogger("bench_stdlib")
        logger.handlers.clear()
        logger.propagate = False
        h = logging.FileHandler(log_file)
        h.setFormatter(logging.Formatter(FMT))
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
        flush = lambda: (h.flush(), None)[1]  # noqa: E731
        confirm = lambda: count_lines(log_file)  # noqa: E731
    else:
        from logxide import logxide as lx

        lx.logging.clear_handlers()
        lx.logging.register_file_handler(log_file, 20, FMT, None)
        logger = lx.logging.getLogger("bench_lx")
        logger.setLevel(20)
        flush = lx.logging.flush
        confirm = lambda: count_lines(log_file)  # noqa: E731

    if scenario == "simple":
        call = lambda i: logger.info("Simple log message")  # noqa: E731
    elif scenario == "structured":
        call = lambda i: logger.info(f"User action - user_id: {i}, action: login")  # noqa: E731
    else:
        call = lambda i: logger.info("user %s did %s, count=%d", "alice", "login", i)  # noqa: E731

    t_start = time.perf_counter()
    for i in range(n):
        call(i)
    flush()
    confirmed = wait_until_count(confirm, n)
    total = time.perf_counter() - t_start
    print(f"RESULT_JSON:{json.dumps({'confirmed': confirmed, 'total_s': total})}")
    return 0


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
    raise RuntimeError(proc.stderr[-400:] or "worker failed")


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

    n = args.iterations
    print(f"Iterations per scenario: {n:,}  (durable throughput, sink-verified)\n")
    print(
        f"{'Scenario':<14}{'logxide rec/s':>16}{'stdlib rec/s':>16}{'speedup':>10}{'verify':>10}"
    )
    print("-" * 66)
    results = {}
    for scenario in SCENARIOS:
        lx_r = _run("logxide", scenario, n, args.timeout)
        std_r = _run("stdlib", scenario, n, args.timeout)
        lx_ops = lx_r["confirmed"] / lx_r["total_s"]
        std_ops = std_r["confirmed"] / std_r["total_s"]
        verify = (
            "OK" if lx_r["confirmed"] == n and std_r["confirmed"] == n else "MISMATCH"
        )
        print(
            f"{scenario:<14}{lx_ops:>16,.0f}{std_ops:>16,.0f}{lx_ops / std_ops:>9.2f}x{verify:>10}"
        )
        results[scenario] = {
            "logxide_durable_rec_per_sec": lx_ops,
            "stdlib_durable_rec_per_sec": std_ops,
            "speedup": lx_ops / std_ops,
            "logxide_confirmed": lx_r["confirmed"],
            "stdlib_confirmed": std_r["confirmed"],
            "expected": n,
        }

    out_dir = Path(THIS).parent / "perf_results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"vs_stdlib_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_file.write_text(json.dumps(results, indent=2))
    print(f"\nResults: {out_file}")
    print("Numbers are machine-specific; see benchmark/README.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
