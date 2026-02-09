"""Centralized logging configuration for the patents-analyzer project.

This module provides consistent logging setup across all components.

Usage in modules:
    import logging
    logger = logging.getLogger(__name__)

Usage in scripts (at the top):
    from src.logging_config import setup_logging
    setup_logging()  # Uses LOG_LEVEL from .env or defaults to INFO

Environment variables:
    LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
"""

import logging
import os
import sys
from typing import TextIO


def setup_logging(
    level: int | None = None,
    format_string: str | None = None,
    stream: TextIO | None = None,
) -> None:
    """Configure logging for the application.

    Args:
        level: Logging level (if None, reads from LOG_LEVEL env var, defaults to INFO)
        format_string: Custom format string (optional)
        stream: Output stream (default: sys.stdout)
    """
    if level is None:
        # Read from environment variable, default to INFO
        log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        level = level_map.get(log_level_str, logging.INFO)
    if format_string is None:
        format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    if stream is None:
        stream = sys.stdout

    # Set up the src logger hierarchy
    src_logger = logging.getLogger("src")
    src_logger.setLevel(level)

    # Only add handler if none exist (prevents duplicates on Streamlit reruns)
    if not src_logger.handlers:
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter(format_string, datefmt="%H:%M:%S"))
        src_logger.addHandler(handler)
    src_logger.propagate = False

    # Also configure scripts logger
    scripts_logger = logging.getLogger("scripts")
    scripts_logger.setLevel(level)

    # Only add handler if none exist
    if not scripts_logger.handlers:
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter(format_string, datefmt="%H:%M:%S"))
        scripts_logger.addHandler(handler)
    scripts_logger.propagate = False

    # Configure __main__ logger for scripts run directly
    main_logger = logging.getLogger("__main__")
    main_logger.setLevel(level)

    if not main_logger.handlers:
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter(format_string, datefmt="%H:%M:%S"))
        main_logger.addHandler(handler)
    main_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    This is a convenience function that ensures consistent logger naming.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Log level constants for convenience
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL
