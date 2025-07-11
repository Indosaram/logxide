"""
Debug string formatting issues with info level.
"""

import logxide

logxide.install()

import logging

logging.basicConfig(
    level=logging.DEBUG, format="%(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("debug")
logger.setLevel(logging.DEBUG)

print("=== Format Debug ===")

# Test basic cases
logger.info("Test 1: %s", "hello")
logger.info("Test 2: %s:%s", "host", 443)

print("\nTesting urllib3 pattern:")
logger.info("Starting new %s connection (%d): %s:%s", "HTTPS", 1, "httpbin.org", 443)

print("\nTesting complex pattern:")
logger.info(
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
