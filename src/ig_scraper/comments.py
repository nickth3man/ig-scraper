"""Comment pagination and conversion for Instagram scraping."""

from __future__ import annotations

import time
from typing import Any

from ig_scraper.config import COMMENTS_PAGE_SIZE, REQUEST_PAUSE_SECONDS, _sleep
from ig_scraper.exceptions import RetryExhaustedError as _RetryExhaustedError
from ig_scraper.logging_utils import format_kv, get_logger
from ig_scraper.models import Comment
from ig_scraper.retry import retry_on


logger = get_logger("instagrapi")


def _comment_to_dict(comment: Any, media_url: str) -> dict[str, Any]:
    """Convert an instagrapi Comment object to a plain dictionary for JSON serialization."""
    return Comment.from_instagrapi_comment(comment, media_url).to_dict()


@retry_on(RuntimeError, ConnectionError, max_attempts=3, wait_base_seconds=REQUEST_PAUSE_SECONDS)
def _fetch_comment_page(
    client: Any, media_id: str, min_id: str | None = None, page_size: int = 250
) -> tuple[list[Any], str | None]:
    """Fetch a single page of comments with built-in retry."""
    logger.info(
        "API call: media_comments_chunk starting | %s",
        format_kv(media_id=media_id, min_id=min_id or "initial", page_size=page_size),
    )
    t0 = time.perf_counter()
    if min_id is None:
        result: tuple[list[Any], str | None] = client.media_comments_chunk(
            media_id, max_amount=page_size
        )
    else:
        result = client.media_comments_chunk(media_id, max_amount=page_size, min_id=min_id)
    elapsed = round(time.perf_counter() - t0, 3)
    chunk_count = len(result[0]) if result[0] else 0
    logger.info(
        "API call: media_comments_chunk returned | %s",
        format_kv(
            media_id=media_id,
            comments_in_chunk=chunk_count,
            next_cursor=result[1] or "end",
            elapsed_seconds=elapsed,
        ),
    )
    return result


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
        t0 = time.perf_counter()
        try:
            comments_chunk, next_min_id = _fetch_comment_page(
                client, media_id, min_id=min_id, page_size=COMMENTS_PAGE_SIZE
            )
            page_elapsed = round(time.perf_counter() - t0, 3)
            logger.info(
                "Comment page fetch completed | %s",
                format_kv(media_id=media_id, page=page, elapsed_seconds=page_elapsed),
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

        t_convert = time.perf_counter()
        all_comments.extend(_comment_to_dict(comment, media_url) for comment in comments_chunk)
        convert_elapsed = round(time.perf_counter() - t_convert, 3)
        logger.info(
            "Comment page fetched and converted | %s",
            format_kv(
                media_id=media_id,
                page=page,
                page_comment_count=len(comments_chunk),
                total_comments=len(all_comments),
                convert_seconds=convert_elapsed,
                next_cursor=next_min_id or "end",
            ),
        )

        if not next_min_id or next_min_id == min_id:
            logger.info(
                "Comment pagination cursor exhausted | %s",
                format_kv(
                    media_id=media_id,
                    page=page,
                    reason="no_next_cursor" if not next_min_id else "cursor_unchanged",
                ),
            )
            break

        logger.info(
            "Advancing comment cursor | %s",
            format_kv(media_id=media_id, old_cursor=min_id, new_cursor=next_min_id),
        )
        min_id = next_min_id
        _sleep("comment pagination backoff")

    return all_comments
