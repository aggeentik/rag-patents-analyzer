"""Centralized logging configuration for the patents-analyzer project.

This module provides consistent logging setup across all components.

Usage in modules:
    import logging
    logger = logging.getLogger(__name__)

Usage in scripts (at the top):
    from src.logging_config import setup_logging
    setup_logging()  # or setup_logging(level=logging.DEBUG)
"""

import logging
import sys
from typing import TextIO


def setup_logging(
    level: int = logging.INFO,
    format_string: str | None = None,
    stream: TextIO | None = None,
) -> None:
    """Configure logging for the application.

    Args:
        level: Logging level (default: INFO)
        format_string: Custom format string (optional)
        stream: Output stream (default: sys.stdout)
    """
    if format_string is None:
        format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    if stream is None:
        stream = sys.stdout

    # Configure root logger for src package
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(format_string, datefmt="%H:%M:%S"))

    # Set up the src logger hierarchy
    src_logger = logging.getLogger("src")
    src_logger.setLevel(level)
    src_logger.addHandler(handler)
    src_logger.propagate = False

    # Also configure scripts logger
    scripts_logger = logging.getLogger("scripts")
    scripts_logger.setLevel(level)
    scripts_logger.addHandler(handler)
    scripts_logger.propagate = False


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
