# LogXide Scripts

This directory contains utility scripts for LogXide development and publication.

## Scripts Overview

### `publish.py`
Publication script for releasing LogXide to PyPI.

**Usage:**
```bash
# Publish to Test PyPI (recommended first)
python scripts/publish.py --test

# Publish to PyPI
python scripts/publish.py

# Publish with git tag creation
python scripts/publish.py --tag

# Skip tests (not recommended)
python scripts/publish.py --skip-tests

# Skip pre-publication checks
python scripts/publish.py --skip-checks
```

**Features:**
- Version consistency checking
- Git status verification
- Automated testing
- Package building and validation
- Upload to Test PyPI or PyPI
- Git tag creation

### `verify_package.py`
Package verification script to test LogXide functionality after installation.

**Usage:**
```bash
# Install LogXide first
pip install logxide

# Then verify
python scripts/verify_package.py
```

**Tests:**
- Basic import functionality
- Logging module functionality
- Drop-in replacement capability
- Performance benchmarking
- Thread safety
- Formatting capabilities

## Publication Workflow

### 1. Pre-publication Checklist

Before publishing, ensure:

- [ ] All tests pass: `pytest tests/`
- [ ] Rust tests pass: `cargo test`
- [ ] Version numbers are consistent
- [ ] CHANGELOG.md is updated
- [ ] Documentation is up to date
- [ ] Git working directory is clean

### 2. Test Publication

Always test on Test PyPI first:

```bash
# Publish to Test PyPI
python scripts/publish.py --test

# Install from Test PyPI
pip install --index-url https://test.pypi.org/simple/ logxide

# Verify installation
python scripts/verify_package.py
```

### 3. Production Publication

If Test PyPI works correctly:

```bash
# Publish to PyPI
python scripts/publish.py --tag

# Verify installation
pip install logxide
python scripts/verify_package.py
```

## Manual Publication Steps

If you prefer manual control:

### 1. Build Package
```bash
# Clean previous builds
rm -rf target/wheels/ dist/

# Build wheels
maturin build --release

# Build source distribution
maturin sdist
```

### 2. Check Package
```bash
# Install twine
pip install twine

# Check package
twine check target/wheels/*
```

### 3. Upload to Test PyPI
```bash
# Configure Test PyPI (first time only)
cat > ~/.pypirc << EOF
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-...  # Your PyPI token

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-...  # Your Test PyPI token
EOF

# Upload to Test PyPI
twine upload --repository testpypi target/wheels/*
```

### 4. Upload to PyPI
```bash
# Upload to PyPI
twine upload target/wheels/*
```

### 5. Create Git Tag
```bash
# Create and push tag
git tag v0.1.0
git push origin v0.1.0
```

## CI/CD Integration

The GitHub Actions workflows in `.github/workflows/` handle automated publication:

- **`ci.yml`**: Continuous integration testing
- **`publish.yml`**: Automated PyPI publication on tag push

To trigger automated publication:
```bash
git tag v0.1.0
git push origin v0.1.0
```

## Configuration

### PyPI Token Setup

1. Create PyPI account at https://pypi.org/
2. Generate API token in account settings
3. Add token to GitHub Secrets as `PYPI_TOKEN`
4. For Test PyPI, add token as `TEST_PYPI_TOKEN`

### Local Configuration

For local publishing, create `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-your-token-here

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-your-test-token-here
```

## Troubleshooting

### Common Issues

1. **Version Mismatch Error**
   - Ensure version in `pyproject.toml` matches `logxide/__init__.py`
   - Update both files to the same version

2. **Upload Already Exists**
   - PyPI doesn't allow overwriting existing versions
   - Increment version number and try again

3. **Package Validation Failed**
   - Check `twine check` output
   - Ensure all required files are included
   - Verify package metadata

4. **Import Errors After Installation**
   - Check that the package was built correctly
   - Verify Python version compatibility
   - Check for missing dependencies

### Debug Commands

```bash
# Check package contents
python -c "import logxide; print(logxide.__file__)"

# Check version
python -c "import logxide; print(logxide.__version__)"

# List package files
pip show -f logxide

# Check package metadata
pip show logxide
```

## Testing Locally

Before publishing, test locally:

```bash
# Build and install in development mode
maturin develop

# Run tests
pytest tests/

# Run verification
python scripts/verify_package.py
```

## Security Notes

- Never commit API tokens to version control
- Use environment variables for sensitive data
- Keep PyPI tokens secure and rotate regularly
- Use Test PyPI for testing to avoid polluting PyPI

## Support

If you encounter issues with publication:

1. Check the GitHub Actions logs
2. Review the script output
3. Verify your PyPI credentials
4. Check the LogXide documentation
5. Open an issue on GitHub

---

For more information, see the main project README and CONTRIBUTING.md files.
