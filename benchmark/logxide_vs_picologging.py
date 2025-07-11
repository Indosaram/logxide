#!/usr/bin/env python3.12
"""
LogXide vs Picologging Head-to-Head Benchmark - Python 3.12

This benchmark focuses on beating Picologging performance with real-world handlers.
We test the exact same scenarios to ensure fair comparison.

Handlers tested:
1. FileHandler - Direct file writing
2. StreamHandler - Console output (to /dev/null)
3. RotatingFileHandler - Log rotation
4. Multiple handlers - Production setup
5. JSON formatting - Structured logging
6. High-throughput scenarios - Stress testing

The goal: Make LogXide faster than Picologging in all scenarios.
"""

import json
import logging
import logging.handlers
import os
import platform
import statistics
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Import libraries
try:
    import picologging

    PICOLOGGING_AVAILABLE = True
    print("✅ Picologging available")
except ImportError:
    PICOLOGGING_AVAILABLE = False
    print("❌ Picologging not available (may not support Python 3.13+)")

try:
    import logxide

    LOGXIDE_AVAILABLE = True
    print("✅ LogXide available")
except ImportError:
    LOGXIDE_AVAILABLE = False
    print("❌ LogXide not available")


class BenchmarkResult:
    """Store benchmark results."""

    def __init__(self, library: str, handler_type: str, scenario: str):
        self.library = library
        self.handler_type = handler_type
        self.scenario = scenario
        self.times: list[float] = []
        self.iterations = 0
        self.messages_per_second = 0
        self.mean_time = 0
        self.std_dev = 0
        self.min_time = 0
        self.max_time = 0

    def add_time(self, elapsed: float, iterations: int):
        self.times.append(elapsed)
        self.iterations = iterations

    def calculate_stats(self):
        if self.times:
            self.mean_time = statistics.mean(self.times)
            self.std_dev = statistics.stdev(self.times) if len(self.times) > 1 else 0
            self.min_time = min(self.times)
            self.max_time = max(self.times)
            self.messages_per_second = (
                self.iterations / self.mean_time if self.mean_time > 0 else 0
            )


