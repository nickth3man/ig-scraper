"""Instagram scraping: profile, post, and comment collection via instagrapi."""

from __future__ import annotations

import functools
import time
from typing import TYPE_CHECKING, Any

from ig_scraper.client import get_instagram_client
from ig_scraper.config import COMMENT_PAGE_RETRIES, _sleep
from ig_scraper.logging_utils import format_kv, get_logger
from ig_scraper.media_processing import _process_single_media
from ig_scraper.models import Profile
from ig_scraper.retry import _retry_with_backoff


if TYPE_CHECKING:
    from pathlib import Path


logger = get_logger("instagrapi")


def _build_profile_dict(user: Any) -> dict[str, Any]:
    """Convert an instagrapi User object to a profile dictionary."""
    logger.debug(
        "Building profile dict | %s",
        format_kv(
            username=getattr(user, "username", "MISSING"),
            pk=getattr(user, "pk", "MISSING"),
            has_biography=bool(getattr(user, "biography", "")),
            follower_count=getattr(user, "follower_count", "MISSING"),
            following_count=getattr(user, "following_count", "MISSING"),
            media_count=getattr(user, "media_count", "MISSING"),
            is_private=getattr(user, "is_private", "MISSING"),
        ),
    )
    return Profile.from_instagrapi_user(user).to_dict()


def _log_profile_fetch_attempt(
    username: str, attempt: int, exc: Exception, wait_seconds: float
) -> None:
    """Log a failed profile fetch attempt."""
    logger.warning(
        "Profile fetch failed | %s",
        format_kv(
            username=username,
            attempt=f"{attempt}/{COMMENT_PAGE_RETRIES}",
            error=exc,
            retry_wait_seconds=wait_seconds,
        ),
    )


def _log_medias_fetch_attempt(
    username: str, attempt: int, exc: Exception, wait_seconds: float
) -> None:
    """Log a failed medias fetch attempt."""
    logger.warning(
        "Medias fetch failed | %s",
        format_kv(
            username=username,
            attempt=f"{attempt}/{COMMENT_PAGE_RETRIES}",
            error=exc,
            retry_wait_seconds=wait_seconds,
        ),
    )






def fetch_profile_posts_and_comments(
    username: str, posts_per_profile: int = 100, account_dir: Path | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Scrape posts and comments for *username* using instagrapi and return (profile, posts, comments)."""
    logger.info(
        "Starting account scrape | %s",
        format_kv(username=username, posts_target=posts_per_profile, account_dir=account_dir),
    )
    t0_client = time.perf_counter()
    client = get_instagram_client()
    elapsed_client = round(time.perf_counter() - t0_client, 3)
    logger.info("Client obtained | %s", format_kv(elapsed_seconds=elapsed_client))
    logger.info("Fetching profile info | %s", format_kv(username=username))
    t0_profile = time.perf_counter()
    user = _retry_with_backoff(
        lambda: client.user_info_by_username_v1(username),
        retries=COMMENT_PAGE_RETRIES,
        exceptions=(RuntimeError, ConnectionError),
        log_attempt=functools.partial(_log_profile_fetch_attempt, username),
    )
    elapsed_profile = round(time.perf_counter() - t0_profile, 3)
    logger.info(
        "user_info_by_username_v1 returned | %s", format_kv(elapsed_seconds=elapsed_profile)
    )
    logger.info(
        "Profile info fetched | %s",
        format_kv(
            username=username,
            user_pk=user.pk,
            followers=user.follower_count,
            following=user.following_count,
            total_profile_posts=user.media_count,
        ),
    )
    logger.info(
        "Fetching recent medias | %s", format_kv(username=username, amount=posts_per_profile)
    )
    t0_medias = time.perf_counter()
    medias = _retry_with_backoff(
        lambda: client.user_medias_v1(user.pk, amount=posts_per_profile),
        retries=COMMENT_PAGE_RETRIES,
        exceptions=(RuntimeError, ConnectionError),
        log_attempt=functools.partial(_log_medias_fetch_attempt, username),
    )
    elapsed_medias = round(time.perf_counter() - t0_medias, 3)
    logger.info(
        "user_medias_v1 returned | %s",
        format_kv(media_count=len(medias), elapsed_seconds=elapsed_medias),
    )
    logger.info("Media list fetched | %s", format_kv(username=username, media_count=len(medias)))
    profile = _build_profile_dict(user)
    posts: list[dict[str, Any]] = []
    comments: list[dict[str, Any]] = []
    posts_root = account_dir / "posts" if account_dir else None
    total_medias = len(medias)
    for index, media in enumerate(medias, start=1):
        post, media_comments, media_files = _process_single_media(
            client=client,
            media=media,
            username=username,
            user=user,
            account_dir=account_dir,
            posts_root=posts_root,
            index=index,
            total_medias=total_medias,
        )
        posts.append(post)
        comments.extend(media_comments)
        logger.info(
            "Media processing complete | %s",
            format_kv(
                username=username,
                progress=f"{index}/{total_medias}",
                shortcode=media.code,
                downloaded_files=len(media_files),
                cumulative_posts=len(posts),
                cumulative_comments=len(comments),
            ),
        )
        _sleep("between media iterations")
    logger.info(
        "Account scrape complete | %s",
        format_kv(username=username, posts=len(posts), comments=len(comments)),
    )
    return profile, posts, comments
