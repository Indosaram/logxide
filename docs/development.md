# Development Guide

## Project Structure

```
logxide/
├── src/                    # Rust source code
│   ├── lib.rs             # Python bindings
│   ├── core.rs            # Core logging types
│   ├── handler.rs         # Log handlers
│   ├── formatter.rs       # Format processing
│   └── ...
├── logxide/               # Python package
│   └── __init__.py        # Python API
├── tests/                 # Test suite
│   ├── test_basic_logging.py
│   ├── test_integration.py
│   └── README.md
├── examples/              # Usage examples
├── benchmark/             # Performance benchmarks
└── docs/                  # Documentation
```

## Development Setup

### Prerequisites

- **Rust**: 1.70+ (install via [rustup](https://rustup.rs/))
- **Python**: 3.12+ 
- **maturin**: For building Python extensions

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/Indosaram/logxide
cd logxide

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install maturin pytest pytest-cov pytest-xdist
```

## Building

### Development Build

```bash
# Build and install in development mode
maturin develop

# Build with debug symbols
maturin develop --profile dev

# Build with optimizations
maturin develop --release
```

### Release Build

```bash
# Build wheel for distribution
maturin build --release

# Build for specific Python version
maturin build --release --interpreter python3.12
```

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=logxide --cov-report=term-missing

# Run specific test categories
pytest tests/ -m unit           # Unit tests only
pytest tests/ -m integration    # Integration tests only
pytest tests/ -m threading      # Threading tests only
pytest tests/ -m "not slow"     # Exclude slow tests

# Parallel execution for faster testing
pytest tests/ -n auto
```

### Test Categories

- **Unit Tests**: Basic functionality, API compatibility
- **Integration Tests**: Real-world scenarios, drop-in replacement testing
- **Threading Tests**: Multi-threaded logging, thread safety
- **Formatting Tests**: Format specifiers, padding, date formatting
- **Performance Tests**: High-throughput scenarios, stress testing

### Writing Tests

```python
import pytest
from logxide import logging

def test_basic_logging():
    """Test basic logging functionality."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("test")
    
    # Your test code here
    logger.info("Test message")
    
    # Ensure all messages are processed
    logging.flush()

@pytest.mark.threading
def test_thread_safety():
    """Test thread safety."""
    # Threading test code
    pass

@pytest.mark.slow
def test_performance():
    """Performance test - marked as slow."""
    # Performance test code
    pass
```

## Code Style and Linting

### Rust Code

```bash
# Format code
cargo fmt

# Run clippy lints
cargo clippy --all-targets --all-features -- -D warnings

# Run tests
cargo test
```

### Python Code

```bash
# Format with black
black tests/ examples/

# Sort imports
isort tests/ examples/

# Type checking with mypy
mypy tests/

# Lint with ruff
ruff check tests/ examples/
```

## Debugging

### Rust Debugging

```bash
# Build with debug symbols
maturin develop --profile dev

# Run with RUST_BACKTRACE for stack traces
RUST_BACKTRACE=1 python your_test.py

# Use logging for debugging
RUST_LOG=debug python your_test.py
```

### Python Debugging

```python
import logging
import logxide

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Use flush to ensure messages are processed
logxide.flush()
```

## Performance Profiling

### Benchmarking

```bash
# Run handler benchmarks
python benchmark/real_handlers_comparison.py

# Run memory benchmarks
python benchmark/compare_loggers.py

# Full library comparison
python benchmark/basic_handlers_benchmark.py
```

### Memory Profiling

```bash
# Install memory profiler
pip install memory-profiler

# Profile memory usage
python -m memory_profiler your_script.py
```

### CPU Profiling

```bash
# Install profiling tools
pip install py-spy

# Profile running application
py-spy record -o profile.svg -- python your_script.py
```

## Contributing

### Workflow

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Make** your changes
4. **Add** tests for new functionality
5. **Ensure** all tests pass: `pytest tests/`
6. **Format** code: `cargo fmt && black .`
7. **Commit** your changes (`git commit -m 'Add amazing feature'`)
8. **Push** to the branch (`git push origin feature/amazing-feature`)
9. **Open** a Pull Request

### Pull Request Guidelines

- **Clear description** of changes and motivation
- **Tests** for new functionality
- **Documentation** updates if needed
- **Backwards compatibility** unless breaking change is necessary
- **Performance impact** analysis for performance-critical changes

### Code Review Process

1. Automated checks must pass (CI/CD)
2. At least one maintainer review
3. Address review feedback
4. Maintainer approval and merge

## Release Process

### Version Management

LogXide uses semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes
- **MINOR**: New features, backwards compatible
- **PATCH**: Bug fixes, backwards compatible

### Creating a Release

```bash
# Update version in Cargo.toml and pyproject.toml
# Update CHANGELOG.md

# Build and test
maturin build --release
pytest tests/

# Create git tag
git tag v0.2.0
git push origin v0.2.0

# Publish to PyPI
maturin publish
```

## Documentation

### Building Documentation

```bash
# Install documentation dependencies
pip install mkdocs mkdocs-material

# Serve documentation locally
mkdocs serve

# Build documentation
mkdocs build
```

### Writing Documentation

- Use **clear, concise** language
- Include **code examples** for all features
- Add **cross-references** between related topics
- Update **API reference** for any API changes

## Troubleshooting

### Common Issues

#### Build Failures

```bash
# Clean build cache
cargo clean
maturin develop

# Update Rust toolchain
rustup update
```

#### Import Errors

```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall in development mode
maturin develop --force
```

#### Test Failures

```bash
# Run tests with verbose output
pytest tests/ -v

# Run specific failing test
pytest tests/test_specific.py::test_function -v
```

### Getting Help

- **GitHub Issues**: Report bugs and request features
- **Discussions**: Ask questions and share ideas
- **Documentation**: Check existing documentation first
- **Code Examples**: Look at examples/ directory

## Advanced Development

### Custom Handlers

```rust
// In src/handler.rs
use crate::core::LogRecord;
use async_trait::async_trait;

#[async_trait]
pub trait Handler: Send + Sync {
    async fn emit(&self, record: &LogRecord);
}

pub struct CustomHandler {
    // Your handler implementation
}

#[async_trait]
impl Handler for CustomHandler {
    async fn emit(&self, record: &LogRecord) {
        // Your custom logic here
    }
}
```

### Performance Optimization

- **Profile before optimizing**: Use benchmarks to identify bottlenecks
- **Measure impact**: Verify optimizations actually improve performance
- **Consider trade-offs**: Balance performance vs. complexity
- **Test thoroughly**: Ensure optimizations don't break functionality

### Adding New Features

1. **Design first**: Consider API design and backwards compatibility
2. **Implement**: Start with Rust core, then Python bindings
3. **Test extensively**: Unit tests, integration tests, performance tests
4. **Document**: Update documentation and examples
5. **Review**: Get feedback before finalizing