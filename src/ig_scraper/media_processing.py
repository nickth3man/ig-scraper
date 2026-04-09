"""Media processing for a single Instagram post."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from ig_scraper.comments import _fetch_all_comments
from ig_scraper.exceptions import MediaDownloadError
from ig_scraper.logging_utils import format_kv, get_logger
from ig_scraper.media import _download_media, _media_permalink
from ig_scraper.models import Post


if TYPE_CHECKING:
    from pathlib import Path


logger = get_logger("instagrapi")


def _build_post_dict(
    media: Any,
    username: str,
    user_full_name: str,
    user_pk: str,
    media_url: str,
    media_files: list[str],
    post_folder: Path | None,
    account_dir: Path | None,
) -> dict[str, Any]:
    """Convert an instagrapi Media object to a post dictionary."""
    logger.debug(
        "Building post dict | %s",
        format_kv(
            shortcode=getattr(media, "code", "MISSING"),
            media_pk=getattr(media, "pk", "MISSING"),
            has_caption=bool(getattr(media, "caption_text", "")),
            caption_length=len(getattr(media, "caption_text", "") or ""),
            media_type=getattr(media, "media_type", "MISSING"),
            product_type=getattr(media, "product_type", "MISSING"),
            resources_count=len(getattr(media, "resources", [])),
            like_count=getattr(media, "like_count", "MISSING"),
            comment_count=getattr(media, "comment_count", "MISSING"),
            taken_at=str(getattr(media, "taken_at", "MISSING")),
            media_files_count=len(media_files),
            post_folder=str(post_folder) if post_folder else "None",
        ),
    )
    post = Post.from_instagrapi_media(media, username, user_full_name, user_pk)
    d = post.to_dict()
    # Overlay runtime-only fields not in the model's to_dict()
    d["media_files"] = media_files
    d["post_folder"] = (
        str(post_folder.relative_to(account_dir)) if post_folder and account_dir else ""
    )
    d["from_url"] = f"https://www.instagram.com/{username}/"
    return d


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
    t0_dl = time.perf_counter()
    try:
        media_files = _download_media(client, media, media_folder) if media_folder else []
        elapsed_dl = round(time.perf_counter() - t0_dl, 3)
        logger.info(
            "Download phase complete | %s",
            format_kv(shortcode=media.code, files=len(media_files), elapsed_seconds=elapsed_dl),
        )
    except MediaDownloadError as exc:
        elapsed_dl = round(time.perf_counter() - t0_dl, 3)
        logger.warning(
            "Media download failed; continuing without media | %s",
            format_kv(
                shortcode=media.code, media_id=media.pk, error=exc, elapsed_seconds=elapsed_dl
            ),
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
    t0_cmt = time.perf_counter()
    try:
        logger.info(
            "Starting full comment pagination | %s",
            format_kv(shortcode=media.code, media_id=media.id, media_url=media_url),
        )
        media_comments = _fetch_all_comments(client, media.id, media_url)
        elapsed_cmt = round(time.perf_counter() - t0_cmt, 3)
        logger.info(
            "Comment pagination complete | %s",
            format_kv(
                shortcode=media.code,
                total_comments=len(media_comments),
                elapsed_seconds=elapsed_cmt,
            ),
        )
    except (RuntimeError, ConnectionError, TimeoutError) as exc:
        elapsed_cmt = round(time.perf_counter() - t0_cmt, 3)
        logger.warning(
            "Comment collection failed for media; preserving post with zero/partial | %s",
            format_kv(
                shortcode=media.code, media_id=media.id, error=exc, elapsed_seconds=elapsed_cmt
            ),
        )
        media_comments = []
    return post, media_comments, media_files
