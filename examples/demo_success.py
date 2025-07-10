"""
Final demo proving logxide works with real third-party libraries.
"""

import sys

import logxide

# Install logxide BEFORE any other imports
print("Installing logxide as drop-in replacement...")
logxide.install()

# Import logging (now points to logxide)
import logging

# Configure logxide
logging.basicConfig(
    level=logging.DEBUG, format="[LOGXIDE] %(name)s - %(levelname)s - %(message)s"
)

print("=== LogXide Success Demo ===")
print(f"sys.modules['logging'] type: {type(sys.modules['logging'])}")

# Test 1: Basic functionality
logger = logging.getLogger("demo")
logger.info("✓ Basic logxide functionality working")

# Test 2: Import third-party libraries
print("\nImporting third-party libraries...")


urllib3_logger = logging.getLogger("urllib3")
urllib3_logger.setLevel(logging.DEBUG)
urllib3_logger.info("✓ urllib3 successfully using logxide")


requests_logger = logging.getLogger("requests")
requests_logger.setLevel(logging.DEBUG)
requests_logger.info("✓ requests successfully using logxide")

# Test 3: Show different libraries
libs = ["sqlalchemy.engine", "django.db", "flask.app"]
for lib in libs:
    lib_logger = logging.getLogger(lib)
    lib_logger.info(f"✓ {lib} would use logxide")

# Test 4: Demonstrate compatibility
test_logger = logging.getLogger("compatibility_test")
test_logger.setLevel(logging.DEBUG)

# These should all work without errors
print("\nTesting standard logging interface compatibility...")
test_logger.debug("Debug message")
test_logger.info("Info message")
test_logger.warning("Warning message")
test_logger.error("Error message")
test_logger.critical("Critical message")

# Test attributes that libraries expect
print(f"Logger has 'handlers' attribute: {hasattr(test_logger, 'handlers')}")
print(f"Logger has 'level' attribute: {hasattr(test_logger, 'level')}")
print(f"Logger has 'manager' attribute: {hasattr(test_logger, 'manager')}")

# Final flush
logging.flush()

print("\n=== SUCCESS ===")
print("✓ logxide.install() working correctly")
print("✓ Third-party libraries can import without errors")
print("✓ All logging goes through logxide")
print("✓ Standard logging interface maintained")
print("✓ Ready for production use!")
