"""Application logging setup.

Logs are written both to the console and to a rotating file inside the
user-writable ``%APPDATA%/HandGestureMouse/logs`` directory.
"""

import logging
import logging.handlers
import os
from typing import Optional

from .paths import log_dir

_LOGGER_NAME = "handgesturemouse"


def configure_logging(level: int = logging.INFO, log_file: bool = True) -> logging.Logger:
    """Configure and return the root application logger.

    Calling this multiple times is safe: handlers are attached once.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream = logging.StreamHandler()
    stream.setLevel(level)
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    if log_file:
        try:
            os.makedirs(log_dir(), exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                os.path.join(log_dir(), "app.log"),
                maxBytes=1_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError:
            # Logging to file must never crash the application.
            pass

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a child logger of the application logger."""
    if name:
        return logging.getLogger(f"{_LOGGER_NAME}.{name}")
    return logging.getLogger(_LOGGER_NAME)