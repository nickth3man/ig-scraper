"""Constants, path and I/O utilities for Instagram scraping."""

from __future__ import annotations

import json
import re
import time
from typing import TYPE_CHECKING, Any

from ig_scraper.logging_utils import format_kv, get_logger


logger = get_logger("io")
if TYPE_CHECKING:
    from pathlib import Path


HOOK_WORDS = {
    "how",
    "why",
    "what",
    "watch",
    "if",
    "the",
    "you",
    "your",
    "stop",
    "this",
    "that",
    "with",
    "from",
    "into",
    "have",
    "want",
    "more",
    "will",
    "just",
    "they",
    "them",
    "then",
    "than",
    "about",
    "because",
    "here",
    "there",
    "when",
    "where",
    "which",
    "their",
    "follow",
    "along",
    "lets",
    "crush",
    "together",
    "comment",
    "free",
    "personalized",
    "roadmap",
    "business",
    "under",
    "seconds",
    "years",
    "year",
    "old",
    "started",
    "story",
}

CTA_TOKENS = frozenset({"comment", "dm", "link in bio", "save", "share", "follow", "reply"})

HANDLE_PATTERN = re.compile(r"^[a-zA-Z0-9._]{1,30}$")


def clean_handle(handle: str) -> str:
    """Normalize and validate an Instagram handle."""
    cleaned = handle.strip().lstrip("@").strip()
    if not HANDLE_PATTERN.fullmatch(cleaned):
        raise ValueError(
            "Instagram handles must be 1-30 characters and contain only letters, numbers, periods, or underscores."
        )
    return cleaned


def handle_dir(base_dir: Path, handle: str) -> Path:
    """Return the output directory path for a given handle."""
    return base_dir / f"@{clean_handle(handle)}"


def sanitize_path_segment(value: str, fallback: str = "item") -> str:
    """Convert an arbitrary string to a safe filesystem path segment."""
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return text[:120] or fallback


def ensure_swipes_dir(base_dir: Path, handle: str) -> Path:
    """Create and return the swipes output directory for a handle."""
    path = handle_dir(base_dir, handle) / "swipes"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, data: Any) -> None:
    """Serialize *data* as JSON and write it to *path*, creating parent dirs as needed."""
    t0 = time.perf_counter()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    path.write_text(payload, encoding="utf-8")
    elapsed = round(time.perf_counter() - t0, 3)
    logger.info(
        "JSON written | %s",
        format_kv(path=path, bytes=len(payload.encode("utf-8")), elapsed_seconds=elapsed),
    )


def write_text(path: Path, data: str) -> None:
    """Write *data* to *path* as UTF-8, creating parent dirs as needed."""
    t0 = time.perf_counter()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")
    elapsed = round(time.perf_counter() - t0, 3)
    logger.info(
        "Text written | %s",
        format_kv(path=path, chars=len(data), elapsed_seconds=elapsed),
    )
