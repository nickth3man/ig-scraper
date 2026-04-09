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
        parsed_value = int(raw_value)
        logger.debug(
            "Env override parsed | %s",
            format_kv(name=name, raw_value=raw_value, parsed_value=parsed_value, default=default),
        )
        return parsed_value
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
        parsed_value = float(raw_value)
        logger.debug(
            "Env override parsed | %s",
            format_kv(name=name, raw_value=raw_value, parsed_value=parsed_value, default=default),
        )
        return parsed_value
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
    import time

    logger.debug(
        "Sleep starting | %s",
        format_kv(reason=reason, seconds=REQUEST_PAUSE_SECONDS),
    )
    t0 = time.perf_counter()
    time.sleep(REQUEST_PAUSE_SECONDS)
    elapsed = round(time.perf_counter() - t0, 3)
    logger.debug(
        "Sleep complete | %s",
        format_kv(reason=reason, requested_seconds=REQUEST_PAUSE_SECONDS, actual_seconds=elapsed),
    )


logger.debug(
    "Config constants resolved | %s",
    format_kv(
        COMMENTS_PAGE_SIZE=COMMENTS_PAGE_SIZE,
        REQUEST_PAUSE_SECONDS=REQUEST_PAUSE_SECONDS,
        COMMENT_PAGE_RETRIES=COMMENT_PAGE_RETRIES,
        MEDIA_DOWNLOAD_RETRIES=MEDIA_DOWNLOAD_RETRIES,
    ),
)
