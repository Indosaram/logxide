"""
Test string formatting in logxide logging methods.
"""

import logxide

logxide.install()

import logging

logging.basicConfig(
    level=logging.DEBUG, format="%(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("format_test")

print("Testing string formatting:")

# Test various format styles
logger.debug("Simple message without formatting")
logger.info("Formatted message: %s", "test value")
logger.warning("Multiple values: %s:%s", "host", 443)
logger.error("Mixed types: %s connection (%d): %s:%s", "HTTPS", 1, "example.com", 443)

# Test the exact urllib3 pattern
logger.debug("Starting new %s connection (%d): %s:%s", "HTTPS", 1, "httpbin.org", 443)
logger.debug(
    '%s://%s:%s "%s %s %s" %s %s',
    "https",
    "httpbin.org",
    443,
    "GET",
    "/json",
    "HTTP/1.1",
    200,
    "OK",
)

print("\nTesting format edge cases:")
logger.info("No args format string %s %d")  # Should not crash
logger.info(
    "Empty args",
)  # Empty tuple
logger.info("Single %s", "value")

logging.flush()
print("Formatting test completed!")
