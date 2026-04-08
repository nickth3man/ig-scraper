"""Media download and resource conversion for Instagram scraping."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ig_scraper.errors import MediaDownloadError
from ig_scraper.ig_config import MEDIA_DOWNLOAD_RETRIES, REQUEST_PAUSE_SECONDS
from ig_scraper.ig_retry import _RetryExhaustedError, retry_on
from ig_scraper.logging_utils import format_kv, get_logger


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
    if media.media_type == 8:
        paths = client.album_download(media.pk, folder=target_dir)
    elif media.media_type == 1:
        paths = [client.photo_download(media.pk, folder=target_dir)]
    elif getattr(media, "product_type", "") == "clips":
        paths = [Path(client.clip_download(media.pk, folder=target_dir))]
    else:
        paths = [client.video_download(media.pk, folder=target_dir)]

    return [Path(path).name for path in paths if path]


def _download_media(client: Any, media: Any, target_dir: Path) -> list[str]:
    """Download media files from Instagram to the target directory.

    Handles photos, videos, albums (media_type 8), and clips (product_type 'clips').
    Retries up to MEDIA_DOWNLOAD_RETRIES times with exponential backoff on failure.

    Raises:
        MediaDownloadError: If all download attempts fail after exhausting retries.
    """
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

    try:
        filenames = _perform_media_download(client, media, target_dir)
        logger.info(
            "Media download complete | %s",
            format_kv(shortcode=media.code, file_count=len(filenames), files=filenames),
        )
        return filenames
    except _RetryExhaustedError as exc:
        raise MediaDownloadError(f"Media download failed for {media.code}: {exc}") from exc
