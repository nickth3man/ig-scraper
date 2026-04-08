"""Instagram scraping: profile, post, and comment collection via instagrapi."""

from __future__ import annotations

import functools
from pathlib import Path  # noqa: TC003
from typing import Any

from ig_scraper.ig_comments import _fetch_all_comments
from ig_scraper.ig_config import COMMENT_PAGE_RETRIES, _sleep
from ig_scraper.ig_media import _download_media, _media_permalink, _resource_to_dict
from ig_scraper.ig_retry import _retry_with_backoff
from ig_scraper.instagram_client import get_instagram_client
from ig_scraper.logging_utils import format_kv, get_logger


logger = get_logger("instagrapi")


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

    profile = {
        "id": str(user.pk),
        "username": user.username,
        "fullName": user.full_name,
        "biography": user.biography,
        "followersCount": user.follower_count,
        "followsCount": user.following_count,
        "postsCount": user.media_count,
        "verified": user.is_verified,
        "isBusinessAccount": user.is_business,
        "profilePicUrl": str(user.profile_pic_url or ""),
        "externalUrl": str(user.external_url or ""),
    }

    posts: list[dict[str, Any]] = []
    comments: list[dict[str, Any]] = []
    posts_root = account_dir / "posts" if account_dir else None
    total_medias = len(medias)
    for index, media in enumerate(medias, start=1):
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
        media_files = _download_media(client, media, media_folder) if media_folder else []
        post = {
            "id": str(media.pk),
            "pk": str(media.pk),
            "shortCode": media.code,
            "url": media_url,
            "type": str(media.product_type or media.media_type),
            "caption": media.caption_text or "",
            "comment_count": media.comment_count or 0,
            "like_count": media.like_count or 0,
            "taken_at": media.taken_at.isoformat() if media.taken_at else "",
            "ownerUsername": username,
            "ownerFullName": user.full_name,
            "ownerId": str(user.pk),
            "video_url": str(getattr(media, "video_url", "") or ""),
            "thumbnail_url": str(getattr(media, "thumbnail_url", "") or ""),
            "is_video": media.media_type == 2,
            "mentions": [],
            "hashtags": [],
            "resources": [_resource_to_dict(r) for r in getattr(media, "resources", [])],
            "media_files": media_files,
            "post_folder": str(post_folder.relative_to(account_dir))
            if post_folder and account_dir
            else "",
            "from_url": f"https://www.instagram.com/{username}/",
        }
        posts.append(post)
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
