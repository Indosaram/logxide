#!/usr/bin/env python3
"""
Publication script for LogXide

This script helps with the publication process to PyPI.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def run_command(cmd, check=True):
    """Run a command and return the result."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result


def check_version_consistency():
    """Check that versions are consistent across files."""
    print("Checking version consistency...")

    # Read version from pyproject.toml
    with open("pyproject.toml") as f:
        content = f.read()
        pyproject_match = re.search(r'version = "([^"]+)"', content)
        if not pyproject_match:
            print("Error: Could not find version in pyproject.toml")
            sys.exit(1)
        pyproject_version = pyproject_match.group(1)

    # Read version from __init__.py
    with open("logxide/__init__.py") as f:
        content = f.read()
        init_match = re.search(r'__version__ = "([^"]+)"', content)
        if not init_match:
            print("Error: Could not find __version__ in logxide/__init__.py")
            sys.exit(1)
        init_version = init_match.group(1)

    # Check consistency
    if pyproject_version != init_version:
        print("Error: Version mismatch!")
        print(f"  pyproject.toml: {pyproject_version}")
        print(f"  __init__.py: {init_version}")
        sys.exit(1)

    print(f"✓ Version consistency check passed: {pyproject_version}")
    return pyproject_version


def check_git_status():
    """Check git status to ensure clean working directory."""
    print("Checking git status...")
    result = run_command("git status --porcelain", check=False)
    if result.stdout.strip():
        print("Warning: Working directory is not clean:")
        print(result.stdout)
        response = input("Continue anyway? (y/N): ")
        if response.lower() != "y":
            sys.exit(1)
    else:
        print("✓ Working directory is clean")


def run_tests():
    """Run the test suite."""
    print("Running tests...")

    # Run Rust tests
    run_command("cargo test")
    print("✓ Rust tests passed")

    # Build Python extension
    run_command("maturin develop")
    print("✓ Python extension built")

    # Run Python tests
    run_command("python -m pytest tests/ -v")
    print("✓ Python tests passed")


def build_package():
    """Build the package."""
    print("Building package...")

    # Clean previous builds
    run_command("rm -rf target/wheels/", check=False)
    run_command("rm -rf dist/", check=False)

    # Build wheels
    run_command("maturin build --release")
    print("✓ Package built")


def check_package():
    """Check the built package."""
    print("Checking package...")

    # Install twine if not available
    run_command("pip install twine", check=False)

    # Check package
    run_command("twine check target/wheels/*")
    print("✓ Package check passed")


def upload_to_test_pypi():
    """Upload to Test PyPI."""
    print("Uploading to Test PyPI...")

    # Upload to Test PyPI
    run_command("twine upload --repository testpypi target/wheels/*")
    print("✓ Uploaded to Test PyPI")


def upload_to_pypi():
    """Upload to PyPI."""
    print("Uploading to PyPI...")

    # Upload to PyPI
    run_command("twine upload target/wheels/*")
    print("✓ Uploaded to PyPI")


def create_git_tag(version):
    """Create a git tag for the version."""
    print(f"Creating git tag v{version}...")

    # Create tag
    run_command(f"git tag v{version}")

    # Push tag
    run_command(f"git push origin v{version}")
    print(f"✓ Created and pushed tag v{version}")


def main():
    parser = argparse.ArgumentParser(description="Publish LogXide to PyPI")
    parser.add_argument(
        "--test", action="store_true", help="Upload to Test PyPI instead of PyPI"
    )
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument(
        "--skip-checks", action="store_true", help="Skip pre-publication checks"
    )
    parser.add_argument(
        "--tag", action="store_true", help="Create git tag after successful upload"
    )

    args = parser.parse_args()

    # Change to project root
    os.chdir(Path(__file__).parent.parent)

    print("🚀 LogXide Publication Script")
    print("=" * 40)

    try:
        # Check version consistency
        version = check_version_consistency()

        if not args.skip_checks:
            # Check git status
            check_git_status()

        if not args.skip_tests:
            # Run tests
            run_tests()

        # Build package
        build_package()

        # Check package
        check_package()

        # Upload
        if args.test:
            upload_to_test_pypi()
            print(f"✅ Successfully uploaded LogXide v{version} to Test PyPI!")
            print(
                "Test installation: pip install "
                "--index-url https://test.pypi.org/simple/ logxide"
            )
        else:
            # Confirm before uploading to PyPI
            response = input(
                f"Ready to upload LogXide v{version} to PyPI. Continue? (y/N): "
            )
            if response.lower() != "y":
                print("❌ Upload cancelled")
                sys.exit(1)

            upload_to_pypi()
            print(f"✅ Successfully uploaded LogXide v{version} to PyPI!")
            print("Installation: pip install logxide")

            # Create git tag if requested
            if args.tag:
                create_git_tag(version)

    except KeyboardInterrupt:
        print("\n❌ Publication cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Publication failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
