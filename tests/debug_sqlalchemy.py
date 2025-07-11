"""
Debug script to understand SQLAlchemy logging issue.
"""

import logxide

logxide.install()

import logging
import sys

logging.basicConfig(level=logging.DEBUG)

print(f"sys.modules['logging'] type: {type(sys.modules['logging'])}")

# Test the logger creation
logger = logging.getLogger("test")
print(f"Logger type: {type(logger)}")
print(f"Logger has disable: {hasattr(logger, 'disable')}")
print(f"Logger has disabled: {hasattr(logger, 'disabled')}")

# Try to create SQLAlchemy logger specifically
try:
    print("\nTesting SQLAlchemy logger creation...")
    sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
    print(f"SQLAlchemy logger type: {type(sqlalchemy_logger)}")
    print(f"SQLAlchemy logger name: {sqlalchemy_logger.name}")
    print(f"SQLAlchemy logger has disable: {hasattr(sqlalchemy_logger, 'disable')}")

    print("\nTesting logger methods...")
    print(f"setLevel method: {getattr(sqlalchemy_logger, 'setLevel', 'MISSING')}")
    print(f"disable method: {getattr(sqlalchemy_logger, 'disable', 'MISSING')}")

    # Test calling disable
    print("\nCalling disable method...")
    sqlalchemy_logger.disable(10)
    print("✓ disable method called successfully")

    print("\nImporting SQLAlchemy...")

    print("✓ SQLAlchemy imported successfully")

except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
