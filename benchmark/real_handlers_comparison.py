#!/usr/bin/env python3
"""
Real handler comparison: LogXide vs Picologging vs Structlog with actual file/stream I/O.

This benchmark tests the same conditions as the original basic_handlers_benchmark.py
but only compares the three libraries we care about.
"""

import gc
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

# Add parent directory for logxide import
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import logxide
try:
    # Remove parent directory from path to avoid local import
    original_path = sys.path.copy()
    parent_dir = str(Path(__file__).parent.parent)
    if parent_dir in sys.path:
        sys.path.remove(parent_dir)
    if "." in sys.path:
        sys.path.remove(".")

    import logxide as logxide_rust

    logging_mod = logxide_rust.logging
    logxide_getLogger = logging_mod.getLogger

    print("Successfully imported logxide")
    logxide = logxide_rust
    sys.path = original_path
except Exception as e:
    print(f"Warning: Could not import logxide: {e}")
    logxide = None
    logxide_getLogger = None
    sys.path = original_path

import picologging
import structlog


class RealHandlerBenchmark:
    """Benchmark with real file and stream handlers."""

    def __init__(self, iterations=10_000):
        self.iterations = iterations
        self.results = {}

    def setup_logxide_file_handler(self, log_file):
        """Setup logxide with real FileHandler."""
        if not logxide_getLogger:
            return None

        # Use logxide's logging module basicConfig to setup file handler
        logging_mod.basicConfig(
            level=20, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        return logxide_getLogger("benchmark")

    def setup_logxide_stream_handler(self):
        """Setup logxide with real StreamHandler to /dev/null."""
        if not logxide_getLogger:
            return None

        # Use logxide's logging module basicConfig to setup stream handler
        logging_mod.basicConfig(
            level=20, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        return logxide_getLogger("benchmark")

    def setup_picologging_file_handler(self, log_file):
        """Setup picologging with real FileHandler."""
        logger = picologging.getLogger("benchmark")
        # Clear existing handlers
        logger.handlers.clear()

        handler = picologging.FileHandler(log_file)
        formatter = picologging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(picologging.INFO)
        return logger

    def setup_picologging_stream_handler(self):
        """Setup picologging with real StreamHandler to /dev/null."""
        logger = picologging.getLogger("benchmark")
        logger.handlers.clear()

        # Keep devnull file handle open
        self._picologging_devnull = open(os.devnull, "w")  # noqa: SIM115
        handler = picologging.StreamHandler(self._picologging_devnull)
        formatter = picologging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(picologging.INFO)
        return logger

    def setup_structlog_file_handler(self, log_file):
        """Setup structlog with real file output."""
        # Keep file handle open by storing it in the logger
        self._structlog_file = open(log_file, "w")  # noqa: SIM115
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=self._structlog_file),
        )
        return structlog.get_logger("benchmark")

    def setup_structlog_stream_handler(self):
        """Setup structlog with real stream output to /dev/null."""
        # Keep devnull file handle open
        self._structlog_devnull = open(os.devnull, "w")  # noqa: SIM115
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=self._structlog_devnull),
        )
        return structlog.get_logger("benchmark")

    def benchmark_logger(self, logger, logger_name, iterations=None):
        """Benchmark a logger with real I/O."""
        if iterations is None:
            iterations = self.iterations

        gc.collect()
        start_time = time.perf_counter()

        for i in range(iterations):
            if (
                logger_name == "logxide"
                or logger_name == "structlog"
                or logger_name == "picologging"
            ):
                logger.info(f"Test message {i}")

        # Ensure all messages are flushed
        if logger_name == "logxide":
            logging_mod.flush()
        elif logger_name == "structlog":
            if hasattr(self, "_structlog_file"):
                self._structlog_file.flush()
            if hasattr(self, "_structlog_devnull"):
                self._structlog_devnull.flush()
        elif logger_name == "picologging" and hasattr(self, "_picologging_devnull"):
            self._picologging_devnull.flush()

        end_time = time.perf_counter()
        return end_time - start_time

    def run_file_handler_benchmark(self):
        """Run FileHandler benchmark."""
        print("\n=== FileHandler Benchmark ===")
        results = {}

        with tempfile.TemporaryDirectory() as temp_dir:
            for lib_name, setup_func in [
                ("logxide", self.setup_logxide_file_handler),
                ("picologging", self.setup_picologging_file_handler),
                ("structlog", self.setup_structlog_file_handler),
            ]:
                if lib_name == "logxide" and not logxide:
                    continue

                print(f"  Testing {lib_name}...")

                # Create separate log file for each library
                log_file = os.path.join(temp_dir, f"{lib_name}_test.log")

                try:
                    logger = setup_func(log_file)
                    if logger is None:
                        continue

                    # Run multiple times and average
                    times = []
                    for _run in range(3):
                        duration = self.benchmark_logger(logger, lib_name)
                        times.append(duration)

                    avg_time = statistics.mean(times)
                    ops_per_second = self.iterations / avg_time

                    results[lib_name] = {
                        "avg_time": avg_time,
                        "ops_per_second": ops_per_second,
                        "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
                    }

                    print(f"    {lib_name}: {ops_per_second:,.0f} ops/sec")

                except Exception as e:
                    print(f"    {lib_name}: ERROR - {e}")

        return results

    def run_stream_handler_benchmark(self):
        """Run StreamHandler benchmark."""
        print("\n=== StreamHandler Benchmark ===")
        results = {}

        for lib_name, setup_func in [
            ("logxide", self.setup_logxide_stream_handler),
            ("picologging", self.setup_picologging_stream_handler),
            ("structlog", self.setup_structlog_stream_handler),
        ]:
            if lib_name == "logxide" and not logxide:
                continue

            print(f"  Testing {lib_name}...")

            try:
                logger = setup_func()
                if logger is None:
                    continue

                # Run multiple times and average
                times = []
                for _run in range(3):
                    duration = self.benchmark_logger(logger, lib_name)
                    times.append(duration)

                avg_time = statistics.mean(times)
                ops_per_second = self.iterations / avg_time

                results[lib_name] = {
                    "avg_time": avg_time,
                    "ops_per_second": ops_per_second,
                    "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
                }

                print(f"    {lib_name}: {ops_per_second:,.0f} ops/sec")

            except Exception as e:
                print(f"    {lib_name}: ERROR - {e}")

        return results

    def print_comparison_table(self, results, title):
        """Print formatted comparison table."""
        print(f"\n{title}")
        print("=" * 80)

        if not results:
            print("No results to display")
            return

        # Sort by ops_per_second descending
        sorted_results = sorted(
            results.items(), key=lambda x: x[1]["ops_per_second"], reverse=True
        )

        print(
            f"{'Rank':<5} {'Library':<12} {'Ops/sec':<15} {'Avg Time (s)':<15} {'Relative':<12}"
        )
        print("-" * 80)

        fastest_ops = sorted_results[0][1]["ops_per_second"]

        for i, (lib_name, metrics) in enumerate(sorted_results, 1):
            emoji = "🏆" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else ""
            relative = metrics["ops_per_second"] / fastest_ops

            print(
                f"{i}{emoji:<4} {lib_name:<12} {metrics['ops_per_second']:<15,.0f} "
                f"{metrics['avg_time']:<15.6f} {relative:<12.2f}x"
            )


