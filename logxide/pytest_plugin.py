"""
LogXide pytest plugin.

Provides caplog fixture for logxide when pytest is installed.
Auto-registered via pyproject.toml entry point.
"""
import pytest

from .testing import LogCaptureFixture

# Import logging from logxide
from . import logxide as _logxide_ext
logging = _logxide_ext.logging


@pytest.fixture
def caplog():
    """
    Pytest caplog fixture for logxide.
    
    Provides pytest caplog-compatible API for capturing logs from logxide.
    
    Usage:
        def test_example(caplog):
            logger = logging.getLogger("test")
            logger.addHandler(caplog.handler)
            logger.info("Hello!")
            
            assert "Hello!" in caplog.text
            assert ("test", 20, "Hello!") in caplog.record_tuples
    """
    fixture = LogCaptureFixture()
    fixture.set_level(10)  # DEBUG level
    yield fixture
    fixture.clear()
