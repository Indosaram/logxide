import logging

from logxide import logging as lx_logging

magic = lx_logging.getLogger("dummy_lib")
stdlib = logging.getLogger("dummy_lib")

print(f"Are they the exact same object? {magic is stdlib}")
