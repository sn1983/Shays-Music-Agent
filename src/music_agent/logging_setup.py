"""Logging configuration: readable console output plus a rolling file log."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from music_agent.config import PROJECT_ROOT

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def configure_logging(level: str = "INFO", log_dir: Path | None = None) -> None:
    directory = log_dir or PROJECT_ROOT / "logs"
    directory.mkdir(parents=True, exist_ok=True)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(_FORMAT))

    file_handler = RotatingFileHandler(
        directory / "agent.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(_FORMAT))

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(console)
    root.addHandler(file_handler)

    # The HTTP clients are chatty at DEBUG and add nothing here.
    for noisy in ("httpx", "httpcore", "anthropic", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
