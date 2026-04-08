"""Instagram scraping analysis utilities."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path  # noqa: TC003
from typing import Any

from ig_scraper.analysis_io import (
    CTA_TOKENS,
    HANDLE_PATTERN,
    HOOK_WORDS,
    clean_handle,
    ensure_swipes_dir,
    handle_dir,
    sanitize_path_segment,
    write_json,
    write_text,
)


__all__ = [
    "CTA_TOKENS",
    "HANDLE_PATTERN",
    "HOOK_WORDS",
    "clean_handle",
    "ensure_swipes_dir",
    "extract_hashtags",
    "extract_hook",
    "extract_mentions",
    "get_caption",
    "get_comment_count",
    "get_like_count",
    "get_post_type",
    "get_post_url",
    "get_shortcode",
    "get_timestamp",
    "group_comments_by_post",
    "handle_dir",
    "post_dir",
    "sanitize_path_segment",
    "summarize_comment_texts",
    "top_words",
    "write_json",
    "write_text",
]


def post_dir(base_dir: Path, handle: str, index: int, post: dict[str, Any]) -> Path:
    """Return the filesystem directory for a single scraped post."""
    shortcode = get_shortcode(post) or str(post.get("id") or index)
    name = sanitize_path_segment(f"{index:03d}_{shortcode}", fallback=f"{index:03d}")
    return handle_dir(base_dir, handle) / "posts" / name


def _first_non_empty(item: dict[str, Any], keys: list[str]) -> Any:
    """Return the first non-empty value from item for the given keys."""
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def get_caption(post: dict[str, Any]) -> str:
    """Extract the best available caption text from a post dict."""
    value = _first_non_empty(post, ["caption", "text", "description"])
    if isinstance(value, list):
        return "\n".join(str(v) for v in value if v)
    return str(value or "").strip()


def get_post_url(post: dict[str, Any]) -> str:
    """Return the canonical post URL from a post dict."""
    value = _first_non_empty(post, ["url", "post_url"])
    return str(value or "").strip()


def get_shortcode(post: dict[str, Any]) -> str:
    """Return the shortcode identifier from a post dict."""
    value = _first_non_empty(post, ["short_code", "code"])
    return str(value or "").strip()


def _safe_int(value: Any) -> int:
    """Coerce a value to int, returning 0 for uncoercible types."""
    if isinstance(value, bool):
        return int(value)
    if not isinstance(value, int | float | str):
        return 0
    try:
        return int(value or 0)
    except (ValueError, TypeError):
        return 0


def get_comment_count(post: dict[str, Any]) -> int:
    """Return the comment count from a post dict, defaulting to 0."""
    return _safe_int(_first_non_empty(post, ["comment_count", "comments_count"]))


def get_like_count(post: dict[str, Any]) -> int:
    """Return the like count from a post dict, defaulting to 0."""
    return _safe_int(_first_non_empty(post, ["like_count", "likes_count"]))


def get_timestamp(post: dict[str, Any]) -> str:
    """Return the timestamp string from a post dict."""
    value = _first_non_empty(
        post, ["timestamp", "takenAtTimestamp", "taken_at", "createdAt", "displayTime"]
    )
    return str(value or "").strip()


def get_post_type(post: dict[str, Any]) -> str:
    """Normalise the post type string (reel/video, carousel, etc.) from a post dict."""
    value = _first_non_empty(post, ["type", "typename", "productType", "mediaType"])
    text = str(value or "unknown").lower()
    if "reel" in text or "clip" in text or "video" in text:
        return "reel/video"
    if "sidecar" in text or "carousel" in text:
        return "carousel"
    if text == "unknown" and (
        post.get("videoUrl") or post.get("video_url") or post.get("is_video")
    ):
        return "reel/video"
    from_url = str(post.get("from_url") or "").lower()
    url = str(post.get("url") or "").lower()
    if "/reel/" in url or "/reels/" in from_url:
        return "reel/video"
    if post.get("images") and len(post.get("images", [])) > 1:
        return "carousel"
    return text


def extract_hashtags(text: str) -> list[str]:
    """Return all hashtag strings found in *text*."""
    return re.findall(r"#\w+", text)


def extract_mentions(text: str) -> list[str]:
    """Return all @mention strings found in *text*."""
    return re.findall(r"@\w+(?:\.\w+)?", text)


def extract_hook(text: str) -> str:
    """Extract the first sentence or line of *text* as a hook (≤140 chars)."""
    if not text:
        return ""
    first_line = text.splitlines()[0].strip()
    sentences = re.split(r"(?<=[.!?])\s+", first_line)
    hook = sentences[0].strip() if sentences else first_line
    return hook[:140]


def top_words(texts: list[str], limit: int = 12) -> list[str]:
    """Return the *limit* most-frequent non-stopword tokens across all *texts*."""
    tokens: list[str] = []
    for text in texts:
        tokens.extend(
            word
            for word in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text.lower())
            if word not in HOOK_WORDS and not word.isdigit()
        )
    return [word for word, _ in Counter(tokens).most_common(limit)]


def group_comments_by_post(
    comments: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group a flat list of comment dicts by their associated post identifier."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for comment in comments:
        key = str(
            _first_non_empty(
                comment,
                ["post_url", "postUrl", "postId", "post_id", "shortCode", "shortcode"],
            )
            or "unknown"
        )
        grouped[key].append(comment)
    return grouped


def summarize_comment_texts(comments: list[dict[str, Any]], limit: int = 5) -> str:
    """Return up to *limit* comment texts as a formatted multi-line string."""
    texts = []
    for comment in comments[:limit]:
        text = str(_first_non_empty(comment, ["text", "commentText", "comment"]) or "").strip()
        if text:
            texts.append(f'- "{text[:180]}"')
    return "\n".join(texts) if texts else "No comment text retrieved."
