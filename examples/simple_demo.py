#!/usr/bin/env python3
"""
Simple LogXide Demo

This demo shows basic usage of LogXide as a drop-in replacement for Python's logging module.
"""

import time
import logxide

# Install LogXide as logging replacement
logxide.install()

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Create logger
logger = logging.getLogger(__name__)

def main():
    """Run the demo."""
    print("LogXide Simple Demo")
    print("==================")
    print()
    
    # Test basic logging
    logger.debug("This is a debug message (won't show with INFO level)")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    print("\nTesting performance...")
    
    # Performance test
    start = time.time()
    for i in range(10000):
        logger.info(f"Performance test message {i}")
    
    # Flush logs
    logging.flush()
    
    elapsed = time.time() - start
    rate = 10000 / elapsed
    
    print(f"\nLogged 10,000 messages in {elapsed:.3f} seconds")
    print(f"Rate: {rate:.0f} messages/second")
    
    # Test child loggers
    print("\nTesting child loggers...")
    child_logger = logging.getLogger(__name__ + ".child")
    child_logger.info("Message from child logger")
    
    # Test logger hierarchy
    print("\nLogger hierarchy:")
    print(f"Main logger: {logger.name}")
    print(f"Child logger: {child_logger.name}")
    
    print("\nDemo complete!")

if __name__ == "__main__":
    main()