"""
Regression test for M1 (0.2.1): caller-frame collection must be driven by ACTUAL need,
not by the mere presence of sentry-sdk.

Importing sentry-sdk pulls in urllib3, which registers a formatter-less NullHandler on the
patched root logger. Previously that flipped the process-global CALLER_INFO_REQUIRED on
(the "non-inspectable formatter => conservatively force caller-info" default), taxing every
log call ~20%. The fix: a formatter-less / non-inspectable foreign handler does NOT force
caller-info; only a formatter that references a caller field (%(lineno)s etc.) does.

CALLER_INFO_REQUIRED is a sticky process-global, so these run in fresh subprocesses to be
deterministic regardless of what the rest of the suite activated.
"""

import subprocess
import sys
import tempfile
import textwrap

import pytest


def _run(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        capture_output=True,
        text=True,
        cwd=tempfile.gettempdir(),  # neutral cwd: avoid the local ./logxide source shadow
        timeout=60,
    )


def test_installed_sentry_does_not_force_caller_info():
    pytest.importorskip("sentry_sdk")
    result = _run(
        """
        import importlib.util
        assert importlib.util.find_spec("sentry_sdk") is not None

        import logxide
        logxide._install()  # triggers sentry auto-config (unconfigured) + urllib3 import
        from logxide import handlers, logging

        log = logging.getLogger("cis.free")
        log.setLevel(logging.DEBUG)
        mh = handlers.MemoryHandler()
        mh.setFormatter(logging.Formatter("%(message)s"))  # NO caller fields
        log.addHandler(mh)
        log.info("x")
        import time; time.sleep(0.05)
        rec = mh.records[-1]
        print("RESULT", repr(rec.pathname), rec.lineno)
        """
    )
    assert result.returncode == 0, result.stderr
    assert "RESULT '' 0" in result.stdout, result.stdout


def test_lineno_formatter_still_populates_caller_info():
    result = _run(
        """
        import logxide
        logxide._install()
        from logxide import handlers, logging

        # Foreign handler (not a logxide wrapper) with a caller-referencing formatter.
        class Capture(logging.Handler):
            def emit(self, record):
                pass

        cap = Capture()
        cap.setFormatter(logging.Formatter("%(lineno)s - %(message)s"))
        log = logging.getLogger("cis.lineno")
        log.setLevel(logging.DEBUG)
        log.addHandler(cap)
        mh = handlers.MemoryHandler()
        log.addHandler(mh)
        log.info("y")
        import time; time.sleep(0.05)
        rec = mh.records[-1]
        print("RESULT", bool(rec.pathname), rec.lineno)
        """
    )
    assert result.returncode == 0, result.stderr
    # caller-info forced by the %(lineno)s formatter => pathname populated, lineno > 0.
    assert "RESULT True" in result.stdout, result.stdout
    import re

    m = re.search(r"RESULT True (\d+)", result.stdout)
    assert m is not None and int(m.group(1)) > 0, result.stdout
