"""Comment pagination and conversion for Instagram scraping."""

from __future__ import annotations

from typing import Any

from ig_scraper.ig_config import COMMENTS_PAGE_SIZE, REQUEST_PAUSE_SECONDS, _sleep
from ig_scraper.ig_retry import _RetryExhaustedError, retry_on
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


@retry_on(RuntimeError, ConnectionError, max_attempts=3, wait_base_seconds=REQUEST_PAUSE_SECONDS)
def _fetch_comment_page(
    client: Any, media_id: str, min_id: str | None = None, page_size: int = 250
) -> tuple[list[Any], str | None]:
    """Fetch a single page of comments with built-in retry."""
    if min_id is None:
        return client.media_comments_chunk(media_id, max_amount=page_size)
    return client.media_comments_chunk(media_id, max_amount=page_size, min_id=min_id)


def _fetch_all_comments(client: Any, media_id: str, media_url: str) -> list[dict[str, Any]]:
    """Paginate through all comments on a media item using cursor-based pagination.

    Continues fetching pages until Instagram returns no next_min_id or the cursor
    stops advancing. Uses @retry_on decorator for per-page retry logic.
    """
    all_comments: list[dict[str, Any]] = []
    min_id: str | None = None
    page = 0
    while True:
        page += 1
        logger.info(
            "Fetching comment page | %s",
            format_kv(
                media_id=media_id,
                page=page,
                cursor=min_id or "initial",
                page_size=COMMENTS_PAGE_SIZE,
            ),
        )
        try:
            comments_chunk, next_min_id = _fetch_comment_page(
                client, media_id, min_id=min_id, page_size=COMMENTS_PAGE_SIZE
            )
        except _RetryExhaustedError as exc:
            logger.warning(
                "Giving up on further comment pagination; preserving partial | %s",
                format_kv(media_id=media_id, page=page, partial_count=len(all_comments), error=exc),
            )
            return all_comments

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