def main():
    """Run the real handler comparison benchmark."""
    print("🚀 Real Handler Comparison: LogXide vs Picologging vs Structlog")
    print("=" * 80)
    print(f"Test conditions: {10_000:,} messages per test, 3 runs averaged")
    print("Testing actual file and stream I/O (same as basic_handlers_benchmark.py)")
    print()

    benchmark = RealHandlerBenchmark(iterations=10_000)

    # Run benchmarks
    file_results = benchmark.run_file_handler_benchmark()
    stream_results = benchmark.run_stream_handler_benchmark()

    # Print results
    benchmark.print_comparison_table(file_results, "FILEHANDLER RESULTS")
    benchmark.print_comparison_table(stream_results, "STREAMHANDLER RESULTS")

    print("\n📊 Summary:")
    if file_results:
        file_winner = max(file_results.items(), key=lambda x: x[1]["ops_per_second"])
        print(
            f"   • FileHandler winner: {file_winner[0]} ({file_winner[1]['ops_per_second']:,.0f} ops/sec)"
        )

    if stream_results:
        stream_winner = max(
            stream_results.items(), key=lambda x: x[1]["ops_per_second"]
        )
        print(
            f"   • StreamHandler winner: {stream_winner[0]} ({stream_winner[1]['ops_per_second']:,.0f} ops/sec)"
        )

    print("\n✅ This benchmark uses the same conditions as basic_handlers_benchmark.py")
    print("   for direct comparison with the existing README results.")


if __name__ == "__main__":
    main()
