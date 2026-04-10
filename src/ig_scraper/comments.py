"""Comment pagination and conversion for Instagram scraping via instaloader."""

from __future__ import annotations

from typing import Any

from instaloader.exceptions import (
    ConnectionException,
    QueryReturnedNotFoundException,
    TooManyRequestsException,
)

from ig_scraper.logging_utils import format_kv, get_logger
from ig_scraper.models import Comment


logger = get_logger("instaloader")


def _comment_to_dict(comment: Any, media_url: str) -> dict[str, Any]:
    """Convert an instaloader Comment object to a plain dictionary for JSON serialization."""
    return Comment.from_instaloader_comment(comment, media_url).to_dict()


def _fetch_all_comments(client: Any, post: Any, media_url: str) -> list[dict[str, Any]]:
    """Fetch all comments on a post using instaloader's iterator-based get_comments().

    Instaloader's get_comments() is an iterator that automatically handles pagination.
    We use a simple loop to iterate through all comments with rate limiting.
    Nested comment replies (answers) are also fetched.
    """
    all_comments: list[dict[str, Any]] = []
    page = 0

    logger.info(
        "Starting comment fetch via instaloader | %s",
        format_kv(
            media_url=media_url,
            shortcode=getattr(post, "shortcode", "unknown"),
        ),
    )

    try:
        for comment in post.get_comments():
            page += 1

            comment_dict = _comment_to_dict(comment, media_url)
            all_comments.append(comment_dict)

            if page % 100 == 0:
                logger.info(
                    "Comment fetch progress | %s",
                    format_kv(
                        media_url=media_url,
                        page=page,
                        total_comments=len(all_comments),
                    ),
                )

    except (
        ConnectionException,
        QueryReturnedNotFoundException,
        TooManyRequestsException,
    ) as exc:
        logger.warning(
            "Retryable error during comment fetching; preserving partial | %s",
            format_kv(
                media_url=media_url, page=page, partial_count=len(all_comments), error=str(exc)
            ),
        )
        return all_comments
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:
        logger.error(
            "Unexpected error during comment fetching; preserving partial | %s",
            format_kv(
                media_url=media_url, page=page, partial_count=len(all_comments), error=str(exc)
            ),
        )
        return all_comments

    logger.info(
        "Comment fetch complete | %s",
        format_kv(
            media_url=media_url,
            total_pages=page,
            total_comments=len(all_comments),
        ),
    )

    return all_comments
