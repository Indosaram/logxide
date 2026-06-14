import gc
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ITERATIONS = 100_000
RUNS = 3


def bench_stdlib_subprocess(scenario: str) -> float:
    script = f"""
import gc, logging, tempfile, time

log_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log')
log_file.close()

logger = logging.getLogger('bench_stdlib')
logger.handlers.clear()
logger.propagate = False
h = logging.FileHandler(log_file.name)
h.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(h)
logger.setLevel(logging.INFO)

iters = {ITERATIONS}
times = []
for _ in range({RUNS}):
    gc.collect()
    t0 = time.perf_counter()
    if "{scenario}" == "simple":
        for _i in range(iters):
            logger.info("Simple log message")
    elif "{scenario}" == "structured":
        for i in range(iters):
            logger.info(f"User action - user_id: {{i}}, action: login")
    elif "{scenario}" == "args":
        for i in range(iters):
            logger.info("user %s did %s, count=%d", "alice", "login", i)
    times.append(time.perf_counter() - t0)

import os
os.unlink(log_file.name)
print(min(times))
"""
    r = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=120
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    return float(r.stdout.strip())


def bench_logxide(scenario: str) -> float:
    from logxide import logxide as lx

    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        log_file = f.name

    lx.logging.clear_handlers()
    lx.logging.register_file_handler(
        log_file, 20, "%(asctime)s - %(name)s - %(levelname)s - %(message)s", None
    )
    logger = lx.logging.getLogger("bench_lx")
    logger.setLevel(20)

    iters = ITERATIONS
    times = []
    for _ in range(RUNS):
        gc.collect()
        t0 = time.perf_counter()
        if scenario == "simple":
            for _i in range(iters):
                logger.info("Simple log message")
        elif scenario == "structured":
            for i in range(iters):
                logger.info(f"User action - user_id: {i}, action: login")
        elif scenario == "args":
            for i in range(iters):
                logger.info("user %s did %s, count=%d", "alice", "login", i)
        lx.logging.flush()
        times.append(time.perf_counter() - t0)

    os.unlink(log_file)
    return min(times)


print(f"Iterations per run: {ITERATIONS:,}, runs: {RUNS}")
print()
print(f"{'Scenario':<14}{'logxide ops/s':>20}{'stdlib ops/s':>20}{'speedup':>12}")
print("-" * 66)
results = {}
for scenario in ["simple", "structured", "args"]:
    lx_t = bench_logxide(scenario)
    std_t = bench_stdlib_subprocess(scenario)
    lx_ops = ITERATIONS / lx_t
    std_ops = ITERATIONS / std_t
    speedup = lx_ops / std_ops
    print(f"{scenario:<14}{lx_ops:>20,.0f}{std_ops:>20,.0f}{speedup:>11.2f}x")
    results[scenario] = {
        "logxide_ops_per_sec": lx_ops,
        "stdlib_ops_per_sec": std_ops,
        "speedup": speedup,
    }

out_dir = Path(__file__).parent / "perf_results"
out_dir.mkdir(exist_ok=True)
out_file = out_dir / f"vs_stdlib_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
out_file.write_text(json.dumps(results, indent=2))
print(f"\nResults: {out_file}")
