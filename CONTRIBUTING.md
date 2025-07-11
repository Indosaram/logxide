# Contributing to LogXide

Thank you for your interest in contributing to LogXide! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Process](#contributing-process)
- [Code Style](#code-style)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)
- [Feature Requests](#feature-requests)

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/). Please read and follow it in all your interactions with the project.

## Getting Started

LogXide is a Rust-based Python extension that provides high-performance logging. To contribute effectively, you should have:

- Experience with Rust programming
- Familiarity with Python and its logging module
- Understanding of PyO3 for Python-Rust bindings
- Knowledge of async programming (Tokio)

## Development Setup

### Prerequisites

- Rust 1.70 or later
- Python 3.9 or later
- Git

### Setup Instructions

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/yourusername/logxide.git
   cd logxide
   ```

3. Set up a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. Install development dependencies:
   ```bash
   pip install maturin pytest pytest-cov pytest-xdist ruff mypy
   ```

5. Install pre-commit hooks:
   ```bash
   pip install pre-commit
   pre-commit install
   ```

6. Build and install in development mode:
   ```bash
   maturin develop
   ```

7. Run tests to verify setup:
   ```bash
   cargo test
   pytest tests/
   ```

## Contributing Process

1. **Create an Issue**: Before starting work, create an issue to discuss your proposed changes
2. **Fork & Branch**: Fork the repo and create a feature branch
3. **Develop**: Make your changes following our guidelines
4. **Test**: Ensure all tests pass and add new tests for your changes
5. **Document**: Update documentation as needed
6. **Submit**: Create a pull request with a clear description

## Code Style

### Rust Code

- Follow standard Rust formatting: `cargo fmt`
- Use Clippy for linting: `cargo clippy`
- Write comprehensive documentation comments (`///`)
- Follow Rust naming conventions
- Use `#[allow(dead_code)]` sparingly and only when necessary

### Python Code

- Follow PEP 8 style guidelines
- Use Ruff for formatting and linting: `ruff check .` and `ruff format`
- Type hints are required for all public functions
- Write docstrings for all public functions and classes

### Documentation

- Write clear, concise documentation
- Include examples in docstrings
- Update CHANGELOG.md for user-facing changes
- Keep README.md up to date

## Testing

### Running Tests

```bash
# Run all Rust tests
cargo test

# Run all Python tests
pytest tests/

# Run with coverage
pytest tests/ --cov=logxide --cov-report=html

# Run specific test categories
pytest tests/ -m unit           # Unit tests
pytest tests/ -m integration    # Integration tests
pytest tests/ -m threading      # Threading tests
pytest tests/ -m "not slow"     # Exclude slow tests
```

### Test Requirements

- All new features must have tests
- Maintain or improve code coverage
- Tests must pass on all supported Python versions
- Include both unit and integration tests where appropriate

### Test Categories

Use pytest markers to categorize tests:

- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.threading`: Threading/concurrency tests
- `@pytest.mark.slow`: Slow tests (performance, stress tests)
- `@pytest.mark.formatting`: Format string tests

## Submitting Changes

### Pull Request Process

1. **Update Documentation**: Ensure all documentation is updated
2. **Add Tests**: Include comprehensive tests for new functionality
3. **Update CHANGELOG**: Add entry to CHANGELOG.md
4. **Commit Messages**: Write clear, descriptive commit messages
5. **Pull Request**: Create a PR with detailed description

### Commit Message Format

```
type(scope): brief description

Detailed explanation of changes made, why they were made,
and any breaking changes or important notes.

Closes #issue_number
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(core): add support for custom log levels

Add ability to define custom log levels beyond the standard
DEBUG, INFO, WARNING, ERROR, CRITICAL levels.

Closes #123
```

### Pull Request Template

When creating a pull request, include:

- **Description**: Clear description of changes
- **Motivation**: Why this change is needed
- **Testing**: How the changes were tested
- **Breaking Changes**: Any breaking changes
- **Related Issues**: Reference related issues

## Reporting Issues

### Bug Reports

When reporting bugs, include:

- **Environment**: Python version, Rust version, OS
- **Steps to Reproduce**: Minimal code example
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Error Messages**: Full error output
- **Additional Context**: Any other relevant information

### Performance Issues

For performance-related issues:

- **Benchmark**: Include benchmark code
- **Comparison**: Compare with Python's logging module
- **Profiling**: Include profiling data if available
- **Environment**: Hardware specifications

## Feature Requests

When requesting features:

- **Use Case**: Describe the specific use case
- **Alternatives**: What alternatives have you considered
- **Implementation**: Any thoughts on implementation
- **Breaking Changes**: Whether this would break existing code

## Development Guidelines

### Architecture

LogXide uses a layered architecture:

1. **Rust Core** (`src/`): Core logging implementation
2. **Python Bindings** (`src/lib.rs`): PyO3 bindings
3. **Python Interface** (`logxide/__init__.py`): Python compatibility layer

### Key Components

- **Core Types** (`src/core.rs`): LogRecord, Logger, LoggerManager
- **Handlers** (`src/handler.rs`): Output destinations
- **Formatters** (`src/formatter.rs`): Message formatting
- **Filters** (`src/filter.rs`): Record filtering

### Adding New Features

1. **Design**: Create an issue to discuss the design
2. **Core Implementation**: Implement in Rust if needed
3. **Python Bindings**: Add PyO3 bindings if needed
4. **Python Interface**: Update Python compatibility layer
5. **Tests**: Add comprehensive tests
6. **Documentation**: Update docs and examples

### Performance Considerations

- **Async by Default**: Use async patterns where possible
- **Minimize Allocations**: Avoid unnecessary memory allocations
- **Efficient String Handling**: Use efficient string operations
- **Benchmark New Features**: Measure performance impact

## Code Review Process

### Review Criteria

- **Correctness**: Does the code work as intended?
- **Performance**: Are there performance implications?
- **Style**: Does it follow our style guidelines?
- **Tests**: Are there adequate tests?
- **Documentation**: Is it properly documented?
- **Compatibility**: Does it maintain Python logging compatibility?

### Review Process

1. **Automated Checks**: CI must pass
2. **Maintainer Review**: At least one maintainer must approve
3. **Testing**: Reviewer should test the changes
4. **Merge**: Squash and merge when approved

## Release Process

### Version Numbering

LogXide follows [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

### Release Steps

1. Update version in `pyproject.toml` and `logxide/__init__.py`
2. Update CHANGELOG.md
3. Create release tag: `git tag v1.0.0`
4. Push tag: `git push origin v1.0.0`
5. GitHub Actions will automatically publish to PyPI

## Getting Help

- **Documentation**: Check the README and docs
- **Issues**: Search existing issues
- **Discussions**: Use GitHub Discussions for questions
- **Email**: Contact maintainers at logxide@example.com

## Recognition

Contributors are recognized in:

- **CHANGELOG.md**: Major contributions
- **README.md**: Regular contributors
- **GitHub**: Contributor statistics

Thank you for contributing to LogXide! Your contributions help make Python logging faster and better for everyone.
