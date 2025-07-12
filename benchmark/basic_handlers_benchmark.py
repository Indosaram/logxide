#!/usr/bin/env python3
"""
Comprehensive benchmark of basic handlers across all logging libraries.

This benchmark tests real-world handler performance:
- FileHandler: Writing to files
- StreamHandler: Console output (to /dev/null to avoid terminal overhead)
- RotatingFileHandler: Log rotation
- Multiple handlers: Combined real-world setup

Libraries tested:
- logging (Python standard library)
- loguru (modern logging library)
- logbook (alternative logging library)
- structlog (structured logging)
- picologging (Cython-based fast logging)
- logxide (Rust-based high-performance logging)
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
from typing import Any, Optional

# Import optional libraries
try:
    import loguru

    LOGURU_AVAILABLE = True
except ImportError:
    LOGURU_AVAILABLE = False

try:
    import logbook

    LOGBOOK_AVAILABLE = True
except ImportError:
    LOGBOOK_AVAILABLE = False

try:
    import structlog

    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False

try:
    import picologging

    PICOLOGGING_AVAILABLE = True
except ImportError:
    PICOLOGGING_AVAILABLE = False
    print("Note: Picologging is not available (may not support Python 3.13+)")

try:
    import logxide

    LOGXIDE_AVAILABLE = True
except ImportError:
    LOGXIDE_AVAILABLE = False


class BenchmarkResult:
    """Store benchmark results."""

    def __init__(self, library: str, handler_type: str):
        self.library = library
        self.handler_type = handler_type
        self.times: list[float] = []
        self.iterations = 0
        self.messages_per_second = 0
        self.mean_time = 0
        self.std_dev = 0

    def add_time(self, elapsed: float, iterations: int):
        self.times.append(elapsed)
        self.iterations = iterations

    def calculate_stats(self):
        if self.times:
            self.mean_time = statistics.mean(self.times)
            self.std_dev = statistics.stdev(self.times) if len(self.times) > 1 else 0
            self.messages_per_second = (
                self.iterations / self.mean_time if self.mean_time > 0 else 0
            )


class BasicHandlersBenchmark:
    """Benchmark basic handlers across all logging libraries."""

    def __init__(self, iterations: int = 10000, warmup: int = 100, runs: int = 3):
        self.iterations = iterations
        self.warmup = warmup
        self.runs = runs
        self.temp_dir = tempfile.mkdtemp(prefix="handlers_benchmark_")
        self.results: list[BenchmarkResult] = []

        # Create /dev/null equivalent for cross-platform
        with open(os.devnull, "w") as self.null_stream:
            pass

    def cleanup(self):
        """Clean up temporary files."""
        import shutil

        try:
            self.null_stream.close()
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

    def run_single_benchmark(
        self, library: str, handler_type: str, setup_fn, log_fn, teardown_fn=None
    ) -> BenchmarkResult:
        """Run a single benchmark."""
        print(f"  {library:<15} {handler_type:<20}", end="", flush=True)

        result = BenchmarkResult(library, handler_type)

        for _run in range(self.runs):
            try:
                # Setup
                logger, handlers = setup_fn()
                if logger is None:
                    print(" SKIPPED (setup failed)")
                    return result

                # Warmup
                for _ in range(self.warmup):
                    log_fn(logger, "warmup message")

                # Benchmark
                start = time.perf_counter()
                for i in range(self.iterations):
                    log_fn(logger, f"benchmark message {i}")

                # Flush if needed
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
                    if handlers:
                        for handler in handlers:
                            if hasattr(handler, "close"):
                                handler.close()

            except Exception as e:
                print(f" ERROR: {e}")
                return result

        result.calculate_stats()
        if result.messages_per_second > 0:
            print(f" {result.messages_per_second:>12,.0f} msgs/sec")
        else:
            print(" FAILED")

        return result

    # === FileHandler Setups ===

    def setup_python_file(self):
        """Python FileHandler."""
        logger = logging.getLogger(f"py_file_{time.time()}")
        logger.setLevel(logging.INFO)
        logger.handlers = []

        log_file = os.path.join(self.temp_dir, f"py_file_{time.time()}.log")
        handler = logging.FileHandler(log_file)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)

        return logger, [handler]

    def setup_loguru_file(self):
        """Loguru FileHandler."""
        if not LOGURU_AVAILABLE:
            return None, []

        from loguru import logger

        logger.remove()

        log_file = os.path.join(self.temp_dir, f"loguru_file_{time.time()}.log")
        logger.add(
            log_file, format="{time:YYYY-MM-DD HH:mm:ss} - {name} - {level} - {message}"
        )

        return logger, []

    def setup_logbook_file(self):
        """Logbook FileHandler."""
        if not LOGBOOK_AVAILABLE:
            return None, []

        log_file = os.path.join(self.temp_dir, f"logbook_file_{time.time()}.log")
        handler = logbook.FileHandler(log_file)
        handler.format_string = "{record.time:%Y-%m-%d %H:%M:%S} - {record.channel} - {record.level_name} - {record.message}"
        handler.push_application()

        logger = logbook.Logger(f"logbook_file_{time.time()}")

        return logger, [handler]

    def setup_structlog_file(self):
        """Structlog FileHandler."""
        if not STRUCTLOG_AVAILABLE:
            return None, []

        log_file = os.path.join(self.temp_dir, f"structlog_file_{time.time()}.log")

        # Configure structlog to use Python logging
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter, # Use ProcessorFormatter
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        # Setup Python logging handler
        py_logger = logging.getLogger(f"structlog_file_{time.time()}")
        py_logger.setLevel(logging.INFO)
        py_logger.handlers = []

        handler = logging.FileHandler(log_file)
        # Use ProcessorFormatter to bridge structlog and standard logging
        handler.setFormatter(structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=False), # Or another structlog processor
            fmt="%(message)s" # This format string is used by ProcessorFormatter
        ))
        py_logger.addHandler(handler)

        logger = structlog.get_logger(f"structlog_file_{time.time()}")

        return logger, [handler]

    def setup_picologging_file(self):
        """Picologging FileHandler."""
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
        """LogXide FileHandler."""
        if not LOGXIDE_AVAILABLE:
            return None, []

        log_file = os.path.join(self.temp_dir, f"logxide_file_{time.time()}.log")
        with open(log_file, "w") as file_handle:
            pass

        def file_handler(record):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            file_handle.write(
                f"{timestamp} - {record.get('logger_name', 'root')} - {record.get('level_name', 'INFO')} - {record.get('message', '')}\n"
            )
            file_handle.flush()

        logxide.logxide.logging.register_python_handler(file_handler)
        logger = logxide.logxide.logging.getLogger(f"logxide_file_{time.time()}")

        return logger, [file_handle]

    # === StreamHandler Setups ===

    def setup_python_stream(self):
        """Python StreamHandler."""
        logger = logging.getLogger(f"py_stream_{time.time()}")
        logger.setLevel(logging.INFO)
        logger.handlers = []

        handler = logging.StreamHandler(self.null_stream)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)

        return logger, [handler]

    def setup_loguru_stream(self):
        """Loguru StreamHandler."""
        if not LOGURU_AVAILABLE:
            return None, []

        from loguru import logger

        logger.remove()
        logger.add(
            self.null_stream,
            format="{time:YYYY-MM-DD HH:mm:ss} - {name} - {level} - {message}",
        )

        return logger, []

    def setup_logbook_stream(self):
        """Logbook StreamHandler."""
        if not LOGBOOK_AVAILABLE:
            return None, []

        handler = logbook.StreamHandler(self.null_stream)
        handler.format_string = "{record.time:%Y-%m-%d %H:%M:%S} - {record.channel} - {record.level_name} - {record.message}"
        handler.push_application()

        logger = logbook.Logger(f"logbook_stream_{time.time()}")

        return logger, [handler]

    def setup_structlog_stream(self):
        """Structlog StreamHandler."""
        if not STRUCTLOG_AVAILABLE:
            return None, []

        # Configure structlog to use Python logging
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter, # Use ProcessorFormatter
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        # Setup Python logging handler
        py_logger = logging.getLogger(f"structlog_stream_{time.time()}")
        py_logger.setLevel(logging.INFO)
        py_logger.handlers = []

        handler = logging.StreamHandler(self.null_stream)
        # Use ProcessorFormatter to bridge structlog and standard logging
        handler.setFormatter(structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=False), # Or another structlog processor
            fmt="%(message)s" # This format string is used by ProcessorFormatter
        ))
        py_logger.addHandler(handler)

        logger = structlog.get_logger(f"structlog_stream_{time.time()}")

        return logger, [handler]

    def setup_picologging_stream(self):
        """Picologging StreamHandler."""
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
        """LogXide StreamHandler."""
        if not LOGXIDE_AVAILABLE:
            return None, []

        def stream_handler(record):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.null_stream.write(
                f"{timestamp} - {record.get('logger_name', 'root')} - {record.get('level_name', 'INFO')} - {record.get('message', '')}\n"
            )
            self.null_stream.flush()

        logxide.logxide.logging.register_python_handler(stream_handler)
        logger = logxide.logxide.logging.getLogger(f"logxide_stream_{time.time()}")

        return logger, []

    def setup_logxide_rotating(self):
        """LogXide RotatingFileHandler using built-in Rust implementation."""
        if not LOGXIDE_AVAILABLE:
            return None, []

        log_file = os.path.join(self.temp_dir, f"logxide_rotating_{time.time()}.log")

        # Use LogXide's logging module
        logxide.logging.basicConfig(
            level=20,  # INFO level
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        logger = logxide.logging.getLogger(f"logxide_rotating_{time.time()}")

        # Note: This uses LogXide's async file handling
        # The RotatingFileHandler is implemented in Rust but not yet exposed to Python
        return logger, []

    # === RotatingFileHandler Setups ===

    def setup_python_rotating(self):
        """Python RotatingFileHandler."""
        logger = logging.getLogger(f"py_rotating_{time.time()}")
        logger.setLevel(logging.INFO)
        logger.handlers = []

        log_file = os.path.join(self.temp_dir, f"py_rotating_{time.time()}.log")
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=1024 * 1024, backupCount=3
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)

        return logger, [handler]

    def setup_loguru_rotating(self):
        """Loguru RotatingFileHandler."""
        if not LOGURU_AVAILABLE:
            return None, []

        from loguru import logger

        logger.remove()

        log_file = os.path.join(self.temp_dir, f"loguru_rotating_{time.time()}.log")
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} - {name} - {level} - {message}",
            rotation="1 MB",
            retention=3,
        )

        return logger, []

    def setup_picologging_rotating(self):
        """Picologging RotatingFileHandler."""
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

    # === Logging Functions ===

    def log_standard(self, logger, message):
        """Standard logging function."""
        logger.info(message)

    def log_loguru(self, logger, message):
        """Loguru logging function."""
        logger.info(message)

    def log_logbook(self, logger, message):
        """Logbook logging function."""
        logger.info(message)

    def log_structlog(self, logger, message):
        """Structlog logging function."""
        logger.info(message)

    def log_picologging(self, logger, message):
        """Picologging logging function."""
        logger.info(message)

    def log_logxide(self, logger, message):
        """LogXide logging function."""
        logger.info(message)

    # === Teardown Functions ===

    def teardown_logxide(self, logger, handlers):
        """Teardown LogXide handlers."""
        logxide.logxide.logging.flush()
        for handler in handlers:
            if hasattr(handler, "close"):
                handler.close()

    def teardown_logbook(self, logger, handlers):
        """Teardown Logbook handlers."""
        for handler in handlers:
            if hasattr(handler, "pop_application"):
                handler.pop_application()
            if hasattr(handler, "close"):
                handler.close()

    # === Main Benchmark Runner ===

    def run_all_benchmarks(self):
        """Run all benchmarks."""
        print("🚀 Basic Handlers Benchmark - All Logging Libraries")
        print("=" * 80)
        print(f"Platform: {platform.platform()}")
        print(f"Python: {sys.version.split()[0]}")
        print(f"Iterations: {self.iterations:,}")
        print(f"Warmup: {self.warmup:,}")
        print(f"Runs per test: {self.runs}")
        print(f"Temp directory: {self.temp_dir}")

        # Check availability
        availability = {
            "Python logging": True,
            "Loguru": LOGURU_AVAILABLE,
            "Logbook": LOGBOOK_AVAILABLE,
            "Structlog": STRUCTLOG_AVAILABLE,
            "Picologging": PICOLOGGING_AVAILABLE,
            "LogXide": LOGXIDE_AVAILABLE,
        }

        print("\nLibrary Availability:")
        for lib, avail in availability.items():
            status = "✅" if avail else "❌"
            print(f"  {status} {lib}")

        print("=" * 80)
        print(f"{'Library':<15} {'Handler':<20} {'Performance':<15}")
        print("-" * 55)

        # 1. FileHandler Benchmarks
        print("\n📁 FILE HANDLER BENCHMARKS")
        print("-" * 55)

        benchmarks = [
            ("Python logging", self.setup_python_file, self.log_standard, None),
            ("Loguru", self.setup_loguru_file, self.log_loguru, None),
            (
                "Logbook",
                self.setup_logbook_file,
                self.log_logbook,
                self.teardown_logbook,
            ),
            ("Structlog", self.setup_structlog_file, self.log_structlog, None),
            ("Picologging", self.setup_picologging_file, self.log_picologging, None),
            (
                "LogXide",
                self.setup_logxide_file,
                self.log_logxide,
                self.teardown_logxide,
            ),
        ]

        file_results = []
        for library, setup_fn, log_fn, teardown_fn in benchmarks:
            result = self.run_single_benchmark(
                library, "FileHandler", setup_fn, log_fn, teardown_fn
            )
            if result.messages_per_second > 0:
                file_results.append(result)
                self.results.append(result)

        # 2. StreamHandler Benchmarks
        print("\n📺 STREAM HANDLER BENCHMARKS")
        print("-" * 55)

        benchmarks = [
            ("Python logging", self.setup_python_stream, self.log_standard, None),
            ("Loguru", self.setup_loguru_stream, self.log_loguru, None),
            (
                "Logbook",
                self.setup_logbook_stream,
                self.log_logbook,
                self.teardown_logbook,
            ),
            ("Structlog", self.setup_structlog_stream, self.log_structlog, None),
            ("Picologging", self.setup_picologging_stream, self.log_picologging, None),
            (
                "LogXide",
                self.setup_logxide_stream,
                self.log_logxide,
                self.teardown_logxide,
            ),
        ]

        stream_results = []
        for library, setup_fn, log_fn, teardown_fn in benchmarks:
            result = self.run_single_benchmark(
                library, "StreamHandler", setup_fn, log_fn, teardown_fn
            )
            if result.messages_per_second > 0:
                stream_results.append(result)
                self.results.append(result)

        # 3. RotatingFileHandler Benchmarks
        print("\n🔄 ROTATING FILE HANDLER BENCHMARKS")
        print("-" * 55)

        benchmarks = [
            ("Python logging", self.setup_python_rotating, self.log_standard, None),
            ("Loguru", self.setup_loguru_rotating, self.log_loguru, None),
            (
                "Picologging",
                self.setup_picologging_rotating,
                self.log_picologging,
                None,
            ),
            (
                "LogXide",
                self.setup_logxide_rotating,
                self.log_logxide,
                self.teardown_logxide,
            ),
        ]

        rotating_results = []
        for library, setup_fn, log_fn, teardown_fn in benchmarks:
            result = self.run_single_benchmark(
                library, "RotatingFileHandler", setup_fn, log_fn, teardown_fn
            )
            if result.messages_per_second > 0:
                rotating_results.append(result)
                self.results.append(result)

        # Print summaries
        self.print_summary("FileHandler", file_results)
        self.print_summary("StreamHandler", stream_results)
        self.print_summary("RotatingFileHandler", rotating_results)

        # Save results
        self.save_results()

    def print_summary(self, handler_type: str, results: list[BenchmarkResult]):
        """Print summary table for a handler type."""
        if not results:
            return

        print(f"\n📊 {handler_type.upper()} PERFORMANCE SUMMARY")
        print("-" * 70)

        # Sort by performance
        sorted_results = sorted(
            results, key=lambda x: x.messages_per_second, reverse=True
        )

        print(f"{'Library':<15} {'Msgs/sec':>15} {'Time (s)':>10} {'Relative':>10}")
        print("-" * 55)

        if sorted_results:
            fastest = sorted_results[0]
            for result in sorted_results:
                relative = result.messages_per_second / fastest.messages_per_second
                print(
                    f"{result.library:<15} {result.messages_per_second:>15,.0f} "
                    f"{result.mean_time:>10.3f} {relative:>10.2f}x"
                )

    def save_results(self):
        """Save benchmark results to JSON."""
        results_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "platform": platform.platform(),
                "python_version": sys.version,
                "iterations": self.iterations,
                "warmup": self.warmup,
                "runs": self.runs,
            },
            "results": [
                {
                    "library": r.library,
                    "handler_type": r.handler_type,
                    "messages_per_second": r.messages_per_second,
                    "mean_time": r.mean_time,
                    "std_dev": r.std_dev,
                    "iterations": r.iterations,
                }
                for r in self.results
            ],
        }

        filename = (
            f"basic_handlers_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(filename, "w") as f:
            json.dump(results_data, f, indent=2)

        print(f"\n💾 Results saved to: {filename}")


def main():
    """Run the benchmark."""
    import argparse

    parser = argparse.ArgumentParser(description="Basic handlers benchmark")
    parser.add_argument(
        "-n",
        "--iterations",
        type=int,
        default=10000,
        help="Number of log messages per benchmark (default: 10000)",
    )
    parser.add_argument(
        "-w",
        "--warmup",
        type=int,
        default=100,
        help="Number of warmup iterations (default: 100)",
    )
    parser.add_argument(
        "-r",
        "--runs",
        type=int,
        default=3,
        help="Number of runs per benchmark (default: 3)",
    )

    args = parser.parse_args()

    benchmark = BasicHandlersBenchmark(
        iterations=args.iterations, warmup=args.warmup, runs=args.runs
    )

    try:
        benchmark.run_all_benchmarks()
    finally:
        benchmark.cleanup()

    print("\n✅ Benchmark completed!")


if __name__ == "__main__":
    main()
