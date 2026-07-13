#!/usr/bin/env python3
"""
Shared helpers for the credibility-corrected logxide benchmark harness.

Design goals (see docs/performance-bottleneck-report-2026-07-13.md section 5):

1. Every scenario runs in its OWN fresh subprocess with a clean interpreter, so
   importing ``logxide`` (which patches stdlib ``logging.getLogger``/``basicConfig``
   and replaces ``sys.modules['logging']``) can never contaminate the stdlib or
   structlog baselines. Non-logxide workers NEVER import logxide.
2. Throughput is only ever reported as **durable throughput** =
   ``sink_confirmed_records / total_wall_time`` (including flush). We refuse to
   report producer call-rate as throughput.
3. Producer-side latency is measured per call and summarised as p50/p95/p99.
4. Async handlers additionally report the full delivery accounting
   ``{emitted, sink_acknowledged, queue_dropped, delivery_failed, in_flight}``
   and we assert the identity
   ``emitted == sink_acknowledged + queue_dropped + delivery_failed`` after
   ``flush()`` (with ``in_flight == 0``).

Nothing here imports logxide at module import time.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Optional


# --------------------------------------------------------------------------- #
# Latency statistics
# --------------------------------------------------------------------------- #
def percentile(sorted_vals: list[float], p: float) -> float:
    """Linear-interpolation percentile. ``p`` in [0, 1]. Input must be sorted."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


@dataclass
class LatencyStats:
    count: int = 0
    mean_ns: float = 0.0
    p50_ns: float = 0.0
    p95_ns: float = 0.0
    p99_ns: float = 0.0
    max_ns: float = 0.0

    @classmethod
    def from_samples(cls, samples_ns: list[float]) -> LatencyStats:
        if not samples_ns:
            return cls()
        s = sorted(samples_ns)
        return cls(
            count=len(s),
            mean_ns=sum(s) / len(s),
            p50_ns=percentile(s, 0.50),
            p95_ns=percentile(s, 0.95),
            p99_ns=percentile(s, 0.99),
            max_ns=s[-1],
        )


# --------------------------------------------------------------------------- #
# Result payload passed from worker subprocess back to the orchestrator
# --------------------------------------------------------------------------- #
@dataclass
class ScenarioResult:
    library: str
    scenario: str
    ok: bool = False
    skipped: bool = False
    error: str = ""

    iterations: int = 0

    # timing
    producer_elapsed_s: float = 0.0  # time to issue all producer calls
    total_elapsed_s: float = 0.0  # producer + flush/drain (durability boundary)

    # sink verification (the ONLY basis for throughput we trust)
    sink_confirmed: int = 0  # records the sink actually received / retained
    sink_expected: int = 0  # what a lossless sync sink should hold

    # producer latency percentiles (nanoseconds)
    latency: LatencyStats = field(default_factory=LatencyStats)

    # async delivery accounting (empty dict for sync handlers)
    metrics: dict = field(default_factory=dict)

    # rotation verification (empty dict for non-rotating scenarios)
    rotation: dict = field(default_factory=dict)

    # is this an async (queueing) handler?
    is_async: bool = False

    @property
    def durable_throughput(self) -> float:
        if self.total_elapsed_s <= 0:
            return 0.0
        return self.sink_confirmed / self.total_elapsed_s

    @property
    def producer_throughput(self) -> float:
        if self.producer_elapsed_s <= 0:
            return 0.0
        return self.iterations / self.producer_elapsed_s

    def to_json(self) -> str:
        d = asdict(self)
        d["durable_throughput"] = self.durable_throughput
        d["producer_throughput"] = self.producer_throughput
        return json.dumps(d)

    @classmethod
    def from_json(cls, blob: str) -> ScenarioResult:
        d = json.loads(blob)
        d.pop("durable_throughput", None)
        d.pop("producer_throughput", None)
        lat = d.pop("latency", {}) or {}
        r = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        r.latency = LatencyStats(**lat) if lat else LatencyStats()
        return r


