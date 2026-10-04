"""
Logging configuration for Tarot Journal.

Provides a rotating log file (tarot_journal.log) that automatically
archives old logs so disk usage stays small (~4 MB max).
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE = Path(__file__).parent / "tarot_journal.log"
LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 3


def get_logger(name: str) -> logging.Logger:
    """Get a named logger that writes to tarot_journal.log."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = RotatingFileHandler(
            LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    return logger
