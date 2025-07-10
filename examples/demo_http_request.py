"""
Demo showing real HTTP requests with logxide formatting.
"""

import logxide

logxide.install()

import logging

logging.basicConfig(
    level=logging.DEBUG, format="%(name)s - %(levelname)s - %(message)s"
)

print("=== Real HTTP Request Demo ===")

try:
    import requests

    # Enable debug logging for urllib3
    urllib3_logger = logging.getLogger("urllib3.connectionpool")
    urllib3_logger.setLevel(logging.DEBUG)

    requests_logger = logging.getLogger("requests.packages.urllib3.connectionpool")
    requests_logger.setLevel(logging.DEBUG)

    logger = logging.getLogger("demo")
    logger.info("Making real HTTP request to test formatting...")

    # Make a real HTTP request - this should trigger actual urllib3 debug logs
    response = requests.get("https://httpbin.org/json", timeout=5)

    logger.info(f"Request completed with status: {response.status_code}")

except Exception as e:
    logger.error(f"Error: {e}")
    import traceback

    traceback.print_exc()

logging.flush()
print("HTTP request demo completed!")
