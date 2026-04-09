"""Instagram scraping: profile, post, and comment collection via instaloader."""

from __future__ import annotations

import time
from itertools import islice
from typing import TYPE_CHECKING, Any

from instaloader.exceptions import (
    PrivateProfileNotFollowedException,
    ProfileNotExistsException,
    QueryReturnedBadRequestException,
    QueryReturnedForbiddenException,
    TooManyRequestsException,
)

from ig_scraper.client import get_instaloader_client
from ig_scraper.config import COMMENT_PAGE_RETRIES, REQUEST_PAUSE_SECONDS, _sleep
from ig_scraper.logging_utils import format_kv, get_logger
from ig_scraper.media_processing import _process_single_media
from ig_scraper.models import Profile
from ig_scraper.retry import retry_on


if TYPE_CHECKING:
    from pathlib import Path


logger = get_logger("instaloader")


def _take_n(iterator: Any, n: int) -> list[Any]:
    """Take at most n items from an iterator."""
    return list(islice(iterator, n))


def _build_profile_dict(profile: Any) -> dict[str, Any]:
    """Convert an instaloader Profile object to a profile dictionary."""
    logger.debug(
        "Building profile dict | %s",
        format_kv(
            username=getattr(profile, "username", "MISSING"),
            user_id=getattr(profile, "userid", "MISSING"),
            has_biography=bool(getattr(profile, "biography", "")),
            follower_count=getattr(profile, "followers", "MISSING"),
            following_count=getattr(profile, "followees", "MISSING"),
            media_count=getattr(profile, "mediacount", "MISSING"),
            is_private=getattr(profile, "is_private", "MISSING"),
        ),
    )
    return Profile.from_instaloader_profile(profile).to_dict()


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


@retry_on(
    RuntimeError,
    ConnectionError,
    TooManyRequestsException,
    QueryReturnedBadRequestException,
    QueryReturnedForbiddenException,
    max_attempts=COMMENT_PAGE_RETRIES,
    wait_base_seconds=REQUEST_PAUSE_SECONDS,
)
def _fetch_profile(username: str) -> Any:
    """Fetch profile by username with retry."""
    client = get_instaloader_client()
    try:
        from instaloader import Profile

        return Profile.from_username(client.context, username)
    except ProfileNotExistsException as exc:
        raise RuntimeError(f"Profile '{username}' does not exist") from exc
    except PrivateProfileNotFollowedException as exc:
        raise RuntimeError(f"Profile '{username}' is private") from exc


def fetch_profile_posts_and_comments(
    username: str, posts_per_profile: int = 100, account_dir: Path | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Scrape posts and comments for *username* using instaloader and return (profile, posts, comments)."""
    logger.info(
        "Starting account scrape | %s",
        format_kv(username=username, posts_target=posts_per_profile, account_dir=account_dir),
    )
    t0_client = time.perf_counter()
    client = get_instaloader_client()
    elapsed_client = round(time.perf_counter() - t0_client, 3)
    logger.info("Client obtained | %s", format_kv(elapsed_seconds=elapsed_client))
    logger.info("Fetching profile info | %s", format_kv(username=username))
    t0_profile = time.perf_counter()

    from instaloader import Profile

    profile_obj = Profile.from_username(client.context, username)
    elapsed_profile = round(time.perf_counter() - t0_profile, 3)
    logger.info("Profile.from_username returned | %s", format_kv(elapsed_seconds=elapsed_profile))
    logger.info(
        "Profile info fetched | %s",
        format_kv(
            username=username,
            user_id=profile_obj.userid,
            followers=profile_obj.followers,
            following=profile_obj.followees,
            total_profile_posts=profile_obj.mediacount,
        ),
    )
    logger.info(
        "Fetching recent medias | %s", format_kv(username=username, amount=posts_per_profile)
    )
    t0_medias = time.perf_counter()

    # Use iterator-based approach with limit
    posts_iterator = profile_obj.get_posts()
    medias = _take_n(posts_iterator, posts_per_profile)

    elapsed_medias = round(time.perf_counter() - t0_medias, 3)
    logger.info(
        "Profile.get_posts() returned | %s",
        format_kv(media_count=len(medias), elapsed_seconds=elapsed_medias),
    )
    logger.info("Media list fetched | %s", format_kv(username=username, media_count=len(medias)))
    profile = _build_profile_dict(profile_obj)
    posts: list[dict[str, Any]] = []
    comments: list[dict[str, Any]] = []
    posts_root = account_dir / "posts" if account_dir else None
    total_medias = len(medias)

    for index, media in enumerate(medias, start=1):
        post, media_comments, media_files = _process_single_media(
            client=client,
            media=media,
            username=username,
            profile_obj=profile_obj,
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
                shortcode=media.shortcode,
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
