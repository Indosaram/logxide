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
| 순위 | 라이브러리 | 초당 메시지 수 | 상대적 성능 |
|------|---------|-------------|---------------------|
| 1위 | **LogXide** | **8,637,132** | **1.00배** |
| 2위 | Picologging | 463,006 | 0.05배 (LogXide보다 18.7배 느림) |
| 3위 | Structlog | 176,275 | 0.02배 (LogXide보다 49배 느림) |

**Key Findings:**
- LogXide is **18.7x faster** than Picologging for file operations
- LogXide is **49x faster** than Structlog for file operations
- LogXide's async architecture excels at I/O-bound operations

### StreamHandler Performance

*Test: 10,000 messages, actual stream output with formatting*

| Rank | Library | Messages/sec | Relative Performance |
|------|---------|-------------|---------------------|
| 순위 | 라이브러리 | 초당 메시지 수 | 상대적 성능 |
|------|---------|-------------|---------------------|
| 1위 | **LogXide** | **9,945,301** | **1.00배** |
| 2위 | Picologging | 775,115 | 0.08배 (LogXide보다 12.8배 느림) |
| 3위 | Structlog | 216,878 | 0.02배 (LogXide보다 45.8배 느림) |

**Key Findings:**
- LogXide is **12.8x faster** than Picologging for stream operations
- LogXide is **45.8x faster** than Structlog for stream operations
- LogXide achieves nearly 10 million operations per second

## Memory-Based Benchmarks

These benchmarks test pure logging performance without I/O overhead, focusing on message processing efficiency.

### Active Logging Performance

*Test: 100,000 iterations, in-memory logging*

| 테스트 시나리오 | LogXide (초당 작업 수) | Picologging (초당 작업 수) | Structlog (초당 작업 수) | LogXide vs Picologging |
|--------------|-------------------|---------------------|-------------------|----------------------|
| **단순 로깅** | **1,371,829** | 1,177,578 | 245,301 | **1.16배 더 빠름** |
| **구조화된 로깅** | **1,167,209** | 1,108,635 | 220,907 | **1.05배 더 빠름** |
| **오류 로깅** | **1,209,617** | 1,051,541 | 224,371 | **1.15배 더 빠름** |

**Key Findings:**
- LogXide maintains 5-16% performance advantage over Picologging in memory operations
- LogXide is consistently 5-6x faster than Structlog
- Performance advantage is smaller without I/O overhead

### Disabled Logging Performance

*Test: 100,000 iterations, messages filtered out by log level*

| 라이브러리 | 초당 작업 수 | 성능 |
|---------|----------------|-------------|
| **Picologging** | **27,285,067** | **가장 빠름** |
| LogXide | 10,106,429 | 2.7배 느림 |
| Structlog | 231,104 | 118배 느림 |

**Key Findings:**
- Picologging excels at disabled logging scenarios
- LogXide still outperforms Structlog by 44x in disabled scenarios
- This represents an optimization opportunity for LogXide

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

| 시나리오 | LogXide | Picologging | Structlog |
|----------|---------|-------------|-----------|
| **FileHandler** | **최고** | 좋음 | 보통 |
| **StreamHandler** | **최고** | 좋음 | 보통 |
| **Active Logging** | **최고** | 매우 좋음 | 보통 |
| **Disabled Logging** | 좋음 | **최고** | 나쁨 |
| **전반적** | **최고** | 매우 좋음 | 보통 |

**LogXide delivers exceptional performance where it matters most: when your application is actually logging.**