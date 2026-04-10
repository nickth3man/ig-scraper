"""Session management utilities for instaloader authentication."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ig_scraper.logging_utils import format_kv, get_logger


if TYPE_CHECKING:
    from pathlib import Path


logger = get_logger("auth")


def load_cookies_from_file(cookies_path: Path) -> dict[str, str]:
    """Load cookies from a JSON file and return a dict of name-value pairs."""
    try:
        with cookies_path.open(encoding="utf-8") as f:
            cookies_json = json.load(f)
        return {
            cookie["name"]: cookie["value"]
            for cookie in cookies_json
            if "name" in cookie and "value" in cookie
        }
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "Failed to load cookies from file | %s",
            format_kv(path=cookies_path, error=str(exc)[:200]),
        )
        return {}
