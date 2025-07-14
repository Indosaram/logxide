# Installation Guide

## From PyPI (Recommended)

Install LogXide from PyPI using pip:

```bash
pip install logxide
```

## Development Setup

For development or building from source:

### Prerequisites

1. Install `maturin` to build the Python package:

```bash
uv venv
source .venv/bin/activate
uv pip install maturin
```

### Building from Source

```bash
# Clone the repository
git clone https://github.com/Indosaram/logxide
cd logxide

# Install development dependencies
uv pip install maturin pytest pytest-cov

# Build in development mode
maturin develop

# Build release version
maturin build --release
```

### Running Tests

```bash
# Install test dependencies
uv pip install pytest pytest-cov pytest-xdist

# Run test suite
pytest tests/ -v

# Generate coverage report
pytest tests/ --cov=logxide --cov-report=html
```

## Compatibility

- **Python**: 3.12+ (3.13+ recommended)
- **Platforms**: macOS, Linux, Windows
- **API**: Full compatibility with Python's `logging` module
- **Dependencies**: None (Rust compiled into native extension)