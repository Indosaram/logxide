# LogXide Examples

This directory contains examples demonstrating various features of logxide.

## Basic Examples

### 1. Basic Usage (`basic_usage.py`)
- Simple logging setup
- Basic logging methods (info, debug, warning, error, critical)
- Logger hierarchy

### 2. Drop-in Replacement (`drop_in_replacement.py`)
- How to use `logxide.install()`
- Replacing Python's standard logging module
- Third-party library compatibility

## Format Examples

### 3. Format Styles (`format_*.py`)
- Different formatting options
- Custom date formats
- Thread information in logs
- JSON logging format

## Advanced Examples

### 4. Third-Party Integration (`third_party_integration.py`)
- Real HTTP requests with urllib3/requests
- SQLAlchemy database logging
- Multiple library integration

### 5. Performance Demo (`performance_demo.py`)
- High-throughput logging
- Multi-threaded scenarios
- Async logging benefits

## Quick Start

For a quick introduction, start with:

```bash
python examples/basic_usage.py
python examples/drop_in_replacement.py
```

For advanced features:

```bash
python examples/third_party_integration.py
python examples/format_detailed.py
```
