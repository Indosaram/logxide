#!/bin/bash

# Clippy check script for CI
# This script ensures consistent clippy behavior across different environments

set -e

echo "Running clippy check for logxide..."

# Print environment info for debugging
echo "Rust version: $(rustc --version)"
echo "Clippy version: $(cargo clippy --version)"
echo "Target: $(rustc -vV | grep host | cut -d' ' -f2)"

# Clean any previous build artifacts to ensure clean state
echo "Cleaning previous build artifacts..."
cargo clean

# Run clippy with explicit configuration
echo "Running clippy with strict warnings..."
cargo clippy --all-targets --all-features -- \
    -D warnings \
    -A clippy::too_many_arguments \
    -A clippy::module_name_repetitions \
    -A clippy::redundant_closure \
    -A clippy::missing_const_for_thread_local \
    -A clippy::while_let_loop \
    -A clippy::useless_conversion \
    -A clippy::redundant_field_names \
    -A clippy::missing_errors_doc \
    -A clippy::missing_panics_doc \
    -A clippy::must_use_candidate \
    -A deprecated

echo "Clippy check completed successfully!"
