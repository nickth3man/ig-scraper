"""Story collection via instaloader."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ig_scraper.exceptions import (
    AuthError,
    IgScraperError,
    is_instaloader_authorization_failure,
)
from ig_scraper.logging_utils import format_kv, get_logger


if TYPE_CHECKING:
    from pathlib import Path

    from instaloader import Instaloader


logger = get_logger("stories")


@dataclass
class StoryCollectionResult:
    """Result of story collection: manifest-friendly items, skipped flag, skip reason, and file path."""

    items: list[dict[str, Any]] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None
    file_path: str | None = None


def _is_auth_error(exc: BaseException) -> bool:
    """Return True if *exc* is an authorization failure for story access."""
    if isinstance(exc, (IgScraperError, AuthError)):
        return True
    exc_name = type(exc).__name__
    if exc_name in {"LoginRequiredException", "LoginRequired", "ChallengeRequired"}:
        return True
    return is_instaloader_authorization_failure(exc)


def _format_datetime(value: Any) -> str:
    """Format a datetime or date-like object to ISO8601 string, or empty string."""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[no-any-return]
    return str(value)


def _build_story_item(item: Any) -> dict[str, Any]:
    """Build a dict for a single story item."""
    return {
        "caption": getattr(item, "caption", "") or "",
        "hashtags": list(getattr(item, "caption_hashtags", []) or []),
        "mentions": list(getattr(item, "caption_mentions", []) or []),
        "date_utc": _format_datetime(getattr(item, "date_utc", None)),
        "is_video": bool(getattr(item, "is_video", False)),
        "video_url": getattr(item, "video_url", None) or None,
        "url": getattr(item, "url", "") or "",
    }


def _write_json(path: Path, data: Any) -> None:
    """Write JSON data to path, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def collect_stories(
    client: Instaloader,
    profile: Any,
    account_dir: Path,
) -> StoryCollectionResult:
    """Collect stories for the authenticated account.

    Calls ``client.get_stories()`` to iterate through active stories,
    extracts metadata and writes per-story JSON files.  Auth/login failures
    are caught and logged as warnings; the function returns a
    ``skipped`` result instead of propagating.

    Args:
        client: An instaloader client instance.
        profile: The instaloader Profile object for the account.
        account_dir: The account directory path.

    Returns:
        A ``StoryCollectionResult`` with ``items`` (manifest-friendly story
        entries), ``skipped`` flag, ``skip_reason`` description, and
        ``file_path`` pointing to the stories index JSON.  On auth failure
        the result includes ``skipped=True`` and a descriptive skip_reason.
    """
    username = getattr(profile, "username", "MISSING")
    logger.info("Starting story collection | %s", format_kv(username=username))

    t0 = time.perf_counter()
    stories_root = account_dir / "stories"
    stories_root.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    story_items: list[dict[str, Any]] = []

    try:
        for story in client.get_stories():
            story_id = str(story.id)
            story_dir = stories_root / story_id
            story_dir.mkdir(parents=True, exist_ok=True)

            story_items_list: list[Any] = list(story.get_items())
            logger.debug(
                "Processing story | %s",
                format_kv(
                    story_id=story_id,
                    owner_username=getattr(story, "username", username),
                    item_count=len(story_items_list),
                ),
            )

            latest_utc = ""
            if story_items_list:
                latest_utc = _format_datetime(getattr(story_items_list[-1], "date_utc", None))

            output: dict[str, Any] = {
                "owner_username": getattr(story, "username", username),
                "media_count": len(story_items_list),
                "latest_media_utc": latest_utc,
                "items": [_build_story_item(item) for item in story_items_list],
            }

            story_file = story_dir / f"{story_id}.json"
            _write_json(story_file, output)

            story_items.append(
                {
                    "story_id": story_id,
                    "file": str(story_file),
                    "media_count": len(story_items_list),
                }
            )
            items.append(output)

            logger.info(
                "Story written | %s",
                format_kv(story_id=story_id, item_count=len(story_items_list), file=story_file),
            )

    except BaseException as exc:
        if _is_auth_error(exc):
            reason = f"auth/login failure for @{username}: {exc}"
            logger.warning(
                "Story collection skipped due to auth failure | %s",
                format_kv(username=username, reason=reason),
            )
            return StoryCollectionResult(skipped=True, skip_reason=reason)

        logger.warning(
            "Story collection failed unexpectedly | %s",
            format_kv(username=username, exc_type=type(exc).__name__, error=str(exc)[:200]),
        )
        return StoryCollectionResult(skipped=True, skip_reason=f"unexpected error: {exc}")

    elapsed = round(time.perf_counter() - t0, 3)
    logger.info(
        "Story collection complete | %s",
        format_kv(
            stories_count=len(story_items),
            items_count=sum(item.get("media_count", 0) for item in story_items),
            elapsed_seconds=elapsed,
        ),
    )

    stories_index_file = stories_root / "stories.json"
    if story_items:
        _write_json(stories_index_file, {"stories": story_items})

    return StoryCollectionResult(
        items=story_items,
        skipped=False,
        skip_reason=None,
        file_path=str(stories_index_file) if story_items else None,
    )
