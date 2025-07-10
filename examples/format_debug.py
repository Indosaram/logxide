from logxide import logging

print("=== Development/Debug Format ===")
debug_format = (
    "[%(asctime)s.%(msecs)03d] %(name)s:%(levelname)s:%(thread)d - %(message)s"
)
logging.basicConfig(format=debug_format, datefmt="%H:%M:%S")

logger = logging.getLogger("debug.module")
logger.setLevel(logging.DEBUG)
logger.debug("Debug trace information")
logger.info("Application state info")
logger.warning("Performance warning")
logger.error("Runtime error occurred")
logger.critical("Critical system failure")
