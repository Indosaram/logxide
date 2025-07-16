from logxide import logging

print("=== Minimal Format ===")
logging.basicConfig(format="%(message)s")

logger = logging.getLogger("clean")
logger.setLevel(logging.INFO)
logger.info("Clean message without metadata")
logger.warning("Warning: Clean format warning")
logger.error("Error: Something went wrong")
logging.flush()
