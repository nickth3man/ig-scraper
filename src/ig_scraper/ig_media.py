"""Media download and resource conversion for Instagram scraping."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ig_scraper.errors import MediaDownloadError
from ig_scraper.ig_config import MEDIA_DOWNLOAD_RETRIES, REQUEST_PAUSE_SECONDS
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


def _download_media(client: Any, media: Any, target_dir: Path) -> list[str]:
    """Download media files from Instagram to the target directory.

    Handles photos, videos, albums (media_type 8), and clips (product_type 'clips').
    Retries up to MEDIA_DOWNLOAD_RETRIES times with exponential backoff on failure.

    Raises:
        MediaDownloadError: If all download attempts fail after exhausting retries.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(1, MEDIA_DOWNLOAD_RETRIES + 1):
        try:
            logger.info(
                "Downloading media assets | %s",
                format_kv(
                    shortcode=media.code,
                    media_pk=media.pk,
                    media_type=media.media_type,
                    product_type=getattr(media, "product_type", ""),
                    attempt=f"{attempt}/{MEDIA_DOWNLOAD_RETRIES}",
                    target_dir=target_dir,
                ),
            )
            if media.media_type == 8:
                paths = client.album_download(media.pk, folder=target_dir)
            elif media.media_type == 1:
                paths = [client.photo_download(media.pk, folder=target_dir)]
            elif getattr(media, "product_type", "") == "clips":
                paths = [Path(client.clip_download(media.pk, folder=target_dir))]
            else:
                paths = [client.video_download(media.pk, folder=target_dir)]
            filenames = [Path(path).name for path in paths if path]
            logger.info(
                "Media download complete | %s",
                format_kv(shortcode=media.code, file_count=len(filenames), files=filenames),
            )
            return filenames
        except (OSError, RuntimeError) as exc:
            last_error = exc
            wait_seconds = round(REQUEST_PAUSE_SECONDS * (2**attempt), 2)
            logger.warning(
                "Media download attempt failed | %s",
                format_kv(
                    shortcode=media.code,
                    attempt=f"{attempt}/{MEDIA_DOWNLOAD_RETRIES}",
                    error=exc,
                    retry_wait_seconds=wait_seconds,
                ),
            )
            if attempt == MEDIA_DOWNLOAD_RETRIES:
                break
            time.sleep(wait_seconds)
    raise MediaDownloadError(
        f"Media download failed for {media.code}: {last_error}"
    ) from last_error
