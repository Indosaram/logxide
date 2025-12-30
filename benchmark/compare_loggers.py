#!/usr/bin/env python3
"""
Comprehensive benchmark comparing logxide, structlog, and picologging with realistic file I/O.

This benchmark script tests real-world logging performance by writing to actual files,
not in-memory buffers. This provides accurate measurements of production performance.

Requirements:
    - Python 3.12+
    - logxide (built with: maturin develop --release)
    - picologging
    - structlog

Usage:
    python benchmark/compare_loggers.py

Results are saved to: logger_comparison_file_io_<timestamp>.json
"""

import gc
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# Import logxide - Rust-powered native logging library
try:
    from logxide import logxide as logxide_rust
    logging_mod = logxide_rust.logging
    logxide_getLogger = logging_mod.getLogger
    logxide_FileHandler = logging_mod.FileHandler  # Native Rust FileHandler
    
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    
    print("✓ Successfully imported logxide")
    LOGXIDE_AVAILABLE = True
except Exception as e:
    print(f"✗ Could not import logxide: {e}")
    LOGXIDE_AVAILABLE = False

# Import picologging - C-based fast logging library
try:
    import picologging
    print("✓ Successfully imported picologging")
    PICOLOGGING_AVAILABLE = True
except ImportError:
    print("✗ picologging not available")
    PICOLOGGING_AVAILABLE = False

# Import structlog - Pure Python structured logging
try:
    import structlog
    print("✓ Successfully imported structlog")
    STRUCTLOG_AVAILABLE = True
except ImportError:
    print("✗ structlog not available")
    STRUCTLOG_AVAILABLE = False

# Standard Python logging - will be tested in subprocess to avoid logxide override
STDLIB_AVAILABLE = True


