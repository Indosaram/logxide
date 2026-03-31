"""
LogXide structural configuration adapter for dictConfig.
Provides a drop-in replacement for `logging.config.dictConfig` that transparently
promotes standard library handlers into Zero-GIL LogXide native handlers.
"""

import copy
import logging.config

# Map standard python handlers to their high-performance LogXide equivalents
HANDLER_MAP = {
    "logging.FileHandler": "logxide.handlers.FileHandler",
    "logging.StreamHandler": "logxide.handlers.StreamHandler",
    "logging.handlers.RotatingFileHandler": "logxide.handlers.RotatingFileHandler",
    "logging.handlers.TimedRotatingFileHandler": (
        "logxide.handlers.TimedRotatingFileHandler"
    ),
}


def dictConfig(config):
    """
    Configure logging using a dictionary.

    This acts as a transparent proxy to `logging.config.dictConfig`. When it parses
    the dictionary, it replaces standard Python `logging.FileHandler`, `StreamHandler`,
    and `RotatingFileHandler` classes with LogXide's high-performance
    native equivalents.
    Custom formatters and configurations are natively passed down through PyO3 bindings.

    Args:
        config (dict): A dictionary mapping configuration keys to values, matching
                       the standard Python `logging.config.dictConfig` schema.
    """
    # Create a deep copy to prevent mutating the user's operational dictionary
    cfg = copy.deepcopy(config)

    if "handlers" in cfg and isinstance(cfg["handlers"], dict):
        for _name, handler_config in cfg["handlers"].items():
            if not isinstance(handler_config, dict):
                continue

            class_name = handler_config.get("class")

            # If the user explicitly requested a LogXide handler via short-form,
            # we expand it to the full import path to help Python's dynamic importer.
            if class_name == "logxide.FileHandler":
                handler_config["class"] = "logxide.handlers.FileHandler"
            elif class_name == "logxide.StreamHandler":
                handler_config["class"] = "logxide.handlers.StreamHandler"
            elif class_name == "logxide.RotatingFileHandler":
                handler_config["class"] = "logxide.handlers.RotatingFileHandler"
            elif class_name == "logxide.HTTPHandler":
                handler_config["class"] = "logxide.handlers.HTTPHandler"
            elif class_name == "logxide.OTLPHandler":
                handler_config["class"] = "logxide.handlers.OTLPHandler"

            # If it's a standard handler we support, seamlessly promote it
            elif class_name in HANDLER_MAP:
                handler_config["class"] = HANDLER_MAP[class_name]

    # Hand off the mutated config to the robust standard Python configuration parser
    logging.config.dictConfig(cfg)
