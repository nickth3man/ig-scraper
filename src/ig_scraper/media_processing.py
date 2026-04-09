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


logger = get_logger("instaloader")


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
    """Convert an instaloader Post object to a post dictionary."""
    logger.debug(
        "Building post dict | %s",
        format_kv(
            shortcode=getattr(media, "shortcode", "MISSING"),
            media_pk=getattr(media, "mediaid", "MISSING"),
            has_caption=bool(getattr(media, "caption", "")),
            caption_length=len(getattr(media, "caption", "") or ""),
            media_type=getattr(media, "mediatype", "MISSING"),
            product_type=getattr(media, "product_type", "MISSING"),
            resources_count=len(getattr(media, "resources", [])),
            like_count=getattr(media, "likes", "MISSING"),
            comment_count=getattr(media, "comments", "MISSING"),
            taken_at=str(getattr(media, "date", "MISSING")),
            media_files_count=len(media_files),
            post_folder=str(post_folder) if post_folder else "None",
        ),
    )
    post = Post.from_instaloader_post(media, username, user_full_name, user_pk)
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
    profile_obj: Any,
    account_dir: Path | None,
    posts_root: Path | None,
    index: int,
    total_medias: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Process a single media item: download, build post dict, fetch comments.

    Args:
        client: An instaloader client instance.
        media: The media object to process.
        username: The Instagram username being scraped.
        profile_obj: The profile object (used for full_name and userid).
        account_dir: The account directory path, if any.
        posts_root: The posts root directory path, if any.
        index: The 1-based index of this media in the list.
        total_medias: Total number of medias being processed.

    Returns:
        A tuple of (post_dict, comments_list, media_files_list).
    """
    media_url = _media_permalink(username, media)
    post_folder = posts_root / f"{index:03d}_{media.shortcode}" if posts_root else None
    media_folder = post_folder / "media" if post_folder else None
    logger.info(
        "Processing media | %s",
        format_kv(
            username=username,
            progress=f"{index}/{total_medias}",
            shortcode=media.shortcode,
            media_pk=media.mediaid,
            media_type=media.mediatype,
            product_type=getattr(media, "product_type", ""),
            likes=media.likes or 0,
            comments=media.comments or 0,
            target_folder=post_folder,
        ),
    )
    t0_dl = time.perf_counter()
    try:
        media_files = _download_media(client, media, media_folder) if media_folder else []
        elapsed_dl = round(time.perf_counter() - t0_dl, 3)
        logger.info(
            "Download phase complete | %s",
            format_kv(
                shortcode=media.shortcode, files=len(media_files), elapsed_seconds=elapsed_dl
            ),
        )
    except MediaDownloadError as exc:
        elapsed_dl = round(time.perf_counter() - t0_dl, 3)
        logger.warning(
            "Media download failed; continuing without media | %s",
            format_kv(
                shortcode=media.shortcode,
                media_id=media.mediaid,
                error=exc,
                elapsed_seconds=elapsed_dl,
            ),
        )
        media_files = []
    post = _build_post_dict(
        media=media,
        username=profile_obj.username,
        user_full_name=profile_obj.full_name,
        user_pk=str(profile_obj.userid),
        media_url=media_url,
        media_files=media_files,
        post_folder=post_folder,
        account_dir=account_dir,
    )
    t0_cmt = time.perf_counter()
    try:
        logger.info(
            "Starting full comment pagination | %s",
            format_kv(shortcode=media.shortcode, media_id=media.mediaid, media_url=media_url),
        )
        media_comments = _fetch_all_comments(client, media, media_url)
        elapsed_cmt = round(time.perf_counter() - t0_cmt, 3)
        logger.info(
            "Comment pagination complete | %s",
            format_kv(
                shortcode=media.shortcode,
                total_comments=len(media_comments),
                elapsed_seconds=elapsed_cmt,
            ),
        )
    except (RuntimeError, ConnectionError, TimeoutError) as exc:
        elapsed_cmt = round(time.perf_counter() - t0_cmt, 3)
        logger.warning(
            "Comment collection failed for media; preserving post with zero/partial | %s",
            format_kv(
                shortcode=media.shortcode,
                media_id=media.mediaid,
                error=exc,
                elapsed_seconds=elapsed_cmt,
            ),
        )
        media_comments = []
    return post, media_comments, media_files
