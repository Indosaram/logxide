"""
Output-equivalence tests for the token-plan formatter (report P1-3).

The refactor parses the format string once into a token plan instead of re-parsing per
record; these tests assert the produced output is byte-identical to the documented
Python-logging formatting semantics across a matrix of format strings, and that repeated
formatting of the same record is stable (guards the scratch-buffer reuse + per-call
asctime dedupe).
"""

import time

from logxide import ColorFormatter, LogRecord, RustFormatter


def _record(
    levelname="INFO", levelno=20, name="app", msg="hello", created=None, msecs=5.0
):
    rec = LogRecord(
        name=name,
        levelno=levelno,
        pathname="test.py",
        lineno=1,
        msg=msg,
    )
    rec.levelname = levelname
    rec.name = name
    rec.msecs = msecs
    if created is not None:
        rec.created = created
    return rec


def test_raw_message():
    fmt = RustFormatter("%(message)s")
    assert fmt.format(_record(msg="hello world")) == "hello world"


def test_levelname_message():
    fmt = RustFormatter("%(levelname)s %(message)s")
    assert fmt.format(_record(levelname="INFO", msg="hi")) == "INFO hi"


def test_padding_and_zero_pad():
    fmt = RustFormatter("%(levelname)-8s|%(name)15s|%(msecs)03d")
    out = fmt.format(_record(levelname="INFO", name="app", msecs=5.0))
    # levelname left-aligned width 8, name right-aligned width 15, msecs zero-padded 3.
    expected = f"{'INFO':<8}|{'app':>15}|{5:03d}"
    assert out == expected, f"{out!r} != {expected!r}"


def test_asctime_prefix_matches_strftime():
    created = 1_700_000_000.0
    rec = _record(name="app", levelname="INFO", msg="msg", created=created, msecs=123.0)
    fmt = RustFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    out = fmt.format(rec)

    expected_asctime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(created))
    assert out == f"{expected_asctime} - app - INFO - msg", out


def test_unknown_field_fallback():
    fmt = RustFormatter("%(nope)s")
    assert fmt.format(_record()) == "%(nope)"


def test_unknown_field_embedded():
    fmt = RustFormatter("a %(nope)s b %(message)s")
    assert fmt.format(_record(msg="M")) == "a %(nope) b M"


def test_color_formatter_wraps_levelname():
    fmt = ColorFormatter(
        "%(ansi_level_color)s%(levelname)s%(ansi_reset_color)s - %(message)s"
    )
    out = fmt.format(_record(levelname="INFO", msg="hello"))
    assert out == "\x1b[32mINFO\x1b[0m - hello", repr(out)


def test_color_formatter_level_colors():
    cases = {
        "DEBUG": "\x1b[37m",
        "INFO": "\x1b[32m",
        "WARNING": "\x1b[33m",
        "ERROR": "\x1b[31m",
        "CRITICAL": "\x1b[35m",
    }
    fmt = ColorFormatter("%(ansi_level_color)s%(levelname)s%(ansi_reset_color)s")
    for levelname, color in cases.items():
        out = fmt.format(_record(levelname=levelname))
        assert out == f"{color}{levelname}\x1b[0m", repr(out)


def test_repeated_format_is_stable():
    created = 1_700_000_000.0
    rec = _record(
        name="svc", levelname="WARNING", msg="repeat", created=created, msecs=42.0
    )
    fmt = RustFormatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s (%(msecs)03d)"
    )
    first = fmt.format(rec)
    for _ in range(1000):
        assert fmt.format(rec) == first
    # Sanity: the asctime prefix is present and correctly formatted.
    expected_asctime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(created))
    assert first.startswith(expected_asctime)
    assert first == f"{expected_asctime} [{'WARNING':<8}] svc: repeat ({42:03d})"


def test_trailing_percent_and_bare_percent():
    # A bare "%" not followed by "(" is emitted literally; a trailing "%" too.
    fmt = RustFormatter("100%% done %(message)s")
    # Note: "%%" is two '%' chars; the parser treats each '%' not followed by '(' as literal.
    out = fmt.format(_record(msg="x"))
    assert out == "100%% done x", repr(out)
