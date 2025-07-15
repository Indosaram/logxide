#!/bin/bash

# Docker runner script for logxide project
# This script provides convenient commands for Docker operations

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  dev        - Start development container with interactive shell"
    echo "  test       - Run all tests (Rust and Python)"
    echo "  test-rust  - Run only Rust tests"
    echo "  test-python - Run only Python tests"
    echo "  lint       - Run linting and formatting checks"
    echo "  build      - Build the package wheel"
    echo "  benchmark  - Run performance benchmarks"
    echo "  clean      - Clean up Docker images and volumes"
    echo "  shell      - Open shell in running dev container"
    echo "  logs       - Show logs from containers"
    echo "  help       - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 dev                    # Start development environment"
    echo "  $0 test                   # Run all tests"
    echo "  $0 build                  # Build package"
    echo "  $0 clean                  # Clean up Docker resources"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Function to build images if they don't exist
ensure_images() {
    print_info "Ensuring Docker images are built..."
    docker compose build --quiet
}

# Main command handling
case "$1" in
    "dev")
        check_docker
        print_info "Starting development container..."
        docker compose up --build -d dev
        docker compose exec dev bash
        ;;

    "test")
        check_docker
        print_info "Running all tests..."
        docker compose run --rm -T test
        if [ $? -eq 0 ]; then
            print_success "All tests passed!"
        else
            print_error "Some tests failed!"
            exit 1
        fi
        ;;

    "test-rust")
        check_docker
        print_info "Running Rust tests..."
        docker compose run --rm -T dev bash -c "cargo test --release"
        ;;

    "test-python")
        check_docker
        print_info "Running Python tests..."
        docker compose run --rm -T dev bash -c ".venv/bin/pytest -v --cov=logxide --cov-report=term-missing"
        ;;

    "lint")
        check_docker
        print_info "Running linting and formatting checks..."
        docker compose run --rm -T dev bash -c "
            echo 'Running ruff check...' &&
            .venv/bin/ruff check . &&
            echo 'Running ruff format check...' &&
            .venv/bin/ruff format --check . &&
            echo 'Running clippy...' &&
            cargo clippy --all-targets --all-features -- -D warnings
        "
        ;;

    "build")
        check_docker
        print_info "Building package..."
        docker compose run --rm -T build
        print_success "Package built successfully! Check ./dist/ directory."
        ;;

    "benchmark")
        check_docker
        print_info "Running benchmarks..."
        docker compose run --rm -T benchmark
        ;;

    "clean")
        print_info "Cleaning up Docker resources..."
        docker compose down -v
        docker system prune -f
        print_success "Cleanup completed!"
        ;;

    "shell")
        check_docker
        print_info "Opening shell in development container..."
        if docker compose ps dev | grep -q "Up"; then
            docker compose exec dev bash
        else
            print_warning "Development container not running. Starting it first..."
            docker compose up -d dev
            docker compose exec dev bash
        fi
        ;;

    "logs")
        check_docker
        docker compose logs -f
        ;;

    "help"|"--help"|"-h")
        show_usage
        ;;

    "")
        print_error "No command provided."
        show_usage
        exit 1
        ;;

    *)
        print_error "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac
