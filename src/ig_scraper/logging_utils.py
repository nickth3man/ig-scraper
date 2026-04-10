"""Structured logging utilities for the ig-scraper package.

By default, every run creates a timestamped log file under ``logs/`` and captures
DEBUG-level (trace) output. The console stream handler also defaults to DEBUG so
terminal runs show the full action trail.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from ig_scraper.paths import LOGS_DIR


LOGGER_NAME = "ig_scraper"

_DEFAULT_CONSOLE_LEVEL = logging.DEBUG
_DEFAULT_FILE_LEVEL = logging.DEBUG
_cached_log_path: Path | None = None


def _timestamped_log_path() -> Path:
    """Return a ``logs/YYYY-MM-DD_HH-MM-SS.log`` path, creating the directory if needed."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")
    return LOGS_DIR / f"{ts}.log"


def configure_logging(
    console_level: int = _DEFAULT_CONSOLE_LEVEL,
    file_level: int = _DEFAULT_FILE_LEVEL,
    log_file: Path | None = None,
) -> logging.Logger:
    """Configure the root ig-scraper logger.

    Creates two handlers:
    - **Stream handler** (stdout) at *console_level* — shows runtime progress in the terminal.
    - **File handler** at *file_level* — captures trace-level detail for post-mortem.

    When *log_file* is ``None`` a timestamped file under ``logs/`` is generated
    automatically so every run is recorded without any extra setup.
    """
    global _cached_log_path
    logger = logging.getLogger(LOGGER_NAME)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # --- console handler (INFO by default) ---
    has_stream_handler = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in logger.handlers
    )
    if not has_stream_handler:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(console_level)
        logger.addHandler(stream_handler)

    # --- file handler (DEBUG / "trace" by default) ---
    # Resolve the path once and cache it so every get_logger() call reuses the
    # same file instead of opening a second handler with a different timestamp.
    if log_file is not None:
        resolved = log_file.resolve()
    elif _cached_log_path is not None:
        resolved = _cached_log_path
    else:
        resolved = _timestamped_log_path()
        _cached_log_path = resolved
    has_file_handler = any(
        isinstance(h, logging.FileHandler) and Path(h.baseFilename).resolve() == resolved
        for h in logger.handlers
    )
    if not has_file_handler:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(resolved, mode="a", encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(file_level)
        logger.addHandler(file_handler)

    # Root level must be permissive so individual handlers can filter
    logger.setLevel(min(console_level, file_level))
    logger.propagate = False
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return the ig-scraper logger, configuring it if it has not been set up yet."""
    configure_logging()
    if not name:
        return logging.getLogger(LOGGER_NAME)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def format_kv(**kwargs: Any) -> str:
    """Format keyword arguments as a pipe-delimited *key=value* string for structured log lines."""
    parts: list[str] = []
    for key, value in kwargs.items():
        if value is None:
            continue
        parts.append(f"{key}={value}")
    return " | ".join(parts)
