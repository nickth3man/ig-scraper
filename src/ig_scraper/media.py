"""Media download and resource conversion for Instagram scraping via instaloader."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from pathlib import Path

from instaloader.exceptions import ConnectionException, TooManyRequestsException

from ig_scraper.config import MEDIA_DOWNLOAD_RETRIES, REQUEST_PAUSE_SECONDS
from ig_scraper.exceptions import MediaDownloadError
from ig_scraper.exceptions import RetryExhaustedError as _RetryExhaustedError
from ig_scraper.logging_utils import format_kv, get_logger
from ig_scraper.retry import retry_on


logger = get_logger("instaloader")


def _media_permalink(username: str, media: Any) -> str:
    """Construct the Instagram permalink URL for a media object."""
    return f"https://www.instagram.com/p/{media.shortcode}/"


def _resource_to_dict(resource: Any) -> dict[str, Any]:
    """Convert an instaloader Resource object to a plain dictionary."""
    return {
        "pk": str(getattr(resource, "pk", "") or ""),
        "media_type": int(getattr(resource, "media_type", 0) or 0),
        "thumbnail_url": str(getattr(resource, "thumbnail_url", "") or ""),
        "video_url": str(getattr(resource, "video_url", "") or ""),
    }


@retry_on(
    OSError,
    RuntimeError,
    ConnectionException,
    TooManyRequestsException,
    max_attempts=MEDIA_DOWNLOAD_RETRIES,
    wait_base_seconds=REQUEST_PAUSE_SECONDS,
)
def _perform_media_download(client: Any, media: Any, target_dir: Path) -> list[str]:
    """Perform the actual media download with retry decorator.

    Handles photos, videos, albums, and clips using instaloader's download_post().
    Raises OSError or RuntimeError on failure for retry.
    """
    download_kind = (
        "album"
        if media.media_type == 8
        else "photo"
        if media.media_type == 1
        else "clip"
        if getattr(media, "typename", "") == "GraphVideo"
        else "video"
    )
    logger.info(
        "Starting media download via instaloader | %s",
        format_kv(
            shortcode=media.shortcode,
            media_pk=media.pk,
            download_kind=download_kind,
            target_dir=target_dir,
        ),
    )
    t0 = time.perf_counter()

    # instaloader's download_post handles all media types automatically
    target_dir.mkdir(parents=True, exist_ok=True)
    client.download_post(media, target=target_dir)

    # Get list of downloaded files from the target directory
    # instaloader creates files with pattern: shortcode_timestamp.jpg
    filenames = [f.name for f in target_dir.iterdir() if f.is_file()]

    # Validate downloads
    if not filenames:
        raise OSError(f"No files downloaded to {target_dir}")

    # Check for zero-byte files which indicate failed downloads
    for name in filenames:
        p = target_dir / name
        if p.stat().st_size == 0:
            raise OSError(f"Zero-byte file detected: {p}")

    elapsed = round(time.perf_counter() - t0, 3)
    file_sizes = {}
    for name in filenames:
        p = target_dir / name
        if p.exists():
            file_sizes[name] = f"{p.stat().st_size / 1024:.1f}KB"
    logger.info(
        "Instaloader download_post returned | %s",
        format_kv(
            shortcode=media.shortcode,
            download_kind=download_kind,
            file_count=len(filenames),
            filenames=filenames,
            file_sizes=file_sizes,
            elapsed_seconds=elapsed,
        ),
    )
    return filenames


def _download_media(client: Any, media: Any, target_dir: Path) -> list[str]:
    """Download media files from Instagram to the target directory.

    Handles photos, videos, albums, and clips using instaloader.
    Retries up to MEDIA_DOWNLOAD_RETRIES times with exponential backoff on failure.

    Raises:
        MediaDownloadError: If all download attempts fail after exhausting retries.
    """
    logger.info(
        "Creating media target directory | %s",
        format_kv(shortcode=media.shortcode, target_dir=target_dir),
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Downloading media assets | %s",
        format_kv(
            shortcode=media.shortcode,
            media_pk=media.pk,
            media_type=media.media_type,
            typename=getattr(media, "typename", ""),
            max_attempts=MEDIA_DOWNLOAD_RETRIES,
            target_dir=target_dir,
        ),
    )

    t0 = time.perf_counter()
    try:
        filenames = _perform_media_download(client, media, target_dir)
        total_elapsed = round(time.perf_counter() - t0, 3)
        logger.info(
            "Media download complete | %s",
            format_kv(
                shortcode=media.shortcode,
                file_count=len(filenames),
                files=filenames,
                total_elapsed_seconds=total_elapsed,
            ),
        )
        return filenames
    except _RetryExhaustedError as exc:
        total_elapsed = round(time.perf_counter() - t0, 3)
        logger.warning(
            "Media download exhausted retries | %s",
            format_kv(shortcode=media.shortcode, elapsed_seconds=total_elapsed, error=exc),
        )
        raise MediaDownloadError(f"Media download failed for {media.shortcode}: {exc}") from exc
