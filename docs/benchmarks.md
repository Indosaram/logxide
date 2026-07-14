# LogXide Performance Benchmarks

This document provides comprehensive performance analysis of LogXide compared to other Python logging libraries.

## Test Environment

- **Platform**: macOS ARM64 (Apple Silicon)
- **Python**: 3.12.11 / 3.14.2
- **Test Methodology**: Multiple runs (3 iterations) with averages, garbage collection between tests
- **Libraries Tested**: LogXide, Picologging, Structlog
- **Test Date**: December 30, 2024 (external), March 19, 2026 (internal), June 12, 2026 (Unreleased)

## Unreleased Optimization Pass (June 12, 2026)

The next release introduces a series of hot-path optimizations measured against the v0.1.19 baseline. Methodology: `benchmark/perf_micro.py`, 200K iterations × 5 runs, FileHandler with formatter `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`, Python 3.14 on macOS arm64, release build with `lto = "fat"` and `codegen-units = 1`.

### Self-Throughput (vs prior LogXide release)

| Scenario              | v0.1.19 baseline | Unreleased | Δ        |
| :-------------------- | ---------------: | ---------: | :------- |
| FileHandler info()    |          720,099 |  1,357,691 | **+88.5%** |
| MemoryHandler info()  |          394,227 |    513,373 | +30.2%   |
| Filtered debug NOOP   |          24.3M   |    28.2M   | +15.9%   |
| info() with `%s` args |          280,473 |    357,320 | +27.4%   |
| FileHandler 4 threads |          299,841 |    388,971 | +29.8%   |

### vs Python stdlib `logging`

The head-to-head speedup vs stdlib for this build is reported once, for both Python versions, in the canonical **Benchmark A** section below ("File I/O Scenarios — vs stdlib"). It lands at roughly ~7–9× on the simple / structured scenarios and ~5–6× on `%`-args, comparable on Python 3.12 and 3.14.

### Optimization Wave Breakdown

| Wave  | Change                                                                 | Primary impact            |
| :---- | :--------------------------------------------------------------------- | :------------------------ |
| **0** | `[profile.release]` with `lto = "fat"`, `codegen-units = 1`            | +7-12% across all paths   |
| **1** | `arc_swap::ArcSwap<Vec<Arc<Handler>>>` for global handler registry     | Lock-free emit dispatch   |
| **2** | `parking_lot::Mutex<Arc<dyn Formatter>>` + `NoOpFormatter` sentinel    | Removes per-emit Option branch |
| **3** | `itoa::Buffer` + `write!` macros + lazy asctime in `PythonFormatter`   | Zero-alloc numeric fields |
| **4** | `chrono::Utc::now()` in record creation                                | Skips TZ lookup           |
| **5** | Thread-local cached `thread_id`, `OnceLock` cached `process_id`        | Removes per-record syscalls |
| **A** | Thread-local `FMT_SCRATCH` buffer with reentrancy guard                | Capacity reuse on format() |
| **B** | `LogLevel::as_str() -> &'static str`, removed self-defeating intern cache | Removes Arc<str>->String round-trip |
| **C** | Batched caller-info via cached `_get_caller_info()` Python helper      | 6+ getattr calls → 1      |
| **D** | `LogRecord.args`: `Option<String>` (JSON) → `Option<Arc<Value>>`       | Removes JSON encode/decode round-trip per record |

The largest single contributor is Wave D (args round-trip removal) for the `info() with %s args` path, and the combined Wave 2+3+A bundle for the `FileHandler info()+formatter` path.

## Internal Handler Benchmarks

Low-level `emit()` latency and throughput measurements for each handler type.

### emit() Latency (10K calls, single LogRecord)

| Handler | Avg | Median | P99 | Ops/sec |
|---------|-----|--------|-----|---------|
| StreamHandler | 60ns | 42ns | 84ns | 16.8M |
| FileHandler | 69ns | 83ns | 84ns | 14.4M |
| RotatingFileHandler | 67ns | 83ns | 84ns | 15.0M |
| MemoryHandler | 67ns | 83ns | 84ns | 15.0M |

### Throughput (200K messages via `logger.info`, Unreleased build)

Methodology: `benchmark/perf_micro.py`, FileHandler with `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"` format, Python 3.14, 5 runs:

