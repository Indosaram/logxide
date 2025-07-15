import logxide

# Install logxide as drop-in replacement
logxide.install()

import logging

print("=== Simple Format Example ===")
logging.basicConfig(format="%(levelname)s: %(name)s - %(message)s")

logger = logging.getLogger("simple")
logger.setLevel(logging.INFO)
logger.info("Simple format message")
logger.warning("Warning in simple format")
logger.error("Error in simple format")
logging.flush()
