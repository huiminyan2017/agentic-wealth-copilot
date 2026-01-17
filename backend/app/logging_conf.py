"""Configure application logging.

This module sets a basic logging configuration for the FastAPI backend.  It
formats log messages with timestamps, log level, logger name and message.
"""

import logging


def configure_logging() -> None:
    """Configure the root logger.

    Calling this function multiple times has no effect because Python's
    logging module ignores subsequent basicConfig calls.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )