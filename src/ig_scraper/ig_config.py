"""Configuration and environment overrides for Instagram scraping."""

from __future__ import annotations

import os

from ig_scraper.logging_utils import format_kv, get_logger


logger = get_logger("instagrapi")


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        logger.warning(
            "Invalid integer environment override; using default | %s",
            format_kv(name=name, value=raw_value, default=default),
        )
        return default


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        logger.warning(
            "Invalid float environment override; using default | %s",
            format_kv(name=name, value=raw_value, default=default),
        )
        return default


COMMENTS_PAGE_SIZE = _env_int("IG_COMMENTS_PAGE_SIZE", 250)
REQUEST_PAUSE_SECONDS = _env_float("IG_REQUEST_PAUSE_SECONDS", 0.25)
COMMENT_PAGE_RETRIES = _env_int("IG_COMMENT_PAGE_RETRIES", 3)
MEDIA_DOWNLOAD_RETRIES = _env_int("IG_MEDIA_DOWNLOAD_RETRIES", 3)


def _sleep(reason: str) -> None:
    """Sleep between Instagram requests to avoid rate limiting."""
    logger.info(
        "Sleeping between Instagram requests | %s",
        format_kv(reason=reason, seconds=REQUEST_PAUSE_SECONDS),
    )
    import time

    time.sleep(REQUEST_PAUSE_SECONDS)