| Handler | Messages | Ops/sec |
|---------|---------:|--------:|
| FileHandler (with formatter) | 200,000 | **1,357,691** |
| MemoryHandler | 200,000 |   513,373 |
| FileHandler (4 threads, 100K total) | 100,000 |   388,971 |

### flush() Latency (1K calls)

| Handler | Avg | Median | P99 |
|---------|-----|--------|-----|
| FileHandler | 80ns | 83ns | 125ns |

!!! note "Handler I/O Strategy"
    - **StreamHandler**: crossbeam channel + background thread (non-blocking emit)
    - **FileHandler / RotatingFileHandler**: synchronous direct write (parking_lot::Mutex + BufWriter)
    - **HTTPHandler / OTLPHandler**: crossbeam channel + background thread (batched)
    - **MemoryHandler**: synchronous Vec::push under parking_lot::Mutex

## Comparative Benchmark — All Logging Libraries (corrected, sink-verified)

The defective cross-library harness flagged in the [performance audit](performance-bottleneck-report-2026-07-13.md) (§5) has been rebuilt. The corrected harness lives at `benchmark/basic_handlers_benchmark.py`. It:

- runs **every library in its own subprocess** per scenario, so stdlib `logging` and Structlog are never measured inside LogXide's monkey-patched process;
- writes to a **real sink** and, after flushing, **counts the records the sink actually received** (every row below was sink-verified at 20,200 / 20,200 records);
- reports **durable throughput** (sink-confirmed records ÷ total wall time including flush) separately from **producer latency** (p50/p95/p99 of the logging call), so a fast-returning async producer can never be scored as durable throughput;
- uses a genuine `RotatingFileHandler` for the rotating row instead of substituting a plain `StreamHandler`.

!!! note "These numbers are machine-specific"
    Re-run this session on **macOS M4 Max, release build, `-n 20000`**, per-scenario subprocess isolation, on **both CPython 3.12.11 and 3.14.2**. Absolute throughput depends on the machine, the build, and the sink. Treat the rounded ranges (FILE ~6–11×, ROTATING ~8–14×, STREAM ~5×) as the durable signal, not any single raw rec/s. Run-to-run variance is real (roughly ±40% on these baselines), so figures here are presented as ranges rather than to false precision, and CPython 3.12 and 3.14 land at parity. Reproduce with `benchmark/basic_handlers_benchmark.py`.

!!! note "A prior '3.14 regression' was an environment artifact"
    An earlier draft published a per-version table showing the file path at roughly half the speedup on Python 3.14. That was a measurement artifact, not a real regression: the 3.14 test venv had `sentry-sdk` installed while the 3.12 venv did not, and importing `sentry-sdk` pulled in `urllib3`'s formatter-less `NullHandler`, which forced process-global caller-frame collection on every log (a ~20% tax that only hit the 3.14 runs). This is fixed in 0.2.1. Environment-matched, CPython 3.12 and 3.14 are at parity, so the ranges here apply to both versions.

### Benchmark B — LogXide vs stdlib durable throughput (both Python versions)

Re-run this session on both Python 3.12.11 and 3.14.2, sink-verified 20,200 / 20,200. Durable speedup vs stdlib, rounded to ranges and comparable across the two versions:

| Sink     | Speedup vs stdlib         |
| :------- | :------------------------ |
| FILE     | **~6–11×**                |
| ROTATING | **~8–14×**                |
| STREAM   | **~5×** (async — see note) |

!!! warning "STREAM is asynchronous, not a guaranteed durable multiplier"
    LogXide's stream handler hands records to a background worker. It reaches ~5× stdlib when the queue fully drains (20,200 / 20,200 on an idle machine), but under a sustained max-rate emit burst its bounded queue can drop records — one loaded run delivered only ~14,420 / 20,200. Call `flush()` and inspect `get_metrics()` to confirm delivery; do not read STREAM as a durable multiplier the way FILE and ROTATING are.

### Cross-library runner-up snapshot

Among the other libraries that install on Python 3.13+ (stdlib, Loguru, Structlog), LogXide leads every sink. Durable throughput of the runner-ups on the reference machine (single cross-library run, rounded):

| Library        | FILE durable | STREAM durable | ROTATING durable |
| :------------- | -----------: | -------------: | ---------------: |
| Python logging |       74,605 |         53,292 |           42,981 |
| Structlog      |       41,364 |        116,796 |                — |
| Loguru         |       57,511 |         52,508 |           33,095 |

