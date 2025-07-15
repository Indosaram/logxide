# Multi-stage Dockerfile for logxide: Rust-Python hybrid project
FROM rust:latest as rust-base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libssl-dev \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Install Rust components including clippy
RUN rustup component add clippy rustfmt

# Set working directory
WORKDIR /app

# Copy Rust configuration files
COPY Cargo.toml Cargo.lock ./
COPY clippy.toml ./

# Copy Python configuration files
COPY pyproject.toml pyrightconfig.json ./

# Copy source code
COPY src/ ./src/
COPY logxide/ ./logxide/

# Copy additional project files
COPY README.md LICENSE MANIFEST.in ./

# Check that Rust code compiles
RUN cargo check

# Install Python packages system-wide for testing
RUN pip3 install --break-system-packages maturin pytest pytest-cov ruff

# Create virtual environment for maturin development
RUN python3 -m venv .venv && \
    .venv/bin/pip install --upgrade pip && \
    .venv/bin/pip install maturin

# Build the package
RUN .venv/bin/maturin develop --release

# Copy remaining files
COPY tests/ ./tests/
COPY examples/ ./examples/
COPY benchmark/ ./benchmark/

# Development stage for testing
FROM rust-base as dev

# Install additional development tools
RUN apt-get update && apt-get install -y \
    valgrind \
    strace \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for development
ENV PYTHONPATH=/app
ENV RUST_LOG=debug
ENV RUST_BACKTRACE=1

# Default command for development
CMD ["bash"]

# Test stage
FROM dev as test

# Run Rust tests
RUN cargo test --release

# Run Python tests
RUN python3 -m pytest -v --cov=logxide --cov-report=term-missing

# Lint and format checks
RUN python3 -m ruff check .
RUN python3 -m ruff format --check .

# Type checking (skipped due to dependency issues)
# RUN .venv/bin/pyright

# Build stage for production package
FROM rust-base as build

# Build wheel
RUN .venv/bin/maturin build --release --out dist/

# Production stage
FROM python:3.11-slim as production

# Install system dependencies needed at runtime
RUN apt-get update && apt-get install -y \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Copy built wheel from build stage
COPY --from=build /app/dist/ /wheels/

# Install the package
RUN pip install /wheels/*.whl

# Set up non-root user
RUN useradd -m -u 1000 logxide
USER logxide

# Set working directory
WORKDIR /home/logxide

# Default command
CMD ["python", "-c", "import logxide; print(f'logxide version: {logxide.__version__}')"]
