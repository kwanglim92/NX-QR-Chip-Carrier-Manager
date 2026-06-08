"""File logger for startup and updater diagnostics."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from src.core.database import get_db_dir

_CONFIGURED = False


def _configure_root() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir = get_db_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger with a persistent file handler configured."""
    _configure_root()
    return logging.getLogger(name)
