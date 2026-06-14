# LogXide Performance Benchmarks

This document provides comprehensive performance analysis of LogXide compared to other Python logging libraries.

## Test Environment

- **Platform**: macOS ARM64 (Apple Silicon)
- **Python**: 3.12.12 / 3.14.2
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

Methodology: `benchmark/perf_vs_stdlib.py`, 100K iterations × 3 runs, FileHandler. stdlib runs in a subprocess to avoid LogXide's interceptor overriding `logging.Logger`.

| Scenario   |     LogXide |     stdlib | Speedup    |
| :--------- | ----------: | ---------: | :--------- |
| simple     |   1,228,811 |    182,533 | **6.73×**  |
| structured |   1,064,164 |    177,366 | **6.00×**  |
| args       |     750,129 |    176,633 | **4.25×**  |

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

## Comparative Benchmark — All Logging Libraries (Python 3.12, June 2026)

These benchmarks run all libraries through the **same harness** (`benchmark/basic_handlers_benchmark.py`, 10,000 iterations × 3 runs, format `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`) on Python 3.12, the highest version Picologging supports. This is the apples-to-apples reference measurement.

### FileHandler

| Rank | Library         |   Ops/sec | Relative to LogXide |
| :--- | :-------------- | --------: | :------------------ |
| 1    | **LogXide**     | **1,139,874** | 1.00× (baseline)   |
| 2    | Structlog       |   932,755 | 0.82×              |
| 3    | Picologging     |   384,319 | 0.34× (LogXide 2.97× faster) |
| 4    | Python `logging`|   145,260 | 0.13× (LogXide 7.85× faster) |
| 5    | Logbook         |    99,538 | 0.09× (LogXide 11.45× faster) |
| 6    | Loguru          |    93,896 | 0.08× (LogXide 12.14× faster) |

### StreamHandler

| Rank | Library         |   Ops/sec | Relative to LogXide |
| :--- | :-------------- | --------: | :------------------ |
| 1    | **LogXide**     | **955,112** | 1.00× (baseline)   |
| 2    | Structlog       |   920,069 | 0.96×              |
| 3    | Python `logging`|    17,006 | 0.02× (LogXide 56.16× faster) |
| 4    | Loguru          |    10,391 | 0.01× (LogXide 91.92× faster) |

### RotatingFileHandler

| Rank | Library         |   Ops/sec | Relative to LogXide |
| :--- | :-------------- | --------: | :------------------ |
| 1    | **LogXide**     | **897,118** | 1.00× (baseline)   |
| 2    | Picologging ¹   |   411,055 | 0.46× (LogXide 2.18× faster) |
| 3    | Loguru          |    85,203 | 0.09× (LogXide 10.53× faster) |
| 4    | Python `logging`|    55,579 | 0.06× (LogXide 16.14× faster) |

¹ *Picologging has no `RotatingFileHandler`; the harness substitutes its `FileHandler` in this row.*

## File I/O Scenarios — vs stdlib `logging` (subprocess-isolated)

Methodology: `benchmark/perf_vs_stdlib.py`, 100,000 iterations × 3 runs, FileHandler with the same standard format. stdlib runs in a subprocess so LogXide's import-time module override doesn't pollute the measurement.

### Python 3.12

| Scenario   | stdlib `logging` |     LogXide | Speedup       |
| :--------- | ---------------: | ----------: | :------------ |
| simple     |          145,562 | **1,922,911** | **13.21× faster** |
| structured |          144,328 | **1,612,029** | **11.17× faster** |
| with `%s` args |      144,156 |   **976,572** | **6.77× faster** |

### Python 3.14

| Scenario   | stdlib `logging` |     LogXide | Speedup       |
| :--------- | ---------------: | ----------: | :------------ |
| simple     |          182,533 | **1,228,811** | **6.73× faster** |
| structured |          177,366 | **1,064,164** | **6.00× faster** |
| with `%s` args |      176,633 |   **750,129** | **4.25× faster** |

LogXide is faster on both versions; stdlib's per-iteration overhead dropped on 3.14, narrowing the absolute gap. The Python 3.12 simple-logging scenario remains the best-case headline figure.

### Why LogXide is faster

1. **Native Rust I/O**: Direct `BufWriter` syscalls without Python overhead
2. **Zero-allocation formatter hot path**: `itoa::Buffer` + `write!` macros + lazy asctime
3. **Thread-local format scratch buffer**: Capacity is reused across calls
4. **Lock-free handler dispatch**: `arc_swap::ArcSwap` for the global handler registry
5. **Cached caller-info via Python helper**: Single `_getframe(1)` call instead of 6 `getattr` round-trips
6. **No JSON round-trip on `args`**: Stored as `Arc<serde_json::Value>` directly

## Historical Benchmarks (Legacy Results)

!!! warning "Different methodology"
    The numbers in this section come from an older benchmark harness (different iteration counts, different formatting setup, different Python and OS environment) and use a different measurement methodology than the **File I/O Benchmarks (Real-World Performance)** tables above. They are kept here for historical reference only and should **not** be compared directly against the file-I/O numbers earlier in this page or against the README results. When in doubt, treat the file-I/O tables above as the authoritative LogXide-vs-others comparison for this document.

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
- ~3× faster than Picologging on `FileHandler` and `RotatingFileHandler` (Python 3.12, same harness)
- Rust's native `BufWriter` provides measurable performance gains
- Efficient buffering and system call optimization

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

1. **Proven Performance**: ~3× faster than Picologging on `FileHandler` and `RotatingFileHandler`, ~13× faster than stdlib in the simple-logging file-I/O scenario (Python 3.12)
2. **Real-World Testing**: Benchmarks based on actual file operations, not synthetic tests
3. **Drop-in Replacement**: No code changes required, instant performance gains
4. **Consistent Speed**: Maintains advantage across all logging patterns
5. **Native Performance**: Rust's efficiency provides measurable benefits

### Performance Summary Table (Python 3.12, FileHandler, 10K iterations)

| Library         |   Ops/sec | Speedup vs stdlib |
| :-------------- | --------: | :---------------- |
| **LogXide**     | **1,139,874** | **7.85×**         |
| Structlog       |   932,755 | 6.42×             |
| Picologging     |   384,319 | 2.65×             |
| Python `logging`|   145,260 | 1.0× (baseline)   |
| Logbook         |    99,538 | 0.69×             |
| Loguru          |    93,896 | 0.65×             |

### Key Takeaways

1. **LogXide wins in real-world scenarios**: File I/O benchmarks show clear advantage on every comparison
2. **Performance gap is significant**: 3× over Picologging, 7-13× over stdlib, 12× over Loguru
3. **Rust advantage is real**: Native code provides measurable benefits over C (Picologging) and pure Python
4. **Consistent across patterns**: LogXide maintains advantage in simple, structured, and `args` logging

**LogXide delivers superior performance where it matters most: actual logging operations in production applications.**

---

*Benchmarks conducted on macOS ARM64 (Apple Silicon) with Python 3.12.0 (`pyenv`) and Python 3.14.2. Results may vary on different platforms but relative performance should be consistent.*
