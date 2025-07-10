# Development Guide

This document outlines the development setup and tools for the logxide project.

## Pre-commit Setup

This project uses pre-commit hooks to maintain code quality and consistency.

### Installation

```bash
# Install pre-commit
uv pip install pre-commit

# Install the git hooks
pre-commit install
```

### Tools Configured

1. **Python (Ruff)**:
   - **ruff-format**: Automatic code formatting (replaces Black)
   - **ruff**: Linting and import sorting (replaces flake8, isort, pyupgrade)

2. **Rust**:
   - **cargo fmt**: Code formatting
   - **cargo clippy**: Linting with warnings as errors

3. **General**:
   - Trailing whitespace removal
   - End-of-file fixing
   - YAML and TOML validation
   - Large file checking
   - Merge conflict detection

### Running Hooks

```bash
# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run ruff --all-files
pre-commit run cargo-clippy --all-files

# Run on staged files only (automatic on commit)
pre-commit run
```

### Configuration Files

- `.pre-commit-config.yaml`: Pre-commit hook configuration
- `pyproject.toml`: All Python tool configurations (ruff, pytest, coverage, pyright)
- No additional Rust config needed (uses defaults)

All Python project settings are centralized in `pyproject.toml` following modern Python packaging standards.

### Development Workflow

1. Make your changes
2. Stage files with `git add`
3. Commit (pre-commit hooks run automatically)
4. If hooks fail, fix issues and retry commit

The hooks are configured to be strict to maintain high code quality standards across the mixed Python/Rust codebase.

## IDE Integration

### VS Code

Install these extensions for optimal development experience:

- **Python**: Python language support
- **rust-analyzer**: Rust language support
- **Ruff**: Python linting/formatting
- **Even Better TOML**: TOML file support

### Configuration

All Python tools are configured in `pyproject.toml` following PEP 518 standards:

**Ruff** (replaces multiple tools):
- Black (formatting)
- isort (import sorting)
- flake8 (linting)
- pyupgrade (syntax upgrades)

**Pytest** (testing):
- Test discovery and execution settings
- Coverage reporting configuration
- Custom markers for test organization

**Coverage** (code coverage):
- Source and omit patterns
- Report exclusion rules

**Pyright** (type checking):
- Virtual environment configuration

This single-file approach simplifies project maintenance and follows modern Python packaging best practices.
