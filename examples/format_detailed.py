from logxide import logging

print("=== Detailed Format with Thread Info ===")
detailed_format = (
    "%(asctime)s | %(name)s | %(levelname)-8s | Thread-%(thread)d | %(message)s"
)
logging.basicConfig(format=detailed_format, datefmt="%Y-%m-%d %H:%M:%S")

logger = logging.getLogger("detailed")
logger.setLevel(logging.DEBUG)
logger.debug("Debug message with detailed format")
logger.info("Info message with detailed format")
logger.warning("Warning message with detailed format")
logger.error("Error message with detailed format")
logging.flush()
