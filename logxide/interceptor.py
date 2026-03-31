"""
LogXide Interceptor Module

This module provides tools to intercept standard library logging and
redirect it to LogXide. This is useful for capturing logs from
third-party libraries like requests, sqlalchemy, or dependencies that
hardcode standard logging usage.
"""

import contextlib
import logging
import threading

from . import logger_wrapper

_local = threading.local()


class InterceptHandler(logging.Handler):
    """
    Standard library logging handler that intercepts all logs and
    forwards them to LogXide without duplicating formatting.
    """

    def emit(self, record):
        if getattr(record, "_from_logxide", False):
            return
        if getattr(_local, "in_interceptor", False):
            import traceback

            print("--- REENTRANCY GUARD HIT ---")
            traceback.print_stack()
            return

        _local.in_interceptor = True
        _local.in_interceptor = True
        try:
            logger = logger_wrapper.getLogger(record.name)

            try:
                message = record.getMessage()
            except Exception:
                message = str(record.msg)

            kwargs = {}
            if record.exc_info:
                kwargs["exc_info"] = record.exc_info

            with contextlib.suppress(Exception):
                logger.log(record.levelno, message, **kwargs)
        finally:
            _local.in_interceptor = False


def intercept_stdlib():
    """
    Redirect all standard library logging to LogXide.

    This function:
    1. Replaces the standard root logger's handlers with InterceptHandler.
    2. Modifies all existing loggers to propagate to the root logger
       and removes their specific handlers to prevent duplicate output.
    """
    # 1. Clear root handlers and add InterceptHandler
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # 2. Iterate through all existing loggers and clear their handlers
    if getattr(logging.root, "manager", None) and hasattr(
        logging.root.manager, "loggerDict"
    ):
        for _name, logger_inst in logging.root.manager.loggerDict.items():
            if isinstance(logger_inst, logging.Logger):
                logger_inst.handlers.clear()
                logger_inst.propagate = True
