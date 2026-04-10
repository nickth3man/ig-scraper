"""Highlight collection for Instagram stories highlights via instaloader."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ig_scraper.config import _sleep
from ig_scraper.exceptions import IgScraperError, classify_exception
from ig_scraper.logging_utils import format_kv, get_logger
from ig_scraper.media import _download_media


if TYPE_CHECKING:
    from pathlib import Path


logger = get_logger("instaloader")


@dataclass
class HighlightCollectionResult:
    """Result of highlight collection: items, skipped flag, skip reason, and file path."""

    items: list[dict[str, Any]] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None
    file_path: str | None = None


def _highlight_to_dict(
    highlight: Any,
    items_file: str,
    item_count: int,
) -> dict[str, Any]:
    return {
        "id": str(getattr(highlight, "id", "")),
        "title": getattr(highlight, "title", "") or "",
        "cover_url": getattr(highlight, "cover_url", "") or "",
        "cover_cropped_url": getattr(highlight, "cover_cropped_url", "") or "",
        "item_count": item_count,
        "items_file": items_file,
    }


def _story_item_to_dict(item: Any, highlight_id: str) -> dict[str, Any]:
    return {
        "id": str(getattr(item, "mediaid", "")) or "",
        "pk": str(getattr(item, "pk", "")) or "",
        "shortcode": getattr(item, "shortcode", "") or "",
        "typename": getattr(item, "typename", "") or "",
        "code": getattr(item, "code", "") or "",
        "url": f"https://www.instagram.com/stories/{highlight_id}/",
        "taken_at": str(getattr(item, "date", "")) or "",
        "likes": getattr(item, "likes", 0) or 0,
    }


def collect_highlights(
    client: Any,
    profile: Any,
    account_dir: Path | None,
) -> HighlightCollectionResult:
    """Collect highlights for a profile; returns result with items or skip_reason."""
    if not account_dir:
        return HighlightCollectionResult(skipped=True, skip_reason="no account_dir")

    highlights_root = account_dir / "highlights"
    highlights_list_file = highlights_root / "highlights.json"

    logger.info(
        "Starting highlights collection | %s",
        format_kv(username=getattr(profile, "username", "unknown")),
    )

    items: list[dict[str, Any]] = []

    try:
        for highlight in client.get_highlights(profile):
            highlight_id = str(getattr(highlight, "id", ""))
            highlight_dir = highlights_root / highlight_id
            items_file_rel = f"{highlight_id}/items.json"

            logger.debug(
                "Processing highlight | %s",
                format_kv(
                    highlight_id=highlight_id,
                    title=getattr(highlight, "title", ""),
                ),
            )

            highlight_items: list[dict[str, Any]] = []
            media_files: list[str] = []

            try:
                for item in highlight.get_items():
                    item_dict = _story_item_to_dict(item, highlight_id)
                    highlight_items.append(item_dict)

                    if highlight_dir:
                        media_dir = highlight_dir / "media"
                        try:
                            downloaded = _download_media(client, item, media_dir)
                            media_files.extend(downloaded)
                        except Exception as exc:  # pragma: no cover
                            logger.warning(
                                "Highlight media download failed; continuing | %s",
                                format_kv(
                                    highlight_id=highlight_id,
                                    item_id=getattr(item, "mediaid", ""),
                                    error=exc,
                                ),
                            )
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "Highlight items fetch failed; preserving partial | %s",
                    format_kv(highlight_id=highlight_id, error=exc),
                )

            highlight_dict = _highlight_to_dict(
                highlight=highlight,
                items_file=items_file_rel,
                item_count=len(highlight_items),
            )
            items.append(highlight_dict)

            highlight_dir.mkdir(parents=True, exist_ok=True)
            items_file = highlight_dir / "items.json"

            with items_file.open("w", encoding="utf-8") as fh:
                json.dump(highlight_items, fh, indent=2, ensure_ascii=False)

            logger.info(
                "Highlight processed | %s",
                format_kv(
                    highlight_id=highlight_id,
                    title=getattr(highlight, "title", ""),
                    item_count=len(highlight_items),
                ),
            )

            _sleep("between highlight items")

    except IgScraperError as exc:
        logger.warning(
            "Highlights collection failed (auth/profile error); skipping | %s",
            format_kv(username=getattr(profile, "username", ""), error=exc),
        )
        return HighlightCollectionResult(
            skipped=True,
            skip_reason=f"IgScraperError: {exc}",
        )
    except Exception as exc:
        if classify_exception(exc):
            logger.warning(
                "Highlights collection failed (retryable); skipping | %s",
                format_kv(username=getattr(profile, "username", ""), error=exc),
            )
            return HighlightCollectionResult(
                skipped=True,
                skip_reason=f"Retryable error: {exc}",
            )
        logger.warning(
            "Highlights collection failed (fatal); skipping | %s",
            format_kv(username=getattr(profile, "username", ""), error=exc),
        )
        return HighlightCollectionResult(
            skipped=True,
            skip_reason=f"Fatal error: {exc}",
        )

    highlights_root.mkdir(parents=True, exist_ok=True)

    output: dict[str, Any] = {"highlights": items}
    with highlights_list_file.open("w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)

    logger.info(
        "Highlights collection complete | %s",
        format_kv(
            username=getattr(profile, "username", ""),
            total_highlights=len(items),
        ),
    )

    return HighlightCollectionResult(
        items=items,
        skipped=False,
        skip_reason=None,
        file_path=str(highlights_list_file),
    )
