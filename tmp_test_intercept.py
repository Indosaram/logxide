import logging
import threading

from logxide import logging as lx_logging

lx_logger = lx_logging.getLogger()
lx_logger.setLevel(lx_logging.DEBUG)
lock = threading.RLock()

print("Calling outside lock...")
lx_logger.log(logging.INFO, "Outside")

print("Acquiring lock...")
with lock:
    print("Calling inside lock...")
    lx_logger.log(logging.INFO, "Inside lock!")

print("FINISHED!")
