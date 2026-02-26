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
        log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        level = int(getattr(logging, log_level_str, logging.INFO))

    if format_string is None:
        format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    if stream is None:
        stream = sys.stdout

    formatter = logging.Formatter(format_string, datefmt="%H:%M:%S")

    for logger_name in ("src", "scripts", "__main__"):
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        logger.propagate = False
        # Only add handler if none exist (prevents duplicates on Streamlit reruns)
        if not logger.handlers:
            handler = logging.StreamHandler(stream)
            handler.setFormatter(formatter)
            logger.addHandler(handler)
