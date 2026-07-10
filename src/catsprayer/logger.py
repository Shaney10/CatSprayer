"""
Application logging utilities.
"""

from __future__ import annotations

import logging

from catsprayer.paths import LOGS_DIR

_LOGGING_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> None:
    """
    Configure application logging.

    Safe to call multiple times.
    """

    global _LOGGING_CONFIGURED

    if _LOGGING_CONFIGURED:
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(
        LOGS_DIR / "catsprayer.log",
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()

    root_logger.setLevel(level)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    _LOGGING_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger for a module.
    """

    return logging.getLogger(name)
