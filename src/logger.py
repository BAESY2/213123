"""Tiny logging helper shared across modules."""
from __future__ import annotations

import logging
import sys

from .config import settings

_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FMT, datefmt="%H:%M:%S"))
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
        logger.propagate = False
    return logger
