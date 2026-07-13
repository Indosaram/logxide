#!/usr/bin/env python3
"""
GIL / sustained-throughput benchmark: stdlib logging vs logxide.

Fixes the report section-5 defects that also affected this script:
* The stdlib and logxide loggers used to be exercised in the SAME process, so
  importing logxide (which patches stdlib ``logging``) contaminated the stdlib
  baseline. Each library now runs in its OWN fresh subprocess; the stdlib
  worker never imports logxide.
* Throughput used to be ``TOTAL / elapsed`` with no check that the sink
  received anything. We now VERIFY the file line count and report DURABLE
  throughput (confirmed records / total time incl. flush).

Usage:
    python benchmark/gil_benchmark.py -n 20000
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _bench_common import count_lines, run_worker, wait_until_count  # noqa: E402

THIS = os.path.abspath(__file__)


def _worker(library: str, n: int) -> int:
    tmpdir = tempfile.mkdtemp(prefix=f"gil_{library}_")
    log_file = os.path.join(tmpdir, "bench.log")

    if library == "stdlib":
        import logging

        assert "logxide" not in sys.modules
        logger = logging.getLogger("gil_stdlib")
        for h in list(logger.handlers):
            logger.removeHandler(h)
        logger.propagate = False
        handler = logging.FileHandler(log_file)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        t0 = time.perf_counter()
        for i in range(n):
            logger.info("Processing sequential request %d to test throughput.", i)
        handler.flush()
        handler.close()
        confirmed = count_lines(log_file)
        total = time.perf_counter() - t0

    else:  # logxide
        from logxide import logxide as lx
        from logxide.handlers import FileHandler

        logger = lx.logging.getLogger("gil_logxide")
        while getattr(logger, "handlers", None):
            logger.removeHandler(logger.handlers[0])
        logger.propagate = False
        handler = FileHandler(log_file)
        logger.addHandler(handler)
        logger.setLevel(20)

        t0 = time.perf_counter()
        for i in range(n):
            logger.info("Processing sequential request %d to test throughput.", i)
        handler.flush()
        lx.logging.flush()
        confirmed = wait_until_count(lambda: count_lines(log_file), n)
        total = time.perf_counter() - t0

    print(f'RESULT_JSON:{{"confirmed": {confirmed}, "total_s": {total}}}')
    return 0


def _run(library: str, n: int, timeout: float):
    import json
    import subprocess

    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, THIS, "--worker", "--library", library, "-n", str(n)],
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
    parser.add_argument("-n", "--iterations", type=int, default=20_000)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--library", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker:
        return _worker(args.library, args.iterations)

    print("=== Sustained-throughput benchmark (subprocess-isolated) ===")
    print(f"iterations={args.iterations:,}  metric=durable (sink-confirmed/time)\n")
    out = {}
    for library in ("stdlib", "logxide"):
        r = _run(library, args.iterations, args.timeout)
        verify = "OK" if r["confirmed"] == args.iterations else "MISMATCH"
        durable = r["confirmed"] / r["total_s"] if r["total_s"] else 0
        out[library] = durable
        print(
            f"{library:<10} durable={durable:>12,.0f} rec/s  "
            f"sink={r['confirmed']}/{args.iterations} [{verify}]  "
            f"total={r['total_s']:.4f}s"
        )
    if out.get("stdlib"):
        print(
            f"\nLogXide durable throughput vs stdlib: {out['logxide'] / out['stdlib']:.2f}x"
        )
    print("\nNumbers are machine-specific; see benchmark/README.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
