"""
Test LogXide compatibility with pytest without using caplog fixture.

This test demonstrates that LogXide logging works correctly in pytest
without requiring the problematic caplog fixture.
"""

import io
import pytest


def test_logging_behavior():
    """Test LogXide logging behavior in pytest without caplog."""
    from logxide import logging, StreamHandler, Formatter

    # Create our own handler to capture output
    stream = io.StringIO()
    handler = StreamHandler(stream)
    handler.setFormatter(Formatter("%(levelname)s:%(name)s:%(message)s"))

    # Create logger and add handler
    logger = logging.getLogger("my_module")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    try:
        # Log a message
        logger.info("This is an info message")
        logging.flush()

        # Verify output
        output = stream.getvalue()
        assert "This is an info message" in output
        assert "INFO" in output
        assert "my_module" in output
    finally:
        # Cleanup
        logger.removeHandler(handler)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])