# --------------------------------------------------------------------------- #
# Producer-side measurement primitive
# --------------------------------------------------------------------------- #
def measure_calls(
    call: Callable[[int], None],
    iterations: int,
    warmup: int,
    sample_latency: bool = True,
    max_latency_samples: int = 200_000,
) -> tuple[float, list[float]]:
    """
    Run ``call(i)`` ``iterations`` times after ``warmup`` warmup calls.

    Returns ``(producer_elapsed_s, latency_samples_ns)``.

    Per-call latency is captured with ``perf_counter_ns`` around each call. To
    bound memory on very large runs we sample at most ``max_latency_samples``
    calls evenly; the returned elapsed time always covers ALL iterations.
    """
    for i in range(warmup):
        call(i)

    latencies: list[float] = []
    if not sample_latency:
        t0 = time.perf_counter()
        for i in range(iterations):
            call(i)
        return time.perf_counter() - t0, latencies

    stride = max(1, iterations // max_latency_samples)
    t0 = time.perf_counter()
    for i in range(iterations):
        if i % stride == 0:
            c0 = time.perf_counter_ns()
            call(i)
            latencies.append(float(time.perf_counter_ns() - c0))
        else:
            call(i)
    producer_elapsed = time.perf_counter() - t0
    return producer_elapsed, latencies


# --------------------------------------------------------------------------- #
# Sink verification helpers
# --------------------------------------------------------------------------- #
def count_lines(path: str) -> int:
    if not os.path.exists(path):
        return 0
    n = 0
    with open(path, "rb") as fh:
        for _ in fh:
            n += 1
    return n


def wait_until_count(
    counter_fn: Callable[[], int],
    expected: int,
    timeout: float = 15.0,
    poll: float = 0.001,
) -> int:
    """
    Poll ``counter_fn`` until it reaches ``expected`` (the true durability
    boundary) or ``timeout`` elapses. Returns the final observed count.

    This is what makes "durable throughput" honest for asynchronous sinks: the
    clock stops only once the sink has actually confirmed the records, not
    after an arbitrary fixed sleep.
    """
    c = counter_fn()
    if c >= expected:
        return c
    deadline = time.perf_counter() + timeout
    while c < expected and time.perf_counter() < deadline:
        time.sleep(poll)
        c = counter_fn()
    return c


class RedirectedFD:
    """
    Context manager that redirects an OS-level file descriptor (1=stdout,
    2=stderr) to a real capture file for its whole lifetime.

    This is the ONLY correct way to capture a Rust ``StreamHandler`` whose sink
    is the process' actual OS stdout/stderr; swapping Python's ``sys.stderr``
    object (as the old harness did) does not control the Rust writer.
    """

    def __init__(self, capture_path: str, which: str = "stdout"):
        self.capture_path = capture_path
        self.fd = 1 if which == "stdout" else 2
        self._saved = None
        self._capfd = None

    def __enter__(self) -> RedirectedFD:
        self._capfd = os.open(
            self.capture_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644
        )
        self._saved = os.dup(self.fd)
        os.dup2(self._capfd, self.fd)
        return self

    def __exit__(self, *exc) -> None:
        with contextlib.suppress(OSError):
            os.fsync(self.fd)
        if self._saved is not None:
            os.dup2(self._saved, self.fd)
            os.close(self._saved)
        if self._capfd is not None:
            os.close(self._capfd)
        return None


# --------------------------------------------------------------------------- #
# Subprocess orchestration
# --------------------------------------------------------------------------- #
def run_worker(
    script: str,
    library: str,
    scenario: str,
    iterations: int,
    warmup: int,
    extra_args: list[str] | None = None,
    timeout: float = 300.0,
) -> ScenarioResult:
    """
    Spawn ``python <script> --worker ...`` as a fresh subprocess and parse the
    single JSON line it prints on stdout (prefixed with ``RESULT_JSON:``).

    A clean environment is used: we scrub any variable that might smuggle
    logxide into a stdlib/structlog worker, and force UTF-8.
    """
    env = dict(os.environ)
    # A fresh interpreter only imports what the worker imports; nothing here
    # pre-imports logxide. We still scrub PYTHONSTARTUP / sitecustomize hooks.
    env.pop("PYTHONSTARTUP", None)
    env["PYTHONUTF8"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    cmd = [
        sys.executable,
        script,
        "--worker",
        "--library",
        library,
        "--scenario",
        scenario,
        "-n",
        str(iterations),
        "-w",
        str(warmup),
    ]
    if extra_args:
        cmd.extend(extra_args)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        r = ScenarioResult(library=library, scenario=scenario)
        r.error = f"timeout after {timeout}s"
        return r

    result: ScenarioResult | None = None
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT_JSON:"):
            result = ScenarioResult.from_json(line[len("RESULT_JSON:") :])
            break

    if result is None:
        r = ScenarioResult(library=library, scenario=scenario)
        if proc.returncode != 0:
            r.error = (proc.stderr or "worker failed").strip()[-500:]
        else:
            r.error = "no RESULT_JSON emitted; stderr=" + (proc.stderr or "")[-300:]
        return result if result else r

    return result


def emit_result(result: ScenarioResult) -> None:
    """Called by a worker to hand its result back to the orchestrator."""
    print("RESULT_JSON:" + result.to_json(), flush=True)
