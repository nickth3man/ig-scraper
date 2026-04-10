"""Tagged posts collection for Instagram via instaloader.

Tagged posts are posts where the profile has been @mentioned. Not all accounts
have this visibility — ``Profile.get_tagged_posts()`` may be restricted or empty
for some profiles even when authenticated. This module handles that gracefully.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ig_scraper.config import _sleep
from ig_scraper.logging_utils import format_kv, get_logger


if TYPE_CHECKING:
    from pathlib import Path


logger = get_logger("tagged")


@dataclass
class TaggedCollectionResult:
    """Result of tagged posts collection: items, skipped flag, skip reason, and file path."""

    items: list[dict[str, Any]] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None
    file_path: str | None = None


def _post_to_dict(post: Any) -> dict[str, Any]:
    """Convert an instaloader Post object to a plain dictionary."""
    return {
        "pk": str(getattr(post, "pk", "") or ""),
        "shortcode": getattr(post, "shortcode", "") or "",
        "url": f"https://www.instagram.com/p/{getattr(post, 'shortcode', '')}/",
        "typename": getattr(post, "typename", "") or "",
        "caption": getattr(post, "caption", "") or "",
        "like_count": getattr(post, "likes", 0) or 0,
        "comment_count": getattr(post, "comments", 0) or 0,
        "taken_at": str(getattr(post, "date", "") or ""),
        "owner_username": getattr(post, "owner_username", "") or "",
        "owner_full_name": getattr(post, "owner_full_name", "") or "",
        "owner_id": str(getattr(post, "owner_id", "") or ""),
        "is_video": bool(getattr(post, "is_video", False)),
        "video_url": getattr(post, "video_url", "") or "",
        "thumbnail_url": getattr(post, "url", "") or "",
        "mentions": list(getattr(post, "caption_mentions", []) or []),
        "hashtags": list(getattr(post, "caption_hashtags", []) or []),
    }


def collect_tagged_posts(
    profile: Any,
    account_dir: Path | None,
) -> TaggedCollectionResult:
    """Collect posts where the profile has been tagged.

    ``Profile.get_tagged_posts()`` may return an empty iterator for accounts
    that have disabled tagging or when the profile is not visible. This is a
    best-effort collection — failures are logged as warnings and the scrape
    continues rather than aborting.

    Args:
        profile: The instaloader Profile object being scraped.
        account_dir: The account directory path where ``tagged/`` will be created.

    Returns:
        TaggedCollectionResult with items on success, or skipped=True with a
        skip_reason on failure.
    """
    if not account_dir:
        return TaggedCollectionResult(skipped=True, skip_reason="no account_dir")

    tagged_root = account_dir / "tagged"
    tagged_list_file = tagged_root / "posts.json"

    username = getattr(profile, "username", "unknown")
    logger.info(
        "Starting tagged posts collection | %s",
        format_kv(username=username),
    )

    t0 = time.perf_counter()
    posts_data: list[dict[str, Any]] = []

    try:
        for post in profile.get_tagged_posts():
            post_dict = _post_to_dict(post)
            posts_data.append(post_dict)
            _sleep("between tagged post iterations")

    except Exception as exc:  # pragma: no cover
        logger.warning(
            "Tagged posts collection failed; continuing without tagged data | %s",
            format_kv(username=username, error=exc),
        )
        return TaggedCollectionResult(
            skipped=True,
            skip_reason=f"Error iterating tagged posts: {exc}",
        )

    tagged_root.mkdir(parents=True, exist_ok=True)
    output: dict[str, Any] = {"tagged_posts": posts_data}
    with tagged_list_file.open("w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)

    elapsed = round(time.perf_counter() - t0, 3)
    logger.info(
        "Tagged posts collection complete | %s",
        format_kv(
            username=username,
            total_tagged=len(posts_data),
            elapsed_seconds=elapsed,
        ),
    )

    return TaggedCollectionResult(
        items=posts_data,
        skipped=False,
        skip_reason=None,
        file_path=str(tagged_list_file),
    )
