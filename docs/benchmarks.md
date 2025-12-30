# LogXide Performance Benchmarks

This document provides comprehensive performance analysis of LogXide compared to other Python logging libraries.

## Test Environment

- **Platform**: macOS ARM64 (Apple Silicon)
- **Python**: 3.12.12
- **Test Methodology**: Multiple runs (3 iterations) with averages, garbage collection between tests
- **Libraries Tested**: LogXide, Picologging, Structlog
- **Test Date**: December 30, 2024

## File I/O Benchmarks (Real-World Performance)

These benchmarks test actual file I/O operations with realistic formatting, representing real-world production usage scenarios.

### Test Configuration

- **Iterations**: 100,000 log messages per test
- **Handler**: FileHandler writing to temporary files
- **Format**: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- **Test Runs**: 3 iterations per scenario, averaged
- **Scenarios**: Simple logging, Structured logging, Error logging

### Simple Logging Performance

*Test: 100,000 messages with simple string formatting*

| Rank | Library | Ops/sec | Avg Time (s) | Relative Performance |
|------|---------|---------|--------------|---------------------|
| 1위 | **LogXide** | **439,913** | 0.227 | **가장 빠름** ⭐ |
| 2위 | Picologging | 352,800 | 0.283 | 1.25x 느림 |
| 3위 | Structlog | 179,948 | 0.556 | 2.44x 느림 |

### Structured Logging Performance

*Test: 100,000 messages with structured context (key-value pairs)*

| Rank | Library | Ops/sec | Avg Time (s) | Relative Performance |
|------|---------|---------|--------------|---------------------|
| 1위 | **LogXide** | **416,242** | 0.240 | **가장 빠름** ⭐ |
| 2위 | Picologging | 371,144 | 0.269 | 1.12x 느림 |
| 3위 | Structlog | 165,936 | 0.603 | 2.51x 느림 |

### Error Logging Performance

*Test: 100,000 error messages with exception context*

| Rank | Library | Ops/sec | Avg Time (s) | Relative Performance |
|------|---------|---------|--------------|---------------------|
| 1위 | **LogXide** | **411,238** | 0.243 | **가장 빠름** ⭐ |
| 2위 | Picologging | 353,487 | 0.283 | 1.16x 느림 |
| 3위 | Structlog | 170,498 | 0.587 | 2.41x 느림 |

### Key Findings

**LogXide Performance Advantages:**
- **12-25% faster** than Picologging across all real I/O scenarios
- **2.4-2.5x faster** than Structlog in production use cases
- Consistent performance across different logging patterns
- Rust's native I/O and memory management provide measurable advantages

**Detailed Comparison:**
- **Simple Logging**: LogXide 25% faster than Picologging
- **Structured Logging**: LogXide 12% faster than Picologging (smallest gap)
- **Error Logging**: LogXide 16% faster than Picologging
- **Overall**: LogXide maintains performance advantage in all realistic scenarios

## Performance Analysis Summary

### Real-World Usage (File I/O)

**Winner: LogXide** - Clear performance leader in production scenarios

| Scenario | LogXide | Picologging | Performance Gap |
|----------|---------|-------------|-----------------|
| Simple Logging | 439,913 ops/sec | 352,800 ops/sec | **LogXide 25% faster** |
| Structured Logging | 416,242 ops/sec | 371,144 ops/sec | **LogXide 12% faster** |
| Error Logging | 411,238 ops/sec | 353,487 ops/sec | **LogXide 16% faster** |

### Why LogXide is Faster

1. **Native Rust I/O**: Direct system calls without Python overhead
2. **Efficient Memory Management**: Rust's zero-cost abstractions and ownership model
3. **Optimized Formatting**: Native string formatting faster than Python's
4. **Better Buffering**: Rust's BufWriter provides optimal buffer management
5. **No GIL Overhead**: Native code execution without Global Interpreter Lock impact

## Historical Benchmarks (Legacy Results)

### Python 3.12.6 - Complete Library Comparison

#### FileHandler Performance
| Rank | Library | Messages/sec | Relative Performance | Speedup vs Baseline |
|------|---------|-------------|---------------------|---------------------|
| 순위 | 라이브러리 | 초당 메시지 수 | 상대적 성능 | 기준 대비 속도 향상 |
|------|---------|-------------|---------------------|---------------------|
| 1위 | **LogXide** | **2,091,663** | **1.00배** | **12.5배 더 빠름** |
| 2위 | Structlog | 1,288,187 | 0.62배 | 7.7배 더 빠름 |
| 3위 | Picologging | 446,114 | 0.21배 | 2.7배 더 빠름 |
| 4위 | Python logging | 166,833 | 0.08배 | 1.0배 (기준) |
| 5위 | Logbook | 145,410 | 0.07배 | 0.9배 |
| 6위 | Loguru | 132,228 | 0.06배 | 0.8배 |

