#!/usr/bin/env python3
"""
Real handler comparison: logxide vs picologging vs structlog (file & stream).

This is a credibility-corrected rewrite (report section 5). The old version
imported logxide, picologging and structlog into the SAME process and measured
call-rate with no sink verification; the logxide "stream" case used
``basicConfig()`` with no filename, so it was not even a stream to a verifiable
sink. Fixes:

* Each library runs in its OWN fresh subprocess. Non-logxide workers never
  import logxide.
* Missing optional libraries (picologging / structlog) are skipped cleanly.
* Every case VERIFIES the sink: file cases count file lines; the logxide stream
  case redirects the OS-level stdout fd to a real file and counts its lines.
* Throughput is DURABLE (sink-confirmed records / total time incl. flush).

Usage:
    python benchmark/real_handlers_comparison.py -n 10000
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _bench_common import RedirectedFD, count_lines, wait_until_count  # noqa: E402

THIS = os.path.abspath(__file__)
FMT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LIBRARIES = ["logxide", "picologging", "structlog"]
HANDLERS = ["file", "stream"]


def _worker(library: str, handler: str, n: int) -> int:
    try:
        confirmed, total = _measure(library, handler, n)
    except ImportError as e:
        print(f"RESULT_JSON:{json.dumps({'skipped': True, 'reason': str(e)})}")
        return 0
    print(
        f"RESULT_JSON:{json.dumps({'confirmed': confirmed, 'total_s': total, 'expected': n})}"
    )
    return 0


def _measure(library: str, handler: str, n: int):
    tmpdir = tempfile.mkdtemp(prefix=f"rh_{library}_")
    log_file = os.path.join(tmpdir, "bench.log")

    if library == "logxide":
        from logxide import logxide as lx

        if handler == "file":
            from logxide.handlers import FileHandler

            logger = lx.logging.getLogger(f"rh_lx_file_{time.time_ns()}")
            while getattr(logger, "handlers", None):
                logger.removeHandler(logger.handlers[0])
            logger.propagate = False
            h = FileHandler(log_file)
            logger.addHandler(h)
            logger.setLevel(20)
            t0 = time.perf_counter()
            for i in range(n):
                logger.info("Test message %d", i)
            h.flush()
            lx.logging.flush()
            confirmed = wait_until_count(lambda: count_lines(log_file), n)
            return confirmed, time.perf_counter() - t0
        else:  # stream via OS-fd redirect (verifiable)
            cap = os.path.join(tmpdir, "stream.out")
            with RedirectedFD(cap, "stdout"):
                lx.logging.clear_handlers()
                lx.logging.register_stream_handler("stdout", 20, "%(message)s", None)
                logger = lx.logging.getLogger(f"rh_lx_stream_{time.time_ns()}")
                logger.setLevel(20)
                t0 = time.perf_counter()
                for i in range(n):
                    logger.info("Test message %d", i)
                lx.logging.flush()
                confirmed = wait_until_count(lambda: count_lines(cap), n)
                total = time.perf_counter() - t0
            return confirmed, total

    if library == "picologging":
        import picologging  # ImportError -> skipped

        logger = picologging.getLogger(f"rh_pico_{handler}_{time.time_ns()}")
        logger.handlers.clear()
        logger.propagate = False
        cap = os.path.join(tmpdir, "stream.out")
        stream = None
        if handler == "file":
            h = picologging.FileHandler(log_file)
            target = log_file
        else:
            stream = open(cap, "w")  # noqa: SIM115
            h = picologging.StreamHandler(stream)
            target = cap
        h.setFormatter(picologging.Formatter(FMT))
        logger.addHandler(h)
        logger.setLevel(picologging.INFO)
        t0 = time.perf_counter()
        for i in range(n):
            logger.info("Test message %d", i)
        h.flush()
        if stream:
            stream.flush()
            stream.close()
        confirmed = count_lines(target)
        return confirmed, time.perf_counter() - t0

    if library == "structlog":
        import structlog  # ImportError -> skipped

        assert "logxide" not in sys.modules
        cap = os.path.join(tmpdir, "out")
        stream = open(cap, "w")  # noqa: SIM115
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
            log = structlog.get_logger("rh_structlog")
            t0 = time.perf_counter()
            for i in range(n):
                log.info("Test message", i=i)
            stream.flush()
            total = time.perf_counter() - t0
            confirmed = count_lines(cap)
        finally:
            stream.close()
        return confirmed, total

    raise ImportError(f"unknown library {library}")


def _run(library: str, handler: str, n: int, timeout: float) -> dict:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            THIS,
            "--worker",
            "--library",
            library,
            "--handler",
            handler,
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
    parser.add_argument("-n", "--iterations", type=int, default=10_000)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--library", default="", help=argparse.SUPPRESS)
    parser.add_argument("--handler", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker:
        return _worker(args.library, args.handler, args.iterations)

    print("Real Handler Comparison (subprocess-isolated, sink-verified)")
    print(f"iterations={args.iterations:,}  metric=durable rec/s\n")
    for handler in HANDLERS:
        print(f"=== {handler.upper()} HANDLER ===")
        print(f"{'Library':<14}{'durable rec/s':>16}{'sink':>16}{'verify':>10}")
        print("-" * 56)
        rows = []
        for library in LIBRARIES:
            r = _run(library, handler, args.iterations, args.timeout)
            if r.get("skipped"):
                print(f"{library:<14}{'SKIPPED':>16}  ({r.get('reason', '')[:30]})")
                continue
            durable = r["confirmed"] / r["total_s"] if r["total_s"] else 0
            verify = "OK" if r["confirmed"] == r["expected"] else "MISMATCH"
            rows.append((library, durable))
            sink = f"{r['confirmed']}/{r['expected']}"
            print(f"{library:<14}{durable:>16,.0f}{sink:>16}{verify:>10}")
        print()
    print("Numbers are machine-specific; see benchmark/README.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
