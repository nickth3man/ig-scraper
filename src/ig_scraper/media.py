"""Media download and resource conversion for Instagram scraping."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ig_scraper.config import MEDIA_DOWNLOAD_RETRIES, REQUEST_PAUSE_SECONDS
from ig_scraper.exceptions import MediaDownloadError
from ig_scraper.exceptions import RetryExhaustedError as _RetryExhaustedError
from ig_scraper.logging_utils import format_kv, get_logger
from ig_scraper.retry import retry_on


logger = get_logger("instagrapi")


def _media_permalink(username: str, media: Any) -> str:
    """Construct the Instagram permalink URL for a media object."""
    kind = "reel" if getattr(media, "product_type", "") == "clips" else "p"
    return f"https://www.instagram.com/{kind}/{media.code}/"


def _resource_to_dict(resource: Any) -> dict[str, Any]:
    """Convert an instagrapi Resource object to a plain dictionary."""
    return {
        "pk": str(getattr(resource, "pk", "") or ""),
        "media_type": int(getattr(resource, "media_type", 0) or 0),
        "thumbnail_url": str(getattr(resource, "thumbnail_url", "") or ""),
        "video_url": str(getattr(resource, "video_url", "") or ""),
    }


@retry_on(
    OSError,
    RuntimeError,
    max_attempts=MEDIA_DOWNLOAD_RETRIES,
    wait_base_seconds=REQUEST_PAUSE_SECONDS,
)
def _perform_media_download(client: Any, media: Any, target_dir: Path) -> list[str]:
    """Perform the actual media download with retry decorator.

    Handles photos, videos, albums (media_type 8), and clips (product_type 'clips').
    Raises OSError or RuntimeError on failure for retry.
    """
    download_kind = (
        "album"
        if media.media_type == 8
        else "photo"
        if media.media_type == 1
        else "clip"
        if getattr(media, "product_type", "") == "clips"
        else "video"
    )
    logger.info(
        "Starting media download via instagrapi | %s",
        format_kv(
            shortcode=media.code,
            media_pk=media.pk,
            download_kind=download_kind,
            target_dir=target_dir,
        ),
    )
    t0 = time.perf_counter()
    if media.media_type == 8:
        paths = client.album_download(media.pk, folder=target_dir)
    elif media.media_type == 1:
        paths = [client.photo_download(media.pk, folder=target_dir)]
    elif getattr(media, "product_type", "") == "clips":
        paths = [Path(client.clip_download(media.pk, folder=target_dir))]
    else:
        paths = [client.video_download(media.pk, folder=target_dir)]
    elapsed = round(time.perf_counter() - t0, 3)
    filenames = [Path(path).name for path in paths if path]
    file_sizes = {}
    for path in paths:
        if path:
            p = Path(path) if not isinstance(path, Path) else path
            if p.exists():
                file_sizes[p.name] = f"{p.stat().st_size / 1024:.1f}KB"
    logger.info(
        "Instagrapi download call returned | %s",
        format_kv(
            shortcode=media.code,
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

    Handles photos, videos, albums (media_type 8), and clips (product_type 'clips').
    Retries up to MEDIA_DOWNLOAD_RETRIES times with exponential backoff on failure.

    Raises:
        MediaDownloadError: If all download attempts fail after exhausting retries.
    """
    logger.info(
        "Creating media target directory | %s",
        format_kv(shortcode=media.code, target_dir=target_dir),
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Downloading media assets | %s",
        format_kv(
            shortcode=media.code,
            media_pk=media.pk,
            media_type=media.media_type,
            product_type=getattr(media, "product_type", ""),
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
                shortcode=media.code,
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
            format_kv(shortcode=media.code, elapsed_seconds=total_elapsed, error=exc),
        )
        raise MediaDownloadError(f"Media download failed for {media.code}: {exc}") from exc
