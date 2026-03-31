import logging

from logxide import handlers
from logxide.config import dictConfig


def test_dictconfig_promotes_stdlib_handlers(tmp_path):
    log_file = tmp_path / "test_app.log"

    # Standard python logging configuration dictionary
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {"format": "%(asctime)s [%(levelname)s] - %(message)s"},
        },
        "handlers": {
            "file": {
                "level": "INFO",
                "formatter": "standard",
                # Note: We use the standard python class name here!
                "class": "logging.FileHandler",
                "filename": str(log_file),
            }
        },
        "loggers": {
            "test_app": {"handlers": ["file"], "level": "INFO", "propagate": False}
        },
    }

    # 1. Apply config using LogXide's adapter
    dictConfig(config)

    # 2. Extract logger and verify handler replacement
    logger = logging.getLogger("test_app")

    # The handler should have been seamlessly promoted to a logxide handler
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], handlers.FileHandler)

    # 3. Fire a log and test if the Rust formatter successfully received the custom format
    logger.info("Structured struct test")

    # Give the Rust thread a tiny moment to flush
    # It flushes on INFO natively if configured, or when dropped
    for h in logger.handlers:
        h.flush()

    log_content = log_file.read_text()
    assert "Structured struct test" in log_content
    # Check if the custom format "[INFO] -" was applied successfully
    assert "[INFO] - Structured struct test" in log_content


def test_dictconfig_preserves_explicit_logxide_handlers(tmp_path):
    log_file = tmp_path / "explicit.log"
    config = {
        "version": 1,
        "formatters": {"custom": {"format": "X-%(message)s-Y"}},
        "handlers": {
            "file": {
                "level": "DEBUG",
                "formatter": "custom",
                "class": "logxide.FileHandler",
                "filename": str(log_file),
            }
        },
        "loggers": {
            "explicit": {
                "handlers": ["file"],
                "level": "DEBUG",
            }
        },
    }

    dictConfig(config)
    logger = logging.getLogger("explicit")

    assert isinstance(logger.handlers[0], handlers.FileHandler)
    logger.debug("Core payload")

    for h in logger.handlers:
        h.flush()

    content = log_file.read_text()
    assert "X-Core payload-Y" in content
