"""
Regression tests for PHASE 6 — native-default text-sink fast path.

Public logxide text-sink wrappers (FileHandler/StreamHandler/RotatingFileHandler) dispatch
via the native Rust engine by default, falling back to Python only for custom Formatter
subclasses, {,$ styles, or handler-level Python filters. MemoryHandler is always native.
"""

import time

import logxide
from logxide import handlers
from logxide import logxide as _ext
from logxide.compat_handlers import Formatter as CompatFormatter

# Real stdlib logging captured at logxide import (before any sys.modules replacement).
from logxide.module_system import _std_logging


def _rust_logger(name):
    logger = _ext.logging.getLogger(name)
    logger.setLevel(10)  # DEBUG
    return logger


def _lines(path):
    with open(path) as f:
        return f.read().splitlines()


def test_native_default_no_formatter(tmp_path):
    log_file = tmp_path / "native.log"
    handler = handlers.FileHandler(str(log_file))
    assert handler._native is True
    assert handler._inner.isNative() is True

    logger = _rust_logger("p6.native.default")
    logger.addHandler(handler)
    logger.info("raw message")
    logxide.flush()
    handler.flush()
    time.sleep(0.2)

    assert _lines(str(log_file)) == ["raw message"]


def test_native_parity_plain_percent_formatter(tmp_path):
    fmt = "%(levelname)s:%(name)s:%(message)s"

    # stdlib reference: format a real stdlib record with a real stdlib Formatter.
    std_file = tmp_path / "std.log"
    std_handler = _std_logging.FileHandler(str(std_file))
    std_handler.setFormatter(_std_logging.Formatter(fmt))
    record = _std_logging.LogRecord(
        "parity.logger", _std_logging.INFO, "path.py", 10, "hello world", None, None
    )
    std_handler.emit(record)
    std_handler.close()
    std_bytes = (std_file).read_bytes()

    # logxide native wrapper: same Formatter, forward the SAME record via emit() (native).
    lx_file = tmp_path / "lx.log"
    lx_handler = handlers.FileHandler(str(lx_file))
    lx_handler.setFormatter(CompatFormatter(fmt))
    assert lx_handler._native is True
    lx_handler.emit(record)
    lx_handler.flush()
    time.sleep(0.2)
    lx_bytes = (lx_file).read_bytes()

    # Compare formatted content parity, normalizing OS newline translation:
    # stdlib opens the file in text mode (\r\n on Windows) while the Rust writer
    # emits \n on every platform.
    assert lx_bytes.replace(b"\r\n", b"\n") == std_bytes.replace(b"\r\n", b"\n"), (
        f"{lx_bytes!r} != {std_bytes!r}"
    )


def test_native_with_args(tmp_path):
    log_file = tmp_path / "args.log"
    handler = handlers.FileHandler(str(log_file))
    logger = _rust_logger("p6.native.args")
    logger.addHandler(handler)
    logger.info("hi %s", "x")
    logxide.flush()
    handler.flush()
    time.sleep(0.2)
    assert _lines(str(log_file)) == ["hi x"]


def test_custom_formatter_subclass_falls_back(tmp_path):
    class CustomFormatter(CompatFormatter):
        def format(self, record):
            return "CUSTOM:" + record.getMessage()

    log_file = tmp_path / "custom.log"
    handler = handlers.FileHandler(str(log_file))
    handler.setFormatter(CustomFormatter())
    assert handler._native is False
    assert handler._inner.isNative() is False

    logger = _rust_logger("p6.custom")
    logger.addHandler(handler)
    logger.info("world")
    logxide.flush()
    handler.flush()
    time.sleep(0.2)
    assert _lines(str(log_file)) == ["CUSTOM:world"]


def test_brace_style_falls_back(tmp_path):
    log_file = tmp_path / "brace.log"
    handler = handlers.FileHandler(str(log_file))
    handler.setFormatter(_std_logging.Formatter("{levelname} {message}", style="{"))
    assert handler._native is False

    logger = _rust_logger("p6.brace")
    logger.addHandler(handler)
    logger.info("braced")
    logxide.flush()
    handler.flush()
    time.sleep(0.2)
    assert _lines(str(log_file)) == ["INFO braced"]


def test_late_set_formatter_no_duplicate(tmp_path):
    log_file = tmp_path / "late.log"
    handler = handlers.FileHandler(str(log_file))
    logger = _rust_logger("p6.late")
    logger.addHandler(handler)

    logger.info("first")  # raw (native, no formatter)
    handler.setFormatter(CompatFormatter("%(levelname)s - %(message)s"))
    logger.info("second")  # formatted (still native)

    logxide.flush()
    handler.flush()
    time.sleep(0.2)
    assert _lines(str(log_file)) == ["first", "INFO - second"]


def test_handler_filter_forces_python_then_restores(tmp_path):
    log_file = tmp_path / "filter.log"
    handler = handlers.FileHandler(str(log_file))
    assert handler._native is True

    class KeepAll:
        def filter(self, record):
            return True

    f = KeepAll()
    handler.addFilter(f)
    assert handler._native is False
    assert handler._inner.isNative() is False

    handler.removeFilter(f)
    assert handler._native is True
    assert handler._inner.isNative() is True


def test_perf_smoke_native_vs_register(tmp_path):
    import os

    n = 20000

    # Native public FileHandler wrapper on a rust logger.
    wrap_file = tmp_path / "wrap.log"
    handler = handlers.FileHandler(str(wrap_file))
    logger = _rust_logger("p6.perf.wrap")
    logger.addHandler(handler)
    start = time.perf_counter()
    for _ in range(n):
        logger.info("perf")
    logxide.flush()
    handler.flush()
    wrap_elapsed = time.perf_counter() - start
    time.sleep(0.2)
    delivered = len(_lines(str(wrap_file)))
    assert delivered == n, f"native wrapper delivered {delivered} of {n}"

    # register_file_handler baseline (proven native engine) to /dev/null.
    _ext.logging.register_file_handler(os.devnull, 10, "%(message)s", None)
    reg_logger = _rust_logger("p6.perf.reg.child")
    reg_logger.parent = _rust_logger("root")
    start = time.perf_counter()
    for _ in range(n):
        reg_logger.info("perf")
    logxide.flush()
    reg_elapsed = time.perf_counter() - start

    wrap_ops = n / wrap_elapsed if wrap_elapsed else float("inf")
    reg_ops = n / reg_elapsed if reg_elapsed else float("inf")
    print(
        f"\n[native-fastpath] wrapper File: {wrap_ops / 1e6:.2f}M rec/s | "
        f"register_file_handler: {reg_ops / 1e6:.2f}M rec/s"
    )
    logxide.clear_handlers()
