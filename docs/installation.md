# Installation Guide

## From PyPI (Recommended)

=== "pip"

    ```bash
    # Basic installation
    pip install logxide

    # With Sentry integration
    pip install logxide[sentry]
    ```

=== "uv"

    ```bash
    # Basic installation
    uv add logxide

    # With Sentry integration
    uv add logxide[sentry]
    ```

## Development Setup

For development or building from source:

### Prerequisites

1. Install `maturin` to build the Python package:

=== "pip"

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install maturin
    ```

=== "uv"

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
```

=== "pip"

    ```bash
    # Install development dependencies
    pip install maturin pytest pytest-cov

    # Build in development mode
    maturin develop

    # Build release version
    maturin build --release
    ```

=== "uv"

    ```bash
    # Install development dependencies
    uv pip install maturin pytest pytest-cov

    # Build in development mode
    maturin develop

    # Build release version
    maturin build --release
    ```

### Running Tests

=== "pip"

    ```bash
    # Install test dependencies
    pip install pytest pytest-cov pytest-xdist

    # Run test suite
    pytest tests/ -v

    # Generate coverage report
    pytest tests/ --cov=logxide --cov-report=html
    ```

=== "uv"

    ```bash
    # Install test dependencies
    uv pip install pytest pytest-cov pytest-xdist

    # Run test suite
    pytest tests/ -v

    # Generate coverage report
    pytest tests/ --cov=logxide --cov-report=html
    ```

## Compatibility

- **Python**: 3.12+ (3.14 supported)
- **Platforms**: macOS, Linux, Windows
- **Dependencies**: None (Rust compiled into native extension)
