#!/usr/bin/env python3
"""Comprehensive benchmark comparing logxide, structlog, and picologging."""

import gc
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

# Try to import logxide
try:
    # Remove parent directory from path to avoid local import
    original_path = sys.path.copy()
    parent_dir = str(Path(__file__).parent.parent)
    if parent_dir in sys.path:
        sys.path.remove(parent_dir)
    if "." in sys.path:
        sys.path.remove(".")

    # Import from installed package
    import logxide as logxide_rust

    # Get the logging module from the Rust extension
    logging_mod = logxide_rust.logging
    logxide_getLogger = logging_mod.getLogger

    # Import log levels
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

    print("Successfully imported logxide")
    logxide = logxide_rust

    # Restore path
    sys.path = original_path
except Exception as e:
    print(f"Warning: Could not import logxide: {e}")
    logxide = None
    logxide_getLogger = None
    DEBUG = INFO = WARNING = ERROR = CRITICAL = None
    sys.path = original_path

import picologging
import structlog


class LoggerBenchmark:
    """Benchmark different logging libraries."""

    def __init__(self, iterations=100_000):
        self.iterations = iterations
        self.results = {}

    def setup_logxide(self):
        """Setup logxide logger."""
        if logxide_getLogger:
            logger = logxide_getLogger("benchmark")
            logger.setLevel(INFO)  # Use setLevel like standard logging
            return logger
        return None

    def setup_structlog(self):
        """Setup structlog logger."""
        import io

        # Create a dummy file object that discards output
        null_file = io.StringIO()
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=null_file),
        )
        return structlog.get_logger("benchmark")

    def setup_picologging(self):
        """Setup picologging logger."""
        import io

        logger = picologging.getLogger("benchmark")
        # Create a handler that writes to nowhere
        handler = picologging.StreamHandler(io.StringIO())
        formatter = picologging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(picologging.INFO)
        return logger

    def benchmark_simple_logging(self, logger, logger_name):
        """Benchmark simple string logging."""
        gc.collect()
        start_time = time.perf_counter()

        for _i in range(self.iterations):
            if (
                logger_name == "logxide"
                or logger_name == "structlog"
                or logger_name == "picologging"
            ):
                logger.info("Simple log message")

        end_time = time.perf_counter()
        return end_time - start_time

    def benchmark_structured_logging(self, logger, logger_name):
        """Benchmark structured logging with context."""
        gc.collect()
        start_time = time.perf_counter()

        for i in range(self.iterations):
            if logger_name == "logxide" or logger_name == "structlog":
                logger.info("User action", user_id=i, action="login", status="success")
            elif logger_name == "picologging":
                # Picologging doesn't support structured logging natively
                logger.info(
                    f"User action - user_id: {i}, action: login, status: success"
                )

        end_time = time.perf_counter()
        return end_time - start_time

    def benchmark_error_logging(self, logger, logger_name):
        """Benchmark error logging with exception."""
        gc.collect()
        exception = ValueError("Test exception")
        start_time = time.perf_counter()

        for i in range(self.iterations):
            if logger_name == "logxide" or logger_name == "structlog":
                logger.error("Error occurred", error=str(exception), count=i)
            elif logger_name == "picologging":
                logger.error(f"Error occurred - error: {exception}, count: {i}")

        end_time = time.perf_counter()
        return end_time - start_time

    def benchmark_disabled_logging(self, logger, logger_name):
        """Benchmark performance when logging level is disabled."""
        gc.collect()

        # Set to ERROR level so DEBUG messages are disabled
        if logger_name == "logxide" and logger:
            logger.setLevel(ERROR)  # Use setLevel like standard logging
        elif logger_name == "picologging":
            logger.setLevel(picologging.ERROR)
        # Note: structlog doesn't have traditional log levels

        start_time = time.perf_counter()

        for i in range(self.iterations):
            if logger_name == "logxide":
                logger.debug("Debug message that should not be processed", data=i)
            elif logger_name == "structlog":
                # Structlog will still process this
                logger.debug("Debug message that should not be processed", data=i)
            elif logger_name == "picologging":
                logger.debug("Debug message that should not be processed %d", i)

        end_time = time.perf_counter()
        return end_time - start_time

    def run_benchmarks(self):
        """Run all benchmarks for all loggers."""
        loggers = {}

        # Only include logxide if it was imported successfully
        logxide_logger = self.setup_logxide()
        if logxide_logger:
            loggers["logxide"] = logxide_logger

        loggers["structlog"] = self.setup_structlog()
        loggers["picologging"] = self.setup_picologging()

        benchmarks = [
            ("simple_logging", self.benchmark_simple_logging),
            ("structured_logging", self.benchmark_structured_logging),
            ("error_logging", self.benchmark_error_logging),
            ("disabled_logging", self.benchmark_disabled_logging),
        ]

        for benchmark_name, benchmark_func in benchmarks:
            print(f"\nRunning {benchmark_name} benchmark...")
            self.results[benchmark_name] = {}

            for logger_name, logger in loggers.items():
                print(f"  Testing {logger_name}...")

                # Run multiple times and take the average
                times = []
                for _ in range(5):
                    duration = benchmark_func(logger, logger_name)
                    times.append(duration)

                avg_time = statistics.mean(times)
                std_dev = statistics.stdev(times) if len(times) > 1 else 0

                self.results[benchmark_name][logger_name] = {
                    "avg_time": avg_time,
                    "std_dev": std_dev,
                    "min_time": min(times),
                    "max_time": max(times),
                    "ops_per_second": self.iterations / avg_time,
                }

    def print_results(self):
        """Print benchmark results in a formatted table."""
        print("\n" + "=" * 80)
        print(f"BENCHMARK RESULTS ({self.iterations:,} iterations)")
        print("=" * 80)

        for benchmark_name, results in self.results.items():
            print(f"\n{benchmark_name.upper().replace('_', ' ')}:")
            print("-" * 80)
            print(
                f"{'Logger':<15} {'Avg Time (s)':<15} {'Ops/sec':<15} {'Std Dev':<15} {'Min (s)':<15} {'Max (s)':<15}"
            )
            print("-" * 80)

            # Sort by average time (fastest first)
            sorted_results = sorted(results.items(), key=lambda x: x[1]["avg_time"])

            for logger_name, metrics in sorted_results:
                print(
                    f"{logger_name:<15} "
                    f"{metrics['avg_time']:<15.6f} "
                    f"{metrics['ops_per_second']:<15,.0f} "
                    f"{metrics['std_dev']:<15.6f} "
                    f"{metrics['min_time']:<15.6f} "
                    f"{metrics['max_time']:<15.6f}"
                )

            # Show relative performance
            if sorted_results:
                fastest_time = sorted_results[0][1]["avg_time"]
                print("\nRelative Performance:")
                for logger_name, metrics in sorted_results:
                    ratio = metrics["avg_time"] / fastest_time
                    print(
                        f"  {logger_name}: {ratio:.2f}x slower"
                        if ratio > 1.01
                        else f"  {logger_name}: fastest"
                    )

    def save_results(self):
        """Save results to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"logger_comparison_{timestamp}.json"

        output = {
            "timestamp": timestamp,
            "iterations": self.iterations,
            "results": self.results,
        }

        with open(filename, "w") as f:
            json.dump(output, f, indent=2)

        print(f"\nResults saved to {filename}")


def main():
    """Run the benchmark comparison."""
    print("Starting comprehensive logger benchmark...")
    print("Comparing: logxide, structlog, and picologging")

    benchmark = LoggerBenchmark(iterations=100_000)
    benchmark.run_benchmarks()
    benchmark.print_results()
    benchmark.save_results()


if __name__ == "__main__":
    main()
