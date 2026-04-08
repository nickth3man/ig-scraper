"""Comment pagination and conversion for Instagram scraping."""

from __future__ import annotations

import time
from typing import Any

from ig_scraper.ig_config import (
    COMMENTS_PAGE_SIZE,
    COMMENT_PAGE_RETRIES,
    REQUEST_PAUSE_SECONDS,
    _sleep,
)
from ig_scraper.logging_utils import format_kv, get_logger


logger = get_logger("instagrapi")


def _comment_to_dict(comment: Any, media_url: str) -> dict[str, Any]:
    """Convert an instagrapi Comment object to a plain dictionary for JSON serialization."""
    return {
        "postUrl": media_url,
        "commentUrl": f"{media_url}#comment-{comment.pk}",
        "id": str(comment.pk),
        "text": comment.text or "",
        "ownerUsername": comment.user.username if comment.user else "",
        "ownerFullName": comment.user.full_name if comment.user else "",
        "ownerProfilePicUrl": str(comment.user.profile_pic_url or "") if comment.user else "",
        "timestamp": comment.created_at_utc.isoformat() if comment.created_at_utc else "",
        "likesCount": int(comment.like_count or 0),
        "repliesCount": int(getattr(comment, "child_comment_count", 0) or 0),
    }


def _fetch_all_comments(client: Any, media_id: str, media_url: str) -> list[dict[str, Any]]:
    """Paginate through all comments on a media item using cursor-based pagination.

    Continues fetching pages until Instagram returns no next_min_id or the cursor
    stops advancing. Retries each page attempt COMMENT_PAGE_RETRIES times.
    """
    all_comments: list[dict[str, Any]] = []
    min_id: str | None = None
    page = 0
    while True:
        page += 1
        comments_chunk: list[Any] = []
        next_min_id: str | None = None
        for attempt in range(1, COMMENT_PAGE_RETRIES + 1):
            try:
                logger.info(
                    "Fetching comment page | %s",
                    format_kv(
                        media_id=media_id,
                        page=page,
                        attempt=f"{attempt}/{COMMENT_PAGE_RETRIES}",
                        cursor=min_id or "initial",
                        page_size=COMMENTS_PAGE_SIZE,
                    ),
                )
                if min_id is None:
                    comments_chunk, next_min_id = client.media_comments_chunk(
                        media_id, max_amount=COMMENTS_PAGE_SIZE
                    )
                else:
                    comments_chunk, next_min_id = client.media_comments_chunk(
                        media_id, max_amount=COMMENTS_PAGE_SIZE, min_id=min_id
                    )
                break
            except (RuntimeError, ConnectionError) as exc:
                wait_seconds = round(REQUEST_PAUSE_SECONDS * (2**attempt), 2)
                logger.warning(
                    "Comment page fetch failed | %s",
                    format_kv(
                        media_id=media_id,
                        page=page,
                        attempt=f"{attempt}/{COMMENT_PAGE_RETRIES}",
                        error=exc,
                        retry_wait_seconds=wait_seconds,
                    ),
                )
                if attempt == COMMENT_PAGE_RETRIES:
                    logger.warning(
                        "Giving up on further comment pagination; preserving partial | %s",
                        format_kv(media_id=media_id, page=page, partial_count=len(all_comments)),
                    )
                    return all_comments
                time.sleep(wait_seconds)
        if not comments_chunk:
            logger.info(
                "No comments returned for page; ending pagination | %s",
                format_kv(media_id=media_id, page=page, total_comments=len(all_comments)),
            )
            break
        all_comments.extend(_comment_to_dict(comment, media_url) for comment in comments_chunk)
        logger.info(
            "Comment page fetched | %s",
            format_kv(
                media_id=media_id,
                page=page,
                page_comment_count=len(comments_chunk),
                total_comments=len(all_comments),
                next_cursor=next_min_id or "end",
            ),
        )
        if not next_min_id or next_min_id == min_id:
            break
        min_id = next_min_id
        _sleep("comment pagination backoff")
    return all_comments