Structlog is the notable exception on the **stream** sink, where it beats stdlib at ~2.2× (116,796 vs 53,292 rec/s) and outruns Loguru — but LogXide still leads it there (~5× stdlib). On FILE and ROTATING, Structlog and Loguru both trail stdlib. Picologging is excluded from the corrected runs (it does not install on Python 3.13+, and the benchmark machine runs CPython 3.14.2), so no cross-library multiplier is asserted against it; see [comparison-picologging.md](comparison-picologging.md) for the qualitative discussion.

### Async accounting — durable vs lossy producers

Async handlers are only meaningful if "throughput" means records the sink confirmed, not records that were merely enqueued. After the run flushes, LogXide's accounting satisfies `in_flight == 0` and the identity `emitted == sink_acknowledged + queue_dropped + delivery_failed`. Two HTTP scenarios show the two honest outcomes:

| Scenario           | emitted | sink_acknowledged | queue_dropped | Producer behavior            |
| :----------------- | ------: | ----------------: | ------------: | :--------------------------- |
| `http_block`       |  20,000 |            20,000 |             0 | durable, producer p99 ~3 ms  |
| `http_drop_newest` |  20,000 |               260 |        19,740 | instant producer, lossy      |

`http_block` back-pressures the producer (slower calls, but every record lands). `http_drop_newest` returns instantly and drops under saturation, so its "producer throughput" would look enormous while only 260 records actually reached the sink. This is exactly the trap the old harness fell into; `get_metrics()` makes the distinction explicit.

### Micro benchmarks (LogXide native path, sink-verified)

Single-process producer micro-benchmarks via `benchmark/perf_micro.py`, sink-verified:

| Path                         | Throughput        |
| :--------------------------- | ----------------: |
| FileHandler (native)         | ~960K rec/s       |
| MemoryHandler (native)       | ~980K rec/s       |
| Filtered / no-op producer    | ~5.8M ops/s       |

!!! note "Numbers reflect 0.2.0 native-default dispatch"
    As of 0.2.0, the text-sink handler wrappers (`FileHandler`, `StreamHandler`, `RotatingFileHandler`) emit through the **native Rust fast path by default**. A handler only falls back to the Python path when it needs custom Python behavior: a custom `logging.Formatter` subclass, `{`- or `$`-style format strings, or a handler-level Python filter. The durable figures above measure the default native path.

### Architectural advantages (independent of any single benchmark)

Regardless of the exact numbers, LogXide's design has real, qualitative advantages:

1. **Native Rust I/O**: `FileHandler`/`RotatingFileHandler` write through a Rust `BufWriter` without materializing a Python `LogRecord` on the fast path.
2. **Background async I/O**: stream/HTTP/OTLP handlers hand records to a worker thread instead of blocking the caller on the sink.
3. **Explicit async accounting**: `get_metrics()` reports `emitted`, `sink_acknowledged`, `queue_dropped`, `delivery_failed`, and `in_flight`, so "throughput" always means records the sink confirmed — never records that were merely enqueued.

The corrected harness quantifies these advantages honestly: on this machine they show up as roughly ~6–11× stdlib on the file path and ~8–14× on rotating, plus ~5× on the async stream sink when it fully drains (durable, sink-verified), comparable on Python 3.12 and 3.14, rather than the inflated multipliers the old harness produced.

## File I/O Scenarios — vs stdlib `logging` (subprocess-isolated)

This is **Benchmark A**. Methodology: `benchmark/perf_vs_stdlib.py`, 50,000 iterations, FileHandler with the standard format `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`. LogXide and stdlib are each measured in isolation (stdlib in its own process so LogXide's import-time module override doesn't pollute the measurement). Re-run this session on macOS M4 Max, release build, on both Python 3.12.11 and 3.14.2.

