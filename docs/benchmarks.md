# LogXide Performance Benchmarks

This document provides comprehensive performance analysis of LogXide compared to other Python logging libraries.

## Test Environment

- **Platform**: macOS 15.5 ARM64 (Apple Silicon)
- **Python**: 3.12.6
- **Test Methodology**: Multiple runs with averages, garbage collection between tests
- **Libraries Tested**: LogXide, Picologging, Structlog, Python logging, Loguru, Logbook

## Handler-Based Benchmarks (Real I/O)

These benchmarks test actual file and stream I/O operations, representing real-world usage scenarios.

### FileHandler Performance

*Test: 10,000 messages, actual file writing with formatting*

| Rank | Library | Messages/sec | Relative Performance |
|------|---------|-------------|---------------------|
| 🥇 | **LogXide** | **8,637,132** | **1.00x** |
| 🥈 | Picologging | 463,006 | 0.05x (18.7x slower) |
| 🥉 | Structlog | 176,275 | 0.02x (49x slower) |

**Key Findings:**
- LogXide is **18.7x faster** than Picologging for file operations
- LogXide is **49x faster** than Structlog for file operations
- LogXide's async architecture excels at I/O-bound operations

### StreamHandler Performance

*Test: 10,000 messages, actual stream output with formatting*

| Rank | Library | Messages/sec | Relative Performance |
|------|---------|-------------|---------------------|
| 🥇 | **LogXide** | **9,945,301** | **1.00x** |
| 🥈 | Picologging | 775,115 | 0.08x (12.8x slower) |
| 🥉 | Structlog | 216,878 | 0.02x (45.8x slower) |

**Key Findings:**
- LogXide is **12.8x faster** than Picologging for stream operations
- LogXide is **45.8x faster** than Structlog for stream operations
- LogXide achieves nearly 10 million operations per second

## Memory-Based Benchmarks

These benchmarks test pure logging performance without I/O overhead, focusing on message processing efficiency.

### Active Logging Performance

*Test: 100,000 iterations, in-memory logging*

| Test Scenario | LogXide (ops/sec) | Picologging (ops/sec) | Structlog (ops/sec) | LogXide vs Picologging |
|--------------|-------------------|---------------------|-------------------|----------------------|
| **Simple Logging** | **1,371,829** | 1,177,578 | 245,301 | **1.16x faster** 🏆 |
| **Structured Logging** | **1,167,209** | 1,108,635 | 220,907 | **1.05x faster** 🏆 |
| **Error Logging** | **1,209,617** | 1,051,541 | 224,371 | **1.15x faster** 🏆 |

**Key Findings:**
- LogXide maintains 5-16% performance advantage over Picologging in memory operations
- LogXide is consistently 5-6x faster than Structlog
- Performance advantage is smaller without I/O overhead

### Disabled Logging Performance

*Test: 100,000 iterations, messages filtered out by log level*

| Library | Operations/sec | Performance |
|---------|----------------|-------------|
| **Picologging** | **27,285,067** | **Fastest** 🏆 |
| LogXide | 10,106,429 | 2.7x slower |
| Structlog | 231,104 | 118x slower |

**Key Findings:**
- Picologging excels at disabled logging scenarios
- LogXide still outperforms Structlog by 44x in disabled scenarios
- This represents an optimization opportunity for LogXide

## Historical Benchmarks (Legacy Results)

### Python 3.12.6 - Complete Library Comparison

#### FileHandler Performance
| Rank | Library | Messages/sec | Relative Performance | Speedup vs Baseline |
|------|---------|-------------|---------------------|---------------------|
| 🥇 | **LogXide** | **2,091,663** | **1.00x** | **12.5x faster** |
| 🥈 | Structlog | 1,288,187 | 0.62x | 7.7x faster |
| 🥉 | Picologging | 446,114 | 0.21x | 2.7x faster |
| 4th | Python logging | 166,833 | 0.08x | 1.0x (baseline) |
| 5th | Logbook | 145,410 | 0.07x | 0.9x |
| 6th | Loguru | 132,228 | 0.06x | 0.8x |

