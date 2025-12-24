# Use auto-install pattern by importing from logxide
from logxide import logging


def test_module_level_logging():
    logging.info("test_module_level_logging")


def test_exception_logging():
    try:
        raise ValueError("test")
    except:
        logging.exception("test_exception_logging")


def test_logger_methods():
    logger = logging.getLogger("test_logger_methods")
    logger.fatal("fatal")
    logger.warn("warn")
    logger.exception("exception")


def test_compatibility_attributes():
    assert logging.BASIC_FORMAT == "%(levelname)s:%(name)s:%(message)s"
    logger = logging.getLogger("test_compatibility_attributes")
    assert logger.filters == []
    
    # Add a handler so hasHandlers returns True
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    assert logger.hasHandlers()
    
    # Clean up
    logger.removeHandler(handler)
