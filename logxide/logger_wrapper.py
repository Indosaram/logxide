"""
LogXide Logger Wrapper Module

This module provides the Python interface to LogXide's Rust implementation,
including configuration management and logger migration.
"""

import contextlib

# Import the Rust extension module directly
try:
    from . import logxide

    _rust_getLogger = logxide.logging.getLogger
    _rust_basicConfig = logxide.logging.basicConfig
except ImportError:
    # Handle case where Rust extension is not available
    def _rust_getLogger(name=None):  # type: ignore[misc]
        return object()

    def _rust_basicConfig(**kwargs):  # type: ignore[misc]
        pass


# Track existing Python loggers that need to be migrated to LogXide
_existing_logger_registry = {}

# Track the current LogXide configuration to apply to new loggers
_current_config = {"level": None, "format": None, "datefmt": None}

# Track whether basicConfig has been called to prevent duplicate handlers
_basic_config_called = False


def basicConfig(**kwargs):
    """
    Basic configuration for the logging system.

    Supported parameters:
    - level: Set the effective level for the root logger
    - format: Format string for log messages (not implemented in Rust handlers)
    - datefmt: Date format string (not implemented in Rust handlers)
    - stream: Stream to write log output to (sys.stdout or sys.stderr supported)
    - filename: Log to a file instead of a stream
    - force: If True, remove any existing handlers and reconfigure (default: False)

    Note: LogXide uses Rust native handlers for performance. All handler
    configuration is done through this function. Direct handler registration
    via addHandler() is not supported.

    Like Python's standard logging, basicConfig() will do nothing if the root
    logger already has handlers configured, unless force=True is specified.
    """
    import sys

    # Import logxide at the top of the function
    from . import logxide as logxide_module

    global _basic_config_called

    # Check if already configured (unless force=True)
    force = kwargs.get("force", False)
    if _basic_config_called and not force:
        return

    # If force=True, clear existing handlers
    if force and _basic_config_called:
        with contextlib.suppress(ImportError, AttributeError):
            logxide_module.logging.clear_handlers()

    _basic_config_called = True

    # Store configuration for applying to new loggers
    _current_config["level"] = kwargs.get("level")
    _current_config["format"] = kwargs.get("format")
    _current_config["datefmt"] = kwargs.get("datefmt")

    # Get configuration parameters
    level = kwargs.get("level", 10)  # Default to DEBUG (10)
    stream = kwargs.get("stream")
    filename = kwargs.get("filename")

    # Register appropriate Rust native handler
    if filename:
        # File handler
        logxide_module.logging.register_file_handler(filename, level)
    else:
        # Stream handler (stdout, stderr, or Python object like StringIO)
        if stream is None:
            # Default to stderr
            logxide_module.logging.register_stream_handler("stderr", level)
        elif stream is sys.stdout:
            logxide_module.logging.register_stream_handler("stdout", level)
        elif stream is sys.stderr:
            logxide_module.logging.register_stream_handler("stderr", level)
        else:
            # Python file-like object (StringIO, file, etc.)
            # Pass the Python object directly to Rust
            logxide_module.logging.register_stream_handler(stream, level)

    # Set root logger level
    root_logger = getLogger()
    if hasattr(root_logger, "setLevel"):
        root_logger.setLevel(level)

    # Now handle existing Python loggers that were created before LogXide
    _migrate_existing_loggers()

    # Explicitly reconfigure uvicorn loggers to ensure they propagate to LogXide's root
    # This is a targeted fix for uvicorn's aggressive logging setup.
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        uvicorn_logger = getLogger(logger_name)
        if uvicorn_logger:
            with contextlib.suppress(AttributeError):
                uvicorn_logger.handlers.clear()
                uvicorn_logger.propagate = True


def _migrate_existing_loggers():
    """
    Discover existing Python loggers and ensure getLogger returns LogXide loggers.
    This handles cases where libraries create loggers before LogXide is configured.
    """
    import logging as std_logging

    # Access Python's standard logger registry
    if hasattr(std_logging.Logger, "manager") and hasattr(
        std_logging.Logger.manager, "loggerDict"
    ):
        logger_dict = std_logging.Logger.manager.loggerDict

        # For each existing logger, register it in our tracking registry
        for logger_name, logger_obj in logger_dict.items():
            if isinstance(logger_obj, std_logging.Logger):
                # Ensure existing loggers use LogXide's root logger
                logger_obj.handlers.clear()  # Remove any existing handlers
                logger_obj.propagate = True  # Let messages go to root
                _existing_logger_registry[logger_name] = True


# Track loggers to ensure we return singleton instances
_logger_cache = {}


def getLogger(name=None):
    """
    Get a logger by name, ensuring existing loggers get LogXide functionality.
    """
    if name is None:
        name = "root"

    if name in _logger_cache:
        return _logger_cache[name]

    # Get the LogXide logger
    logger = _rust_getLogger(name)
    _logger_cache[name] = logger

    # Ensure any retrieved logger propagates to the root and has no other handlers
    # logger.handlers.clear() # Handlers are managed by the Rust side now
    # logger.propagate = True # Propagate is handled by Rust side now

    # Apply the current configuration level if available
    if _current_config["level"] is not None:
        with contextlib.suppress(AttributeError):
            logger.setLevel(_current_config["level"])

    # Set parent for non-root loggers
    if name and "." in name:
        parent_name = name.rsplit(".", 1)[0]
        parent_logger = getLogger(parent_name)
        with contextlib.suppress(AttributeError):
            logger.parent = parent_logger
    elif name and name != "root":
        with contextlib.suppress(AttributeError):
            logger.parent = getLogger("root")

    return logger