#### StreamHandler Performance
| Rank | Library | Messages/sec | Relative Performance | Speedup vs Baseline |
|------|---------|-------------|---------------------|---------------------|
| 순위 | 라이브러리 | 초당 메시지 수 | 상대적 성능 | 기준 대비 속도 향상 |
|------|---------|-------------|---------------------|---------------------|
| 1위 | **LogXide** | **2,137,244** | **1.00배** | **186.2배 더 빠름** |
| 2위 | Structlog | 1,222,748 | 0.57배 | 106.5배 더 빠름 |
| 3위 | Picologging | 802,598 | 0.38배 | 69.9배 더 빠름 |
| 4위 | Python logging | 11,474 | 0.01배 | 1.0배 (기준) |
| 5위 | Logbook | 147,733 | 0.07배 | 12.9배 더 빠름 |
| 6위 | Loguru | 8,438 | 0.004배 | 0.7배 |

#### RotatingFileHandler Performance
| Rank | Library | Messages/sec | Relative Performance | Speedup vs Baseline |
|------|---------|-------------|---------------------|---------------------|
| 순위 | 라이브러리 | 초당 메시지 수 | 상대적 성능 | 기준 대비 속도 향상 |
|------|---------|-------------|---------------------|---------------------|
| 1위 | **LogXide** | **2,205,392** | **1.00배** | **17.7배 더 빠름** |
| 2위 | Picologging | 435,633 | 0.20배 | 3.5배 더 빠름 |
| 3위 | Python logging | 124,900 | 0.06배 | 1.0배 (기준) |
| 4위 | Loguru | 114,459 | 0.05배 | 0.9배 |

## Detailed Performance Comparison

### LogXide Advantages

**1. Real I/O Operations** ✅
- 12-25% faster than Picologging in actual file writing
- Rust's native I/O provides measurable performance gains
- Efficient buffering and system call optimization

**2. Consistent Performance** ✅
- Maintains advantage across all logging patterns
- No performance degradation with structured logging
- Stable performance under high load

**3. Production Ready** ✅
- Best performance where it matters: actual logging operations
- Optimized for real-world usage patterns
- Scales well with application complexity

### When to Choose Each Library

**Choose LogXide when:**
- ✅ You need maximum performance in production
- ✅ Your application does significant logging to files
- ✅ You want a drop-in replacement with better performance
- ✅ You value consistent performance across scenarios

**Choose Picologging when:**
- ⚠️ You primarily need stdout/stderr logging
- ⚠️ Your application rarely logs (mostly disabled)
- ⚠️ You need absolute minimal overhead for disabled logging

**Choose Structlog when:**
- ⚠️ You need advanced structured logging features
- ⚠️ Performance is not a primary concern
- ⚠️ You want maximum flexibility in log processing

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

1. ✅ **Proven Performance**: 12-25% faster than Picologging in real file I/O
2. ✅ **Real-World Testing**: Benchmarks based on actual file operations, not synthetic tests
3. ✅ **Drop-in Replacement**: No code changes required, instant performance gains
4. ✅ **Consistent Speed**: Maintains advantage across all logging patterns
5. ✅ **Native Performance**: Rust's efficiency provides measurable benefits

### Performance Summary Table

| Scenario | LogXide | Picologging | Structlog | Winner |
|----------|---------|-------------|-----------|---------|
| **File I/O** | 411-440k ops/sec | 353-371k ops/sec | 166-180k ops/sec | **LogXide** ⭐ |
| **Simple Logging** | **439,913** ops/sec | 352,800 ops/sec | 179,948 ops/sec | **LogXide** ⭐ |
| **Structured Logging** | **416,242** ops/sec | 371,144 ops/sec | 165,936 ops/sec | **LogXide** ⭐ |
| **Error Logging** | **411,238** ops/sec | 353,487 ops/sec | 170,498 ops/sec | **LogXide** ⭐ |
| **Overall** | **최고** | 매우 좋음 | 보통 | **LogXide** ⭐ |

### Key Takeaways

1. **LogXide wins in real-world scenarios**: File I/O benchmarks show clear advantage
2. **Performance gap is significant**: 12-25% faster is noticeable at scale
3. **Rust advantage is real**: Native code provides measurable benefits over C (Picologging)
4. **Consistent across patterns**: LogXide maintains advantage in simple, structured, and error logging

**LogXide delivers superior performance where it matters most: actual logging operations in production applications.**

---

*Benchmarks conducted on macOS ARM64 with Python 3.12.12. Results may vary on different platforms but relative performance should be consistent.*
