"""I/O helpers and profile extraction for relationship collection (followers/followees)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ig_scraper.logging_utils import format_kv, get_logger


if TYPE_CHECKING:
    from pathlib import Path


logger = get_logger("relationships")

#: Default chunk size for progressive follower/following writes.
FOLLOW_CHUNK_SIZE = 5000

#: Relationship flags emitted per profile dict when the viewer context is available.
RELATIONSHIP_FLAGS = (
    "followed_by_viewer",
    "follows_viewer",
    "blocked_by_viewer",
    "has_blocked_viewer",
    "has_requested_viewer",
    "requested_by_viewer",
)


def _profile_to_dict(profile: Any) -> dict[str, Any]:
    """Convert an instaloader Profile from get_followers/get_followees to a dict.

    These partial Profile objects contain user identity and relationship flags.
    Extracts all available fields including relationship context when logged in.
    Uses Phase 2 verified flag names.
    """
    result: dict[str, Any] = {
        "id": str(getattr(profile, "userid", "") or ""),
        "username": getattr(profile, "username", "") or "",
        "full_name": getattr(profile, "full_name", "") or "",
        "profile_pic_url": getattr(profile, "profile_pic_url", "") or "",
        "is_private": bool(getattr(profile, "is_private", False)),
        "is_verified": bool(getattr(profile, "is_verified", False)),
        "followers": getattr(profile, "followers", 0) or 0,
        "following": getattr(profile, "followees", 0) or 0,
    }
    # Phase 2 relationship flags — only present when auth context is available.
    for flag in RELATIONSHIP_FLAGS:
        value = getattr(profile, flag, None)
        if value is not None:
            result[flag] = bool(value)
    return result


def _write_chunk(chunk_path: Path, profiles: list[dict[str, Any]]) -> int:
    """Write a single chunk of profiles to disk as JSON."""
    chunk_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(profiles, indent=2, ensure_ascii=False)
    chunk_path.write_text(payload, encoding="utf-8")
    byte_count = len(payload.encode("utf-8"))
    logger.info(
        "Chunk written | %s",
        format_kv(
            path=chunk_path,
            profile_count=len(profiles),
            bytes=byte_count,
        ),
    )
    return byte_count
