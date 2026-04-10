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


def _media_type_int(media: Any) -> int:
    """Extract numeric media type from an instaloader Post object.

    Standard Post objects expose ``typename`` (GraphImage/GraphVideo/GraphSidecar).
    Posts created via ``from_iphone_struct`` store the raw ``media_type`` in the
    ``iphone_struct`` dict but do not expose it as a property.
    """
    typename_map = {"GraphImage": 1, "GraphVideo": 2, "GraphSidecar": 8}
    typename = getattr(media, "typename", "")
    if typename in typename_map:
        return typename_map[typename]
    iphone = getattr(media, "_node", {}).get("iphone_struct", {})
    return int(iphone.get("media_type", 0) or 0)


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
        if _media_type_int(media) == 8
        else "photo"
        if _media_type_int(media) == 1
        else "clip"
        if getattr(media, "typename", "") == "GraphVideo"
        else "video"
    )
    logger.info(
        "Starting media download via instaloader | %s",
        format_kv(
            shortcode=media.shortcode,
            media_pk=getattr(media, "pk", media.mediaid),
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
            media_pk=getattr(media, "pk", media.mediaid),
            media_type=_media_type_int(media),
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
