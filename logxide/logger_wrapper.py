"""
Logger wrapper and configuration logic for LogXide.

This module handles the integration between Python and Rust logging,
including configuration management and logger migration.
"""

import logging as _std_logging


# Import the Rust extension module directly
from . import logxide
_rust_getLogger = logxide.logging.getLogger
_rust_basicConfig = logxide.logging.basicConfig


# Track existing Python loggers that need to be migrated to LogXide
_existing_logger_registry = {}

# Track the current LogXide configuration to apply to new loggers
_current_config = {
    'level': None,
    'format': None,
    'datefmt': None
}


def basicConfig(**kwargs):
    """
    Basic configuration for the logging system.

    Supported parameters:
    - level: Set the effective level for the root logger
    - format: Format string for log messages
    - datefmt: Date format string
    """
    # Store configuration for applying to new loggers
    _current_config['level'] = kwargs.get("level", None)
    _current_config['format'] = kwargs.get("format", None)
    _current_config['datefmt'] = kwargs.get("datefmt", None)
    
    # Apply configuration to LogXide's Rust backend
    format_str = kwargs.get("format", None)
    datefmt = kwargs.get("datefmt", None)

    # Build kwargs for Rust basicConfig
    rust_kwargs = {}
    if "level" in kwargs:
        rust_kwargs["level"] = kwargs["level"]
    if format_str is not None:
        rust_kwargs["format"] = format_str
    if datefmt is not None:
        rust_kwargs["datefmt"] = datefmt

    # Call Rust basicConfig with processed parameters
    _rust_basicConfig(**rust_kwargs)
    
    # Now handle existing Python loggers that were created before LogXide
    _migrate_existing_loggers()

    # Ensure the root logger has a handler with the specified format
    root_logger = getLogger() # Get the root logger
    if not root_logger.handlers:
        from .compat_handlers import StreamHandler, Formatter
        handler = StreamHandler()
        if format_str:
            formatter = Formatter(format_str, datefmt)
            handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    # Explicitly reconfigure uvicorn loggers to ensure they propagate to LogXide's root
    # This is a targeted fix for uvicorn's aggressive logging setup.
    for logger_name in ['uvicorn', 'uvicorn.error', 'uvicorn.access']:
        uvicorn_logger = getLogger(logger_name) # Get the LogXide PyLogger instance
        if uvicorn_logger:
            uvicorn_logger.handlers.clear() # Clear any handlers uvicorn might have added
            uvicorn_logger.propagate = True # Ensure messages go to the root logger


def _migrate_existing_loggers():
    """
    Discover existing Python loggers and ensure getLogger returns LogXide loggers for them.
    This handles cases where libraries create loggers before LogXide is configured.
    """
    import logging as std_logging
    
    # Access Python's standard logger registry
    if hasattr(std_logging.Logger, 'manager') and hasattr(std_logging.Logger.manager, 'loggerDict'):
        logger_dict = std_logging.Logger.manager.loggerDict
        
        # For each existing logger, register it in our tracking registry
        for logger_name, logger_obj in logger_dict.items():
            if isinstance(logger_obj, std_logging.Logger):
                # Ensure existing loggers use LogXide's root logger
                logger_obj.handlers.clear()  # Remove any existing handlers
                logger_obj.propagate = True   # Let messages go to root logger (our LogXide)
                _existing_logger_registry[logger_name] = True


def getLogger(name=None):
    """
    Get a logger by name, ensuring existing loggers get LogXide functionality.
    
    This wraps the Rust getLogger to handle cases where Python libraries
    created loggers before LogXide was configured.
    """
    # Get the LogXide logger
    from .module_system import _manager
    logger = _rust_getLogger(name, manager=_manager)
    
    # Ensure any retrieved logger propagates to the root and has no other handlers
    # logger.handlers.clear() # Handlers are managed by the Rust side now
    # logger.propagate = True # Propagate is handled by Rust side now

    # Apply the current configuration level if available
    if _current_config['level'] is not None:
        logger.setLevel(_current_config['level'])

    # Set parent for non-root loggers
    if name and '.' in name:
        parent_name = name.rsplit('.', 1)[0]
        parent_logger = getLogger(parent_name)
        logger.parent = parent_logger
    elif name and name != "root":
        logger.parent = getLogger("root")
    
    return logger