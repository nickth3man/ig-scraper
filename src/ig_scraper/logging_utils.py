"""Structured logging utilities for the ig-scraper package."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


LOGGER_NAME = "ig_scraper"


def _write_run_divider(log_file: Path) -> None:
    """Write a visual divider banner to the log file marking the start of a new run.

    Creates the log file's parent directory if needed. The divider includes a
    timestamp and visual separators for easy scanning of log output.

    Args:
        log_file: Path to the log file where the divider should be written.
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    divider = "\n" + "=" * 100 + "\n" + f"RUN START | {timestamp}\n" + "=" * 100 + "\n"
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(divider)


def configure_logging(level: int = logging.INFO, log_file: Path | None = None) -> logging.Logger:
    """Configure the root ig-scraper logger with a stream handler and optional file handler."""
    logger = logging.getLogger(LOGGER_NAME)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )

    has_stream_handler = any(
        isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
        for handler in logger.handlers
    )
    if not has_stream_handler:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    if log_file is not None:
        resolved_log_file = log_file.resolve()
        has_file_handler = any(
            isinstance(handler, logging.FileHandler)
            and Path(handler.baseFilename).resolve() == resolved_log_file
            for handler in logger.handlers
        )
        if not has_file_handler:
            _write_run_divider(resolved_log_file)
            file_handler = logging.FileHandler(resolved_log_file, mode="a", encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    logger.setLevel(level)
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