#### StreamHandler Performance  
| Rank | Library | Messages/sec | Relative Performance | Speedup vs Baseline |
|------|---------|-------------|---------------------|---------------------|
| 🥇 | **LogXide** | **2,137,244** | **1.00x** | **186.2x faster** |
| 🥈 | Structlog | 1,222,748 | 0.57x | 106.5x faster |
| 🥉 | Picologging | 802,598 | 0.38x | 69.9x faster |
| 4th | Python logging | 11,474 | 0.01x | 1.0x (baseline) |
| 5th | Logbook | 147,733 | 0.07x | 12.9x faster |
| 6th | Loguru | 8,438 | 0.004x | 0.7x |

#### RotatingFileHandler Performance
| Rank | Library | Messages/sec | Relative Performance | Speedup vs Baseline |
|------|---------|-------------|---------------------|---------------------|
| 🥇 | **LogXide** | **2,205,392** | **1.00x** | **17.7x faster** |
| 🥈 | Picologging | 435,633 | 0.20x | 3.5x faster |
| 3rd | Python logging | 124,900 | 0.06x | 1.0x (baseline) |
| 4th | Loguru | 114,459 | 0.05x | 0.9x |

## Performance Analysis

### Where LogXide Excels

1. **I/O-Heavy Operations**: LogXide's async architecture provides massive advantages for file and stream operations
   - 10-50x faster than competitors in real I/O scenarios
   - Async message processing prevents blocking

2. **High-Throughput Scenarios**: Consistent performance across different logging patterns
   - Maintains speed regardless of message complexity
   - Excellent for applications with heavy logging requirements

3. **Multi-Handler Scenarios**: Concurrent handler execution
   - Parallel processing of multiple output destinations
   - Scales well with increasing handler complexity

### Where Competitors Excel

1. **Disabled Logging**: Picologging is significantly faster for filtered-out messages
   - 2.7x faster than LogXide for disabled logging
   - Represents an optimization opportunity for LogXide

2. **Minimal Overhead**: For applications that rarely log, Picologging may be preferred

### Optimization Opportunities

1. **Disabled Logging Performance**: LogXide could implement faster level checking
2. **Cold Start Performance**: Initial setup time optimization
3. **Memory Usage**: Further optimization of memory allocations

## Test Reproducibility

### Running the Benchmarks

```bash
# Handler-based benchmarks (recommended for real-world comparison)
python benchmark/real_handlers_comparison.py

# Memory-based logging benchmarks
python benchmark/compare_loggers.py

# Complete library comparison (all libraries)
python benchmark/basic_handlers_benchmark.py
```

### Benchmark Scripts

- **`real_handlers_comparison.py`**: Tests FileHandler and StreamHandler with actual I/O
- **`compare_loggers.py`**: Tests in-memory logging performance and disabled logging
- **`basic_handlers_benchmark.py`**: Comprehensive comparison across all libraries

### Test Conditions

All benchmarks use:
- Consistent message formatting: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Multiple runs with statistical averaging
- Garbage collection between tests
- Same hardware and Python environment

## Conclusions

### For Most Applications: LogXide

LogXide is the clear choice for most Python applications because:

1. **Real-world performance**: 10-50x faster in actual I/O scenarios
2. **Consistent performance**: Excellent across all logging patterns
3. **Drop-in compatibility**: No code changes required
4. **Future-proof**: Async architecture ready for modern Python

### For Minimal Logging: Consider Picologging

Picologging may be preferred if:

1. Your application rarely logs (mostly disabled logging)
2. Minimal overhead is critical
3. You don't need async processing

### Performance Summary

| Scenario | LogXide | Picologging | Structlog |
|----------|---------|-------------|-----------|
| **FileHandler** | 🏆 **Best** | Good | Fair |
| **StreamHandler** | 🏆 **Best** | Good | Fair |
| **Active Logging** | 🏆 **Best** | Very Good | Fair |
| **Disabled Logging** | Good | 🏆 **Best** | Poor |
| **Overall** | 🏆 **Best** | Very Good | Fair |

**LogXide delivers exceptional performance where it matters most: when your application is actually logging.**