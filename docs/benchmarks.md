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
| 1st | **LogXide** | **439,913** | 0.227 | **Fastest** |
| 2nd | Picologging | 352,800 | 0.283 | 1.25x slower |
| 3rd | Structlog | 179,948 | 0.556 | 2.44x slower |

### Structured Logging Performance

*Test: 100,000 messages with structured context (key-value pairs)*

| Rank | Library | Ops/sec | Avg Time (s) | Relative Performance |
|------|---------|---------|--------------|---------------------|
| 1st | **LogXide** | **416,242** | 0.240 | **Fastest** |
| 2nd | Picologging | 371,144 | 0.269 | 1.12x slower |
| 3rd | Structlog | 165,936 | 0.603 | 2.51x slower |

### Error Logging Performance

*Test: 100,000 error messages with exception context*

| Rank | Library | Ops/sec | Avg Time (s) | Relative Performance |
|------|---------|---------|--------------|---------------------|
| 1st | **LogXide** | **411,238** | 0.243 | **Fastest** |
| 2nd | Picologging | 353,487 | 0.283 | 1.16x slower |
| 3rd | Structlog | 170,498 | 0.587 | 2.41x slower |

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
- 12-25% faster than Picologging in actual file writing
- Rust's native I/O provides measurable performance gains
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

1. **Proven Performance**: 12-25% faster than Picologging in real file I/O
2. **Real-World Testing**: Benchmarks based on actual file operations, not synthetic tests
3. **Drop-in Replacement**: No code changes required, instant performance gains
4. **Consistent Speed**: Maintains advantage across all logging patterns
5. **Native Performance**: Rust's efficiency provides measurable benefits

### Performance Summary Table

| Scenario | LogXide | Picologging | Structlog | Winner |
|----------|---------|-------------|-----------|---------|
| **File I/O** | 411-440k ops/sec | 353-371k ops/sec | 166-180k ops/sec | **LogXide** |
| **Simple Logging** | **439,913** ops/sec | 352,800 ops/sec | 179,948 ops/sec | **LogXide** |
| **Structured Logging** | **416,242** ops/sec | 371,144 ops/sec | 165,936 ops/sec | **LogXide** |
| **Error Logging** | **411,238** ops/sec | 353,487 ops/sec | 170,498 ops/sec | **LogXide** |
| **Overall** | **Best** | Very Good | Good | **LogXide** |

### Key Takeaways

1. **LogXide wins in real-world scenarios**: File I/O benchmarks show clear advantage
2. **Performance gap is significant**: 12-25% faster is noticeable at scale
3. **Rust advantage is real**: Native code provides measurable benefits over C (Picologging)
4. **Consistent across patterns**: LogXide maintains advantage in simple, structured, and error logging

**LogXide delivers superior performance where it matters most: actual logging operations in production applications.**

---

*Benchmarks conducted on macOS ARM64 with Python 3.12.12. Results may vary on different platforms but relative performance should be consistent.*
