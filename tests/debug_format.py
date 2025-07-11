"""
Debug string formatting issues.
"""

import logxide

logxide.install()

import logging

logging.basicConfig(level=logging.DEBUG, format="%(message)s")

logger = logging.getLogger("debug")

print("=== Format Debug ===")

# Test basic cases
logger.info("Test 1: %s", "hello")
logger.info("Test 2: %s:%s", "host", 443)
logger.info("Test 3: %s connection (%d): %s:%s", "HTTPS", 1, "example.com", 443)

# Test the problematic urllib3 case
print("\nTesting urllib3 pattern:")
logger.debug("Starting new %s connection (%d): %s:%s", "HTTPS", 1, "httpbin.org", 443)

print("\nTesting complex pattern:")
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

logging.flush()
