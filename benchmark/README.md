# logxide benchmark harness

This directory contains a **credibility-corrected** benchmark harness. It was
rewritten to fix the seven defects catalogued in
`docs/performance-bottleneck-report-2026-07-13.md` §5, which showed that the
previous harness reported *producer call-rate* (including silently dropped
records) as if it were delivered throughput.

> **All numbers are machine-specific.** They depend on CPU, filesystem, Python
> build (GIL vs free-threaded), and system load. Treat them as relative,
> reproducible-on-*your*-box measurements, not universal constants. Every
> throughput figure printed here is backed by a **verified sink count**; an
> unverified number is treated as invalid.

## Core methodology

1. **Process isolation.** Each `(library, scenario)` runs in its own fresh
   subprocess. This is essential because importing `logxide` monkey-patches
   `logging.getLogger` / `logging.basicConfig` and replaces
   `sys.modules['logging']`. The stdlib and structlog baselines therefore run
   in workers that **never import logxide**, so they measure the real stdlib.

2. **Durable throughput, not call-rate.** Throughput is always
   `sink_confirmed_records / total_wall_time`, where `total_wall_time` covers
   the producer loop **plus** flush **plus** the time to drain to the sink. The
   clock stops only once the sink has actually confirmed the records (we poll
   the file line count / in-memory record count / server-received count), not
   after an arbitrary `sleep`.

3. **Sink verification for every scenario.**
   * File / rotating / stream → count the lines actually written to a real file.
   * Stream handlers whose sink is the process' OS stdout/stderr (logxide's Rust
     `StreamHandler`) are captured by redirecting the OS-level file descriptor
     to a real file — swapping Python's `sys.stderr` object does **not** control
     the Rust writer.
   * `MemoryHandler` → `len(handler.records)`.
   * Async HTTP handler → the slow local HTTP server's received count.
   A `[MISMATCH]` in the output means the sink did not receive what was emitted
   (e.g. rotation eviction or queue overflow) and the throughput must not be
   trusted as "durable".

4. **Producer latency.** Per-call latency is sampled with `perf_counter_ns` and
   summarised as p50 / p95 / p99 / mean / max (nanoseconds). For synchronous vs
   asynchronous handlers this is reported in a table *separate* from durable
   throughput, because a fast producer can simply be dropping records.

5. **Async delivery accounting.** logxide 0.2.0 async handlers expose
   `get_metrics()` → `{emitted, sink_acknowledged, queue_dropped,
   delivery_failed, in_flight}`. After `flush()` the harness asserts the
   identity

   ```
   emitted == sink_acknowledged + queue_dropped + delivery_failed   (and in_flight == 0)
   ```

   and prints both the `overflow="block"` (durable, high producer latency) and
   `overflow="drop_newest"` (instant producer, lossy) cases so the trade-off is
   explicit.

6. **Rotation is verified.** The rotating-file scenario uses a real
   `RotatingFileHandler` with a real filename and reports the number of rotated
   files, retained line count, and total bytes. (The old harness called
   `basicConfig()` with no filename, so it was actually a stream handler.)

7. **Measurement rigor** follows report §7: warmup before timing, GC disabled
   during the timed loop (micro-benchmarks), and a thread barrier for the
   concurrent scenario.

## Scripts

| Script | What it measures |
|---|---|
| `basic_handlers_benchmark.py` | File / Stream / Rotating handlers across logxide, stdlib, loguru, logbook, structlog, picologging + logxide async HTTP accounting. Durable-throughput and producer-latency tables. |
| `perf_micro.py` | logxide producer micro-benchmarks (file, memory, filtered NOOP, `%s` args, 4-thread), one fresh process per scenario. |
| `perf_vs_stdlib.py` | logxide vs stdlib file logging, both sink-verified. |
| `gil_benchmark.py` | Sustained file throughput: stdlib vs logxide, isolated + verified. |
| `real_handlers_comparison.py` | logxide vs picologging vs structlog, file & stream, isolated + verified. |
| `compare_loggers.py` | logxide vs stdlib vs picologging vs structlog file I/O, isolated + verified. |
| `_bench_common.py` | Shared helpers: latency stats, subprocess runner, sink counters, OS-fd redirect, poll-until-drained. |

## Running

Iteration counts are CLI-configurable with **small defaults** so a run finishes
quickly (logxide-only path well under a minute):

```bash
# quick end-to-end (default -n 2000)
.venv/bin/python benchmark/basic_handlers_benchmark.py -n 2000

# micro-benchmarks
.venv/bin/python benchmark/perf_micro.py -n 20000

# others
.venv/bin/python benchmark/perf_vs_stdlib.py -n 20000
.venv/bin/python benchmark/gil_benchmark.py -n 20000
.venv/bin/python benchmark/real_handlers_comparison.py -n 5000
.venv/bin/python benchmark/compare_loggers.py -n 5000
```

Optional libraries (loguru / logbook / structlog / picologging) are **skipped
cleanly** when not installed; logxide + stdlib always run. Results are written
to timestamped JSON files (existing result files are never deleted).