!!! note "Scope of these numbers"
    These compare only LogXide against stdlib, each in its own process — the subprocess isolation the [audit](performance-bottleneck-report-2026-07-13.md) (§5) recommends. `FileHandler` is a **synchronous** Rust handler, so there is no async queue and "durable throughput" equals producer throughput here; no records are dropped. The figures are machine-specific and rounded to ranges (baselines are noisy run-to-run, roughly ±40%), and they measure the standard format-string scenarios. The corrected, sink-verified cross-library and async-handler numbers are published in the [comparative section above](#comparative-benchmark--all-logging-libraries-corrected-sink-verified).

### Speedup vs stdlib (comparable on both Python versions)

Rounded speedup vs stdlib. CPython 3.12 and 3.14 land at parity once the environments match, so a single range covers both:

| Scenario   | Speedup vs stdlib |
| :--------- | :---------------- |
| simple     | **~7–9×**         |
| structured | **~7–9×**         |
| `%`-args   | **~5–6×**         |

For reference, LogXide absolute throughput lands around 1.0–1.4M rec/s on the simple and structured scenarios and ~0.8–0.9M rec/s on `%`-args, while stdlib sits around 0.12–0.17M rec/s; exact rec/s swings run-to-run, which is why the table reports ranges.

LogXide is faster on both versions. There is no intrinsic Python 3.14 regression: an earlier draft that showed 3.14 at roughly half the file-path speedup was measuring a `sentry-sdk` environment artifact (see the note in the comparative section), fixed in 0.2.1. Every figure is machine-specific and rounded.

### Why LogXide is faster

1. **Native Rust I/O**: Direct `BufWriter` syscalls without Python overhead
2. **Zero-allocation formatter hot path**: `itoa::Buffer` + `write!` macros + lazy asctime
3. **Thread-local format scratch buffer**: Capacity is reused across calls
4. **Lock-free handler dispatch**: `arc_swap::ArcSwap` for the global handler registry
5. **Cached caller-info via Python helper**: Single `_getframe(1)` call instead of 6 `getattr` round-trips
6. **No JSON round-trip on `args`**: Stored as `Arc<serde_json::Value>` directly

## Historical Benchmarks (Legacy Results)

!!! warning "Legacy cross-library numbers — not evidence"
    The numbers in this section come from an older cross-library harness of the same family flagged in the [performance audit](performance-bottleneck-report-2026-07-13.md) (§5). They use a different iteration count, formatting setup, Python/OS environment, and measurement methodology, and they share the same reliability problems (no sink verification, async drops counted as throughput, same-process library imports). They are kept only as a historical record and must **not** be cited as performance evidence or compared against any other table. Treat them as withdrawn pending re-measurement with the corrected harness.

### Python 3.12.6 - Complete Library Comparison

#### FileHandler Performance
| Rank | Library | Messages/sec | Relative Performance | Speedup vs Baseline |
|------|---------|-------------|---------------------|---------------------|
| 1st | **LogXide** | **2,091,663** | **1.00x** | **12.5x faster** |
| 2nd | Structlog | 1,288,187 | 0.62x | 7.7x faster |
| 3rd | Picologging | 446,114 | 0.21x | 2.7x faster |
| 4th | Python logging | 166,833 | 0.08x | 1.0x (baseline) |
| 5th | Logbook | 145,410 | 0.07x | 0.9x |
| 6th | Loguru | 132,228 | 0.06x | 0.8x |

#### StreamHandler Performance
| Rank | Library | Messages/sec | Relative Performance | Speedup vs Baseline |
|------|---------|-------------|---------------------|---------------------|
| 1st | **LogXide** | **2,137,244** | **1.00x** | **186.2x faster** |
| 2nd | Structlog | 1,222,748 | 0.57x | 106.5x faster |
| 3rd | Picologging | 802,598 | 0.38x | 69.9x faster |
| 4th | Python logging | 11,474 | 0.01x | 1.0x (baseline) |
| 5th | Logbook | 147,733 | 0.07x | 12.9x faster |
| 6th | Loguru | 8,438 | 0.004x | 0.7x |

#### RotatingFileHandler Performance
| Rank | Library | Messages/sec | Relative Performance | Speedup vs Baseline |
|------|---------|-------------|---------------------|---------------------|
| 1st | **LogXide** | **2,205,392** | **1.00x** | **17.7x faster** |
| 2nd | Picologging | 435,633 | 0.20x | 3.5x faster |
| 3rd | Python logging | 124,900 | 0.06x | 1.0x (baseline) |
| 4th | Loguru | 114,459 | 0.05x | 0.9x |

## Detailed Performance Comparison

### LogXide Advantages

**1. Real I/O Operations**
- Runs actual file writes through Rust's native `BufWriter` rather than synthetic no-ops
- Efficient buffering and system call optimization
- Cross-library durable throughput is now sink-verified: on the file path LogXide is ~6–11× stdlib, ~8–14× on rotating, and ~5× on the async stream sink (comparable on Python 3.12 and 3.14; see the [corrected comparative section](#comparative-benchmark--all-logging-libraries-corrected-sink-verified)); Picologging is excluded because it does not install on Python 3.13+

**2. Consistent Performance**
- Maintains advantage across all logging patterns
- No performance degradation with structured logging
- Stable performance under high load

**3. Production Ready**
- Best performance where it matters: actual logging operations
- Optimized for real-world usage patterns
- Scales well with application complexity

### When to Choose Each Library

**Choose LogXide when:**
- You need maximum performance in production
- Your application does significant logging to files
- You want a drop-in replacement with better performance
- You value consistent performance across scenarios

**Choose Picologging when:**
- You primarily need stdout/stderr logging
- Your application rarely logs (mostly disabled)
- You need absolute minimal overhead for disabled logging

**Choose Structlog when:**
- You need advanced structured logging features
- Performance is not a primary concern
- You want maximum flexibility in log processing

## Test Reproducibility

### Running the Benchmarks

```bash
# Recommended: File I/O benchmark (most realistic)
cd logxide
source .venv312/bin/activate  # Use Python 3.12 environment
python benchmark/compare_loggers.py

# Results are saved to: logger_comparison_file_io_TIMESTAMP.json
```

### Benchmark Configuration

**Environment Setup:**
```bash
# Create Python 3.12 environment
python3.12 -m venv .venv312
source .venv312/bin/activate

# Install dependencies
pip install structlog picologging

# Build LogXide
maturin develop --release

# Run benchmarks
python benchmark/compare_loggers.py
```

**Test Conditions:**
- Format string: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Multiple runs (3 iterations) with statistical averaging
- Garbage collection between test runs
- Temporary files created and cleaned up per test
- Consistent hardware and Python environment

## Conclusions

### Recommendation: LogXide for Production

**LogXide is the best choice for production Python applications:**

1. **Strong file-I/O performance**: Against stdlib in the subprocess-isolated, synchronous-`FileHandler` scenario, LogXide is substantially faster. The corrected, sink-verified harness puts LogXide at ~6–11× stdlib on the durable file path and ~8–14× on rotating, plus ~5× on the async stream sink when it fully drains; exact multipliers are machine- and scenario-specific, and Python 3.12 and 3.14 are at parity.
2. **Real-World Testing**: Benchmarks based on actual file operations, not synthetic tests
3. **Drop-in Replacement**: No code changes required for common patterns
4. **Native Performance**: Rust's efficiency provides measurable benefits

### Performance Summary Table (durable, sink-verified)

The old per-library summary that reranked everything from the defective harness has been replaced by the corrected, sink-verified [comparative tables above](#comparative-benchmark--all-logging-libraries-corrected-sink-verified). On the reference machine (macOS M4 Max), re-run this session on both Python 3.12.11 and 3.14.2, the durable headline is: LogXide leads every sink, at roughly ~6–11× stdlib on file and ~8–14× on rotating, plus ~5× on the async stream sink. The two Python versions come out at parity. Structlog is the runner-up on stream (~2.2× stdlib). Every figure is machine-specific and rounded to ranges to avoid false precision.

### Key Takeaways

1. **LogXide is designed for real-world file I/O**: the durable path writes through a Rust `BufWriter` with no Python `LogRecord` on the fast path
2. **Cross-library gaps are now sink-verified**: LogXide leads all measured libraries on durable throughput (~6–11× stdlib on file, ~8–14× on rotating, ~5× on the async stream sink; comparable on Python 3.12 and 3.14); numbers are machine-specific and reproduced via `benchmark/basic_handlers_benchmark.py`
3. **Rust advantage is architectural**: native code and background async I/O provide measurable benefits, quantified honestly by the corrected harness
4. **Async delivery is accounted**: `get_metrics()` distinguishes delivered records from dropped ones, so async "throughput" is never inflated by drops

**LogXide targets performance where it matters most: actual logging operations in production applications, measured honestly.**

---

*Benchmarks conducted on macOS ARM64 (Apple Silicon) with Python 3.12.11 (`pyenv`) and Python 3.14.2. Results may vary on different platforms but relative performance should be consistent.*
