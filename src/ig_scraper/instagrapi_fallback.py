"""Instagram scraping: profile, post, and comment collection via instagrapi."""

from __future__ import annotations

import functools
from pathlib import Path  # noqa: TC003
from typing import Any

from ig_scraper.builders import (
    _build_post_dict,
    _build_profile_dict,
    _log_medias_fetch_attempt,
    _log_profile_fetch_attempt,
)
from ig_scraper.errors import MediaDownloadError
from ig_scraper.ig_comments import _fetch_all_comments
from ig_scraper.ig_config import COMMENT_PAGE_RETRIES, _sleep
from ig_scraper.ig_media import _download_media, _media_permalink
from ig_scraper.ig_retry import _retry_with_backoff
from ig_scraper.instagram_client import get_instagram_client
from ig_scraper.logging_utils import format_kv, get_logger


logger = get_logger("instagrapi")


def _process_single_media(
    client: Any,
    media: Any,
    username: str,
    user: Any,
    account_dir: Path | None,
    posts_root: Path | None,
    index: int,
    total_medias: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Process a single media item: download, build post dict, fetch comments.

    Args:
        client: An instagrapi client instance.
        media: The media object to process.
        username: The Instagram username being scraped.
        user: The user object (used for full_name and pk).
        account_dir: The account directory path, if any.
        posts_root: The posts root directory path, if any.
        index: The 1-based index of this media in the list.
        total_medias: Total number of medias being processed.

    Returns:
        A tuple of (post_dict, comments_list, media_files_list).
    """
    media_url = _media_permalink(username, media)
    post_folder = posts_root / f"{index:03d}_{media.code}" if posts_root else None
    media_folder = post_folder / "media" if post_folder else None
    logger.info(
        "Processing media | %s",
        format_kv(
            username=username,
            progress=f"{index}/{total_medias}",
            shortcode=media.code,
            media_pk=media.pk,
            media_type=media.media_type,
            product_type=getattr(media, "product_type", ""),
            likes=media.like_count or 0,
            comments=media.comment_count or 0,
            target_folder=post_folder,
        ),
    )
    try:
        media_files = _download_media(client, media, media_folder) if media_folder else []
    except MediaDownloadError as exc:
        logger.warning(
            "Media download failed; continuing without media | %s",
            format_kv(shortcode=media.code, media_id=media.pk, error=exc),
        )
        media_files = []
    post = _build_post_dict(
        media=media,
        username=username,
        user_full_name=user.full_name,
        user_pk=str(user.pk),
        media_url=media_url,
        media_files=media_files,
        post_folder=post_folder,
        account_dir=account_dir,
    )
    try:
        logger.info(
            "Starting full comment pagination | %s",
            format_kv(shortcode=media.code, media_id=media.id, media_url=media_url),
        )
        media_comments = _fetch_all_comments(client, media.id, media_url)
        logger.info(
            "Comment pagination complete | %s",
            format_kv(shortcode=media.code, total_comments=len(media_comments)),
        )
    except (RuntimeError, ConnectionError, TimeoutError) as exc:
        logger.warning(
            "Comment collection failed for media; preserving post with zero/partial | %s",
            format_kv(shortcode=media.code, media_id=media.id, error=exc),
        )
        media_comments = []
    return post, media_comments, media_files


def fetch_profile_posts_and_comments(
    username: str, posts_per_profile: int = 100, account_dir: Path | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Scrape posts and comments for *username* using instagrapi and return (profile, posts, comments)."""
    logger.info(
        "Starting account scrape | %s",
        format_kv(username=username, posts_target=posts_per_profile, account_dir=account_dir),
    )
    client = get_instagram_client()
    logger.info("Fetching profile info | %s", format_kv(username=username))
    user = _retry_with_backoff(
        lambda: client.user_info_by_username_v1(username),
        retries=COMMENT_PAGE_RETRIES,
        exceptions=(RuntimeError, ConnectionError),
        log_attempt=functools.partial(_log_profile_fetch_attempt, username),
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
    medias = _retry_with_backoff(
        lambda: client.user_medias_v1(user.pk, amount=posts_per_profile),
        retries=COMMENT_PAGE_RETRIES,
        exceptions=(RuntimeError, ConnectionError),
        log_attempt=functools.partial(_log_medias_fetch_attempt, username),
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
