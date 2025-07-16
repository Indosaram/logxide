"""
Essential test demonstrating LogXide caplog compatibility.

This test shows that the exact requirement from the specification works:
- Import LogXide logging
- Use caplog
- Verify it works correctly
"""

import pytest


def test_logging_behavior(caplog):
    """Test the exact requirement: LogXide works with caplog."""
    from logxide import logging

    logger = logging.getLogger("my_module")
    with caplog.at_level(logging.INFO):
        logger.info("This is an info message")

    assert "This is an info message" in caplog.text
    assert caplog.records[0].levelname == "INFO"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