class LoggerBenchmark:
    """
    Benchmark different logging libraries with realistic file I/O.
    
    This class sets up each logger with a FileHandler writing to temporary files,
    runs multiple test scenarios, and collects performance metrics.
    
    Test scenarios:
        1. Simple logging - basic string messages
        2. Structured logging - messages with key-value context
        3. Error logging - error messages with exception context
    
    Each test runs 3 iterations and averages the results for statistical reliability.
    """

    def __init__(self, iterations=100_000):
        """
        Initialize the benchmark suite.
        
        Args:
            iterations: Number of log messages to write per test (default: 100,000)
        """
        self.iterations = iterations
        self.results = {}
        self.temp_files = []

    def cleanup(self):
        """Clean up temporary files."""
        for f in self.temp_files:
            try:
                if os.path.exists(f):
                    os.unlink(f)
            except:
                pass

    def create_temp_file(self):
        """Create a temporary file and track it for cleanup."""
        fd, path = tempfile.mkstemp(suffix='.log')
        os.close(fd)
        self.temp_files.append(path)
        return path

    def setup_logxide_file(self):
        """
        Setup logxide logger with FileHandler writing to a temporary file.
        
        Uses Rust-native FileHandler for maximum performance.
        
        Returns:
            Configured logger or None if logxide is not available
        """
        if not LOGXIDE_AVAILABLE:
            return None
        
        log_file = self.create_temp_file()
        logger = logxide_getLogger(f"benchmark_{id(self)}")
        logger.propagate = False
        # Clear any existing handlers to ensure clean state
        while hasattr(logger, 'handlers') and logger.handlers:
            logger.removeHandler(logger.handlers[0])
        # Add Rust-native FileHandler
        handler = logxide_FileHandler(log_file)
        logger.addHandler(handler)
        logger.setLevel(INFO)
        return logger

    def setup_picologging_file(self):
        """
        Setup picologging logger with FileHandler writing to a temporary file.
        
        Uses picologging's C-based FileHandler for comparison.
        
        Returns:
            Configured logger or None if picologging is not available
        """
        if not PICOLOGGING_AVAILABLE:
            return None
        
        log_file = self.create_temp_file()
        logger = picologging.getLogger(f"benchmark_{id(self)}")
        logger.handlers.clear()
        handler = picologging.FileHandler(log_file)
        # Use same format string as other loggers for fair comparison
        formatter = picologging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(picologging.INFO)
        return logger

    def setup_structlog_file(self):
        """
        Setup structlog logger writing to a temporary file.
        
        Uses structlog's PrintLoggerFactory with JSON rendering.
        File is kept open during the test to avoid overhead.
        
        Returns:
            Configured logger or None if structlog is not available
        """
        if not STRUCTLOG_AVAILABLE:
            return None
        
        log_file = self.create_temp_file()
        # Keep file handle open - will be closed in cleanup
        f = open(log_file, 'w', buffering=8192)
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=f),
        )
        return structlog.get_logger(f"benchmark_{id(self)}")

    def benchmark_stdlib_subprocess(self, benchmark_name):
        """
        Benchmark standard Python logging in a subprocess.
        
        Since logxide overrides the logging module, we need to run
        stdlib logging in a separate process to get accurate measurements.
        
        Args:
            benchmark_name: Name of the benchmark (simple_logging, etc.)
            
        Returns:
            Average time in seconds over 3 runs
        """
        import subprocess
        
        # Create a temporary script to run stdlib logging
        script_content = f'''
import logging
import tempfile
import time
import gc
import os

# Setup
log_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log')
log_file.close()

logger = logging.getLogger("benchmark_stdlib")
logger.handlers.clear()
logger.propagate = False
handler = logging.FileHandler(log_file.name)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

iterations = {self.iterations}
times = []

for run in range(3):
    gc.collect()
    start_time = time.perf_counter()
    
    if "{benchmark_name}" == "simple_logging":
        for i in range(iterations):
            logger.info("Simple log message")
    elif "{benchmark_name}" == "structured_logging":
        for i in range(iterations):
            logger.info(f"User action - user_id: {{i}}, action: login, status: success")
    elif "{benchmark_name}" == "error_logging":
        exception = ValueError("Test exception")
        for i in range(iterations):
            logger.error(f"Error occurred - error: {{exception}}, count: {{i}}")
    
    end_time = time.perf_counter()
    times.append(end_time - start_time)

# Clean up
os.unlink(log_file.name)

# Output average time
avg_time = sum(times) / len(times)
print(avg_time)
'''
        
        # Write script to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script_content)
            script_path = f.name
        
        try:
            # Run the script
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                avg_time = float(result.stdout.strip())
                return avg_time
            else:
                print(f"Error running stdlib benchmark: {result.stderr}")
                return None
        finally:
            # Clean up script
            os.unlink(script_path)



    def benchmark_simple_logging(self, logger, logger_name):
        """
        Benchmark simple string logging.
        
        Tests basic INFO level logging with a static string message.
        This represents the most common logging use case.
        
        Args:
            logger: Configured logger instance
            logger_name: Name of the logger library (for output)
            
        Returns:
            Elapsed time in seconds
        """
        gc.collect()  # Clear any garbage before timing
        start_time = time.perf_counter()

        for _i in range(self.iterations):
            logger.info("Simple log message")

        end_time = time.perf_counter()
        return end_time - start_time

    def benchmark_structured_logging(self, logger, logger_name):
        """
        Benchmark structured logging with context parameters.
        
        Tests logging with additional context data (key-value pairs).
        Logxide and structlog support native structured logging,
        while picologging requires string formatting.
        
        Args:
            logger: Configured logger instance
            logger_name: Name of the logger library (for output)
            
        Returns:
            Elapsed time in seconds
        """
        gc.collect()  # Clear any garbage before timing
        start_time = time.perf_counter()

        for i in range(self.iterations):
            if logger_name in ["logxide", "structlog"]:
                # Native structured logging with kwargs
                logger.info("User action", user_id=i, action="login", status="success")
            elif logger_name in ["picologging", "logging"]:
                # Picologging and stdlib don't support structured logging, use f-string
                logger.info(
                    f"User action - user_id: {i}, action: login, status: success"
                )

        end_time = time.perf_counter()
        return end_time - start_time

    def benchmark_error_logging(self, logger, logger_name):
        """
        Benchmark error logging with exception context.
        
        Tests ERROR level logging with exception information.
        This represents error handling scenarios in production.
        
        Args:
            logger: Configured logger instance
            logger_name: Name of the logger library (for output)
            
        Returns:
            Elapsed time in seconds
        """
        gc.collect()  # Clear any garbage before timing
        exception = ValueError("Test exception")
        start_time = time.perf_counter()

        for i in range(self.iterations):
            if logger_name in ["logxide", "structlog"]:
                # Structured error logging
                logger.error("Error occurred", error=str(exception), count=i)
            elif logger_name in ["picologging", "logging"]:
                # F-string formatting for picologging and stdlib
                logger.error(f"Error occurred - error: {exception}, count: {i}")

        end_time = time.perf_counter()
        return end_time - start_time

    def run_benchmarks(self):
        """
        Run all benchmarks for all loggers.
        
        Executes three test scenarios (simple, structured, error) for each logger,
        running 3 iterations per scenario and averaging the results.
        
        Results are stored in self.results for later analysis.
        """
        print(f"\n{'='*80}")
        print(f"STARTING FILE I/O BENCHMARKS ({self.iterations:,} iterations per test)")
        print(f"{'='*80}\n")

        # Map logger names to their setup functions
        setup_functions = {
            "logxide": self.setup_logxide_file,
            "picologging": self.setup_picologging_file,
            "structlog": self.setup_structlog_file,
        }
        
        benchmarks = [
            ("simple_logging", self.benchmark_simple_logging),
            ("structured_logging", self.benchmark_structured_logging),
            ("error_logging", self.benchmark_error_logging),
        ]

        for benchmark_name, benchmark_func in benchmarks:
            print(f"Running {benchmark_name.replace('_', ' ').title()}...")
            self.results[benchmark_name] = {}

            # First, run stdlib logging in subprocess
            if STDLIB_AVAILABLE:
                print(f"  {'logging':.<20}", end="", flush=True)
                avg_time = self.benchmark_stdlib_subprocess(benchmark_name)
                
                if avg_time is not None:
                    self.results[benchmark_name]["logging"] = {
                        "avg_time": avg_time,
                        "std_dev": 0.0,  # Subprocess doesn't return individual times
                        "min_time": avg_time,
                        "max_time": avg_time,
                        "ops_per_second": self.iterations / avg_time,
                    }
                    print(f" {avg_time:.4f}s ({self.iterations / avg_time:,.0f} ops/sec)")
                else:
                    print(" ERROR")
            
            # Then run other loggers normally
            for logger_name, setup_func in setup_functions.items():
                print(f"  {logger_name:.<20}", end="", flush=True)

                # Run multiple times and take the average
                times = []
                for run in range(3):
                    logger = setup_func()
                    if logger is None:
                        print(" SKIPPED (not available)")
                        break
                    
                    try:
                        duration = benchmark_func(logger, logger_name)
                        times.append(duration)
                    except Exception as e:
                        print(f" ERROR: {e}")
                        break
                    finally:
                        # Clean up for next run
                        self.cleanup()
                
                if not times:
                    continue

                avg_time = statistics.mean(times)
                std_dev = statistics.stdev(times) if len(times) > 1 else 0

                self.results[benchmark_name][logger_name] = {
                    "avg_time": avg_time,
                    "std_dev": std_dev,
                    "min_time": min(times),
                    "max_time": max(times),
                    "ops_per_second": self.iterations / avg_time,
                }
                
                print(f" {avg_time:.4f}s ({self.iterations / avg_time:,.0f} ops/sec)")
            
            print()

    def print_results(self):
        """
        Print benchmark results in a formatted table.
        
        Displays results sorted by performance (fastest first) with
        relative performance comparisons.
        """
        print("\n" + "="*80)
        print(f"FINAL RESULTS - FILE I/O ({self.iterations:,} iterations)")
        print("="*80)

        for benchmark_name, results in self.results.items():
            print(f"\n{benchmark_name.upper().replace('_', ' ')}:")
            print("-" * 80)
            print(f"{'Logger':<15} {'Avg Time (s)':<15} {'Ops/sec':<20} {'Std Dev':<15}")
            print("-" * 80)

            # Sort by average time (fastest first)
            sorted_results = sorted(results.items(), key=lambda x: x[1]["avg_time"])

            for logger_name, metrics in sorted_results:
                print(
                    f"{logger_name:<15} "
                    f"{metrics['avg_time']:<15.6f} "
                    f"{metrics['ops_per_second']:<20,.0f} "
                    f"{metrics['std_dev']:<15.6f}"
                )

            # Show relative performance
            if sorted_results:
                print("\nRelative Performance:")
                fastest_time = sorted_results[0][1]["avg_time"]
                fastest_name = sorted_results[0][0]
                for logger_name, metrics in sorted_results:
                    ratio = metrics["avg_time"] / fastest_time
                    if ratio > 1.01:
                        speedup = metrics['ops_per_second'] / sorted_results[0][1]['ops_per_second']
                        print(f"  {logger_name}: {ratio:.2f}x slower than {fastest_name}")
                    else:
                        print(f"  {logger_name}: fastest ⭐")

    def save_results(self):
        """
        Save results to JSON file with timestamp.
        
        Output includes:
            - Timestamp
            - Iteration count
            - Python version info
            - Detailed results for each scenario and logger
        
        File format: logger_comparison_file_io_YYYYMMDD_HHMMSS.json
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"logger_comparison_file_io_{timestamp}.json"

        output = {
            "timestamp": timestamp,
            "iterations": self.iterations,
            "python_version": sys.version,
            "scenario": "file_io",
            "results": self.results,
        }

        with open(filename, "w") as f:
            json.dump(output, f, indent=2)

        print(f"\n{'='*80}")
        print(f"Results saved to {filename}")
        print(f"{'='*80}")


def main():
    """
    Run the benchmark comparison.
    
    This is the main entry point that:
    1. Creates a benchmark suite with 100,000 iterations
    2. Runs all test scenarios
    3. Prints formatted results
    4. Saves results to JSON
    5. Cleans up temporary files
    
    Results demonstrate LogXide's performance advantages in real-world
    file I/O scenarios compared to Picologging (C-based) and Structlog
    (pure Python).
    """
    print("\n" + "="*80)
    print("LOGXIDE vs PICOLOGGING vs PYTHON LOGGING vs STRUCTLOG")
    print("Realistic File I/O Benchmark")
    print("="*80)

    benchmark = LoggerBenchmark(iterations=100_000)
    try:
        benchmark.run_benchmarks()
        benchmark.print_results()
        benchmark.save_results()
    finally:
        benchmark.cleanup()


if __name__ == "__main__":
    main()