class LogXideVsPicologgingBenchmark:
    """Head-to-head benchmark between LogXide and Picologging."""

    def __init__(self, iterations: int = 50000, warmup: int = 1000, runs: int = 5):
        self.iterations = iterations
        self.warmup = warmup
        self.runs = runs
        self.temp_dir = tempfile.mkdtemp(prefix="logxide_vs_pico_")
        self.results: list[BenchmarkResult] = []
        with open(os.devnull, "w") as f:
            self.null_stream = f

        print("Benchmark setup:")
        print(f"  Iterations: {self.iterations:,}")
        print(f"  Warmup: {self.warmup:,}")
        print(f"  Runs: {self.runs}")
        print(f"  Temp dir: {self.temp_dir}")

    def cleanup(self):
        """Clean up temporary files."""
        import shutil

        try:
            self.null_stream.close()
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

    def run_benchmark(
        self,
        library: str,
        handler_type: str,
        scenario: str,
        setup_fn,
        log_fn,
        teardown_fn=None,
    ) -> BenchmarkResult:
        """Run a single benchmark scenario."""
        print(
            f"\n  {library:<12} {handler_type:<18} {scenario:<25}", end="", flush=True
        )

        result = BenchmarkResult(library, handler_type, scenario)

        try:
            for _run in range(self.runs):
                # Setup
                logger, handlers = setup_fn()
                if logger is None:
                    print(" FAILED (setup)")
                    return result

                # Warmup
                for _ in range(self.warmup):
                    log_fn(logger, "warmup message")

                # Clear any buffers
                if hasattr(logger, "flush"):
                    logger.flush()
                elif "logxide" in library.lower():
                    logxide.logxide.logging.flush()

                # Benchmark
                start = time.perf_counter()
                for i in range(self.iterations):
                    log_fn(logger, f"benchmark message {i}")

                # Ensure all messages are processed
                if hasattr(logger, "flush"):
                    logger.flush()
                elif "logxide" in library.lower():
                    logxide.logxide.logging.flush()

                elapsed = time.perf_counter() - start
                result.add_time(elapsed, self.iterations)

                # Teardown
                if teardown_fn:
                    teardown_fn(logger, handlers)
                else:
                    # Default teardown
                    for handler in handlers:
                        if hasattr(handler, "close"):
                            handler.close()

            result.calculate_stats()
            if result.messages_per_second > 0:
                print(f" {result.messages_per_second:>12,.0f} msgs/sec")
            else:
                print(" FAILED")

        except Exception as e:
            print(f" ERROR: {e}")

        return result

    # === FileHandler Benchmarks ===

    def setup_picologging_file(self):
        """Setup Picologging FileHandler."""
        if not PICOLOGGING_AVAILABLE:
            return None, []

        logger = picologging.getLogger(f"pico_file_{time.time()}")
        logger.setLevel(picologging.INFO)
        logger.handlers = []

        log_file = os.path.join(self.temp_dir, f"pico_file_{time.time()}.log")
        handler = picologging.FileHandler(log_file)
        handler.setFormatter(
            picologging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
        logger.addHandler(handler)

        return logger, [handler]

    def setup_logxide_file(self):
        """Setup LogXide FileHandler."""
        if not LOGXIDE_AVAILABLE:
            return None, []

        log_file = os.path.join(self.temp_dir, f"logxide_file_{time.time()}.log")
        with open(log_file, "w") as file_handle:

            def file_handler(record):
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
                file_handle.write(
                    f"{timestamp} - {record.get('logger_name', 'root')} - {record.get('level_name', 'INFO')} - {record.get('message', '')}\n"
                )
                file_handle.flush()

            logxide.logxide.logging.register_python_handler(file_handler)
            logger = logxide.logxide.logging.getLogger(f"logxide_file_{time.time()}")

            return logger, [file_handle]

    # === StreamHandler Benchmarks ===

    def setup_picologging_stream(self):
        """Setup Picologging StreamHandler."""
        if not PICOLOGGING_AVAILABLE:
            return None, []

        logger = picologging.getLogger(f"pico_stream_{time.time()}")
        logger.setLevel(picologging.INFO)
        logger.handlers = []

        handler = picologging.StreamHandler(self.null_stream)
        handler.setFormatter(
            picologging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
        logger.addHandler(handler)

        return logger, [handler]

    def setup_logxide_stream(self):
        """Setup LogXide StreamHandler."""
        if not LOGXIDE_AVAILABLE:
            return None, []

        def stream_handler(record):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
            self.null_stream.write(
                f"{timestamp} - {record.get('logger_name', 'root')} - {record.get('level_name', 'INFO')} - {record.get('message', '')}\n"
            )
            self.null_stream.flush()

        logxide.logxide.logging.register_python_handler(stream_handler)
        logger = logxide.logxide.logging.getLogger(f"logxide_stream_{time.time()}")

        return logger, []

    # === RotatingFileHandler Benchmarks ===

    def setup_picologging_rotating(self):
        """Setup Picologging RotatingFileHandler."""
        if not PICOLOGGING_AVAILABLE:
            return None, []

        logger = picologging.getLogger(f"pico_rotating_{time.time()}")
        logger.setLevel(picologging.INFO)
        logger.handlers = []

        log_file = os.path.join(self.temp_dir, f"pico_rotating_{time.time()}.log")
        # Picologging doesn't have RotatingFileHandler, use FileHandler instead
        handler = picologging.FileHandler(log_file)
        handler.setFormatter(
            picologging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
        logger.addHandler(handler)

        return logger, [handler]

    def setup_logxide_rotating(self):
        """Setup LogXide RotatingFileHandler (manual rotation)."""
        if not LOGXIDE_AVAILABLE:
            return None, []

        log_file = os.path.join(self.temp_dir, f"logxide_rotating_{time.time()}.log")
        with open(log_file, "w") as file_handle:

            def rotating_handler(record):
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
                message = f"{timestamp} - {record.get('logger_name', 'root')} - {record.get('level_name', 'INFO')} - {record.get('message', '')}\n"
                file_handle.write(message)
                file_handle.flush()

                # Simple rotation check (every 10000 messages for this benchmark)
                if hasattr(rotating_handler, "count"):
                    rotating_handler.count += 1
                else:
                    rotating_handler.count = 1

            logxide.logxide.logging.register_python_handler(rotating_handler)
            logger = logxide.logxide.logging.getLogger(
                f"logxide_rotating_{time.time()}"
            )

            return logger, [file_handle]

    # === JSON Formatting Benchmarks ===

    def setup_picologging_json(self):
        """Setup Picologging with JSON formatting."""
        if not PICOLOGGING_AVAILABLE:
            return None, []

        class JSONFormatter(picologging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": datetime.now().isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                    "thread": record.thread,
                    "thread_name": record.threadName,
                    "process": record.process,
                }
                return json.dumps(log_data)

        logger = picologging.getLogger(f"pico_json_{time.time()}")
        logger.setLevel(picologging.INFO)
        logger.handlers = []

        log_file = os.path.join(self.temp_dir, f"pico_json_{time.time()}.log")
        handler = picologging.FileHandler(log_file)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

        return logger, [handler]

    def setup_logxide_json(self):
        """Setup LogXide with JSON formatting."""
        if not LOGXIDE_AVAILABLE:
            return None, []

        log_file = os.path.join(self.temp_dir, f"logxide_json_{time.time()}.log")
        with open(log_file, "w") as file_handle:

            def json_handler(record):
                log_data = {
                    "timestamp": datetime.now().isoformat(),
                    "level": record.get("level_name", "INFO"),
                    "logger": record.get("logger_name", "root"),
                    "message": record.get("message", ""),
                    "module": record.get("module", ""),
                    "function": record.get("function", ""),
                    "line": record.get("line", 0),
                    "thread": record.get("thread_id", ""),
                    "thread_name": record.get("thread_name", ""),
                    "process": record.get("process_id", ""),
                }
                file_handle.write(json.dumps(log_data) + "\n")
                file_handle.flush()

            logxide.logxide.logging.register_python_handler(json_handler)
            logger = logxide.logxide.logging.getLogger(f"logxide_json_{time.time()}")

            return logger, [file_handle]

    # === High-Throughput Benchmarks ===

    def setup_picologging_high_throughput(self):
        """Setup Picologging for high-throughput test."""
        if not PICOLOGGING_AVAILABLE:
            return None, []

        logger = picologging.getLogger(f"pico_high_{time.time()}")
        logger.setLevel(picologging.INFO)
        logger.handlers = []

        # Use NullHandler for maximum throughput
        handler = picologging.NullHandler()
        logger.addHandler(handler)

        return logger, [handler]

    def setup_logxide_high_throughput(self):
        """Setup LogXide for high-throughput test."""
        if not LOGXIDE_AVAILABLE:
            return None, []

        def null_handler(record):
            # Minimal processing
            pass

        logxide.logxide.logging.register_python_handler(null_handler)
        logger = logxide.logxide.logging.getLogger(f"logxide_high_{time.time()}")

        return logger, []

    # === Logging Functions ===

    def log_simple(self, logger, message):
        """Simple logging."""
        logger.info(message)

    def log_formatted(self, logger, message):
        """Formatted logging."""
        logger.info("User %s performed action: %s", "user123", message)

    def log_with_extra(self, logger, message):
        """Logging with extra fields."""
        logger.info(
            "Processing: %s", message, extra={"user_id": 123, "request_id": "req_456"}
        )

    # === Teardown Functions ===

    def teardown_logxide(self, logger, handlers):
        """Teardown LogXide."""
        logxide.logxide.logging.flush()
        for handler in handlers:
            if hasattr(handler, "close"):
                handler.close()

    # === Main Benchmark Runner ===

    def run_all_benchmarks(self):
        """Run all LogXide vs Picologging benchmarks."""
        print("\n🚀 LogXide vs Picologging Head-to-Head Benchmark")
        print("=" * 80)
        print(f"Platform: {platform.platform()}")
        print(f"Python: {sys.version.split()[0]}")
        print("=" * 80)

        if not PICOLOGGING_AVAILABLE:
            print(
                "❌ Picologging not available. Please install: pip install picologging"
            )
            return

        if not LOGXIDE_AVAILABLE:
            print("❌ LogXide not available. Please install: maturin develop")
            return

        print(f"{'Library':<12} {'Handler':<18} {'Scenario':<25} {'Performance':<15}")
        print("-" * 75)

        # 1. FileHandler Benchmarks
        print("\n📁 FILE HANDLER BENCHMARKS")
        print("-" * 75)

        pico_file = self.run_benchmark(
            "Picologging",
            "FileHandler",
            "Simple Messages",
            self.setup_picologging_file,
            self.log_simple,
        )
        self.results.append(pico_file)

        logxide_file = self.run_benchmark(
            "LogXide",
            "FileHandler",
            "Simple Messages",
            self.setup_logxide_file,
            self.log_simple,
            self.teardown_logxide,
        )
        self.results.append(logxide_file)

        # 2. StreamHandler Benchmarks
        print("\n📺 STREAM HANDLER BENCHMARKS")
        print("-" * 75)

        pico_stream = self.run_benchmark(
            "Picologging",
            "StreamHandler",
            "Simple Messages",
            self.setup_picologging_stream,
            self.log_simple,
        )
        self.results.append(pico_stream)

        logxide_stream = self.run_benchmark(
            "LogXide",
            "StreamHandler",
            "Simple Messages",
            self.setup_logxide_stream,
            self.log_simple,
            self.teardown_logxide,
        )
        self.results.append(logxide_stream)

        # 3. RotatingFileHandler Benchmarks
        print("\n🔄 ROTATING FILE HANDLER BENCHMARKS")
        print("-" * 75)

        pico_rotating = self.run_benchmark(
            "Picologging",
            "RotatingFileHandler",
            "Simple Messages",
            self.setup_picologging_rotating,
            self.log_simple,
        )
        self.results.append(pico_rotating)

        logxide_rotating = self.run_benchmark(
            "LogXide",
            "RotatingFileHandler",
            "Simple Messages",
            self.setup_logxide_rotating,
            self.log_simple,
            self.teardown_logxide,
        )
        self.results.append(logxide_rotating)

        # 4. JSON Formatting Benchmarks
        print("\n📋 JSON FORMATTING BENCHMARKS")
        print("-" * 75)

        pico_json = self.run_benchmark(
            "Picologging",
            "JSONHandler",
            "Structured Logging",
            self.setup_picologging_json,
            self.log_formatted,
        )
        self.results.append(pico_json)

        logxide_json = self.run_benchmark(
            "LogXide",
            "JSONHandler",
            "Structured Logging",
            self.setup_logxide_json,
            self.log_formatted,
            self.teardown_logxide,
        )
        self.results.append(logxide_json)

        # 5. High-Throughput Benchmarks
        print("\n⚡ HIGH-THROUGHPUT BENCHMARKS")
        print("-" * 75)

        pico_high = self.run_benchmark(
            "Picologging",
            "NullHandler",
            "Maximum Throughput",
            self.setup_picologging_high_throughput,
            self.log_simple,
        )
        self.results.append(pico_high)

        logxide_high = self.run_benchmark(
            "LogXide",
            "NullHandler",
            "Maximum Throughput",
            self.setup_logxide_high_throughput,
            self.log_simple,
            self.teardown_logxide,
        )
        self.results.append(logxide_high)

        # Print comparison results
        self.print_comparison_results()

        # Save results
        self.save_results()

    def print_comparison_results(self):
        """Print head-to-head comparison results."""
        print("\n" + "=" * 80)
        print("🏆 HEAD-TO-HEAD COMPARISON RESULTS")
        print("=" * 80)

        # Group results by handler type
        handler_groups = {}
        for result in self.results:
            if result.messages_per_second > 0:
                key = f"{result.handler_type}_{result.scenario}"
                if key not in handler_groups:
                    handler_groups[key] = []
                handler_groups[key].append(result)

        # Print comparisons
        logxide_wins = 0
        picologging_wins = 0

        for handler_scenario, results in handler_groups.items():
            if len(results) == 2:
                pico_result = next(
                    (r for r in results if r.library == "Picologging"), None
                )
                logxide_result = next(
                    (r for r in results if r.library == "LogXide"), None
                )

                if pico_result and logxide_result:
                    handler_type = handler_scenario.split("_")[0]
                    scenario = "_".join(handler_scenario.split("_")[1:])

                    print(f"\n📊 {handler_type} - {scenario}")
                    print(
                        f"  Picologging: {pico_result.messages_per_second:>12,.0f} msgs/sec"
                    )
                    print(
                        f"  LogXide:     {logxide_result.messages_per_second:>12,.0f} msgs/sec"
                    )

                    if (
                        logxide_result.messages_per_second
                        > pico_result.messages_per_second
                    ):
                        speedup = (
                            logxide_result.messages_per_second
                            / pico_result.messages_per_second
                        )
                        improvement = (
                            (
                                logxide_result.messages_per_second
                                - pico_result.messages_per_second
                            )
                            / pico_result.messages_per_second
                        ) * 100
                        print(
                            f"  🏆 LogXide WINS: {speedup:.2f}x faster ({improvement:.1f}% improvement)"
                        )
                        logxide_wins += 1
                    else:
                        slowdown = (
                            pico_result.messages_per_second
                            / logxide_result.messages_per_second
                        )
                        gap = (
                            (
                                pico_result.messages_per_second
                                - logxide_result.messages_per_second
                            )
                            / pico_result.messages_per_second
                        ) * 100
                        print(
                            f"  🥈 Picologging wins: {slowdown:.2f}x faster ({gap:.1f}% advantage)"
                        )
                        picologging_wins += 1

        # Overall summary
        print("\n🎯 OVERALL SCORE:")
        print(f"  LogXide wins: {logxide_wins}")
        print(f"  Picologging wins: {picologging_wins}")

        if logxide_wins > picologging_wins:
            print("  🏆 LogXide is the WINNER!")
        elif picologging_wins > logxide_wins:
            print("  🥈 Picologging is ahead - optimization needed!")
        else:
            print("  🤝 It's a tie!")

    def save_results(self):
        """Save benchmark results to JSON."""
        results_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "platform": platform.platform(),
                "python_version": sys.version,
                "picologging_version": picologging.__version__
                if PICOLOGGING_AVAILABLE
                else None,
                "iterations": self.iterations,
                "warmup": self.warmup,
                "runs": self.runs,
            },
            "results": [
                {
                    "library": r.library,
                    "handler_type": r.handler_type,
                    "scenario": r.scenario,
                    "messages_per_second": r.messages_per_second,
                    "mean_time": r.mean_time,
                    "std_dev": r.std_dev,
                    "min_time": r.min_time,
                    "max_time": r.max_time,
                    "iterations": r.iterations,
                }
                for r in self.results
                if r.messages_per_second > 0
            ],
        }

        filename = (
            f"logxide_vs_picologging_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(filename, "w") as f:
            json.dump(results_data, f, indent=2)

        print(f"\n💾 Results saved to: {filename}")


def main():
    """Run the LogXide vs Picologging benchmark."""
    import argparse

    parser = argparse.ArgumentParser(description="LogXide vs Picologging benchmark")
    parser.add_argument(
        "-n",
        "--iterations",
        type=int,
        default=50000,
        help="Number of log messages per benchmark (default: 50000)",
    )
    parser.add_argument(
        "-w",
        "--warmup",
        type=int,
        default=1000,
        help="Number of warmup iterations (default: 1000)",
    )
    parser.add_argument(
        "-r",
        "--runs",
        type=int,
        default=5,
        help="Number of runs per benchmark (default: 5)",
    )

    args = parser.parse_args()

    # Ensure we're using Python 3.12
    if sys.version_info < (3, 12):
        print(
            f"❌ Python 3.12+ required for Picologging compatibility. Current: {sys.version}"
        )
        sys.exit(1)

    benchmark = LogXideVsPicologgingBenchmark(
        iterations=args.iterations, warmup=args.warmup, runs=args.runs
    )

    try:
        benchmark.run_all_benchmarks()
    finally:
        benchmark.cleanup()

    print("\n✅ Benchmark completed!")


if __name__ == "__main__":
    main()
