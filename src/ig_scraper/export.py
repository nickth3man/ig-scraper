"""Manifest and profile export for scraped Instagram accounts.

Provides functions to build a versioned manifest dict, write it to disk as
``manifest.json``, and write a cleaned profile dict as ``profile.json``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from pathlib import Path

from ig_scraper.analysis_io import write_json
from ig_scraper.logging_utils import format_kv, get_logger


logger = get_logger("export")

#: Metadata for each collection domain.
_COLLECTION_META: dict[str, dict[str, Any]] = {
    "posts": {"auth_required": False, "chunked": False},
    "stories": {"auth_required": True, "chunked": False},
    "highlights": {"auth_required": True, "chunked": False},
    "tagged": {"auth_required": False, "chunked": False},
    "saved": {"auth_required": True, "chunked": True},
    "followers": {"auth_required": True, "chunked": True},
    "followees": {"auth_required": True, "chunked": True},
}


def _build_collection_entry(
    domain: str,
    items_or_summary: list[dict[str, Any]] | dict[str, Any],
) -> dict[str, Any]:
    """Build a single collection entry dict with metadata.

    Args:
        domain: Collection domain name (e.g. ``"saved"``, ``"followers"``).
        items_or_summary: Either a list of item dicts (legacy path) or a
            precomputed summary dict with keys: ``count`` (required),
            ``chunks`` (optional), ``auth_required`` (optional),
            ``chunked`` (optional). When a summary dict is passed,
            ``items`` is always emitted as an empty list and ``count`` is
            taken from the summary directly rather than inferred via
            ``len(items)``.
    """
    meta = _COLLECTION_META.get(domain, {"auth_required": False, "chunked": False})

    if isinstance(items_or_summary, dict):
        # Summary-dict path (chunked collections): use explicit metadata.
        summary = items_or_summary
        return {
            "domain": domain,
            "count": summary["count"],
            "items": [],
            "auth_required": summary.get("auth_required", meta["auth_required"]),
            "chunked": summary.get("chunked", meta["chunked"]),
            **({"chunks": summary["chunks"]} if "chunks" in summary else {}),
        }

    # Legacy list path: derive count from items and use _COLLECTION_META defaults.
    items = items_or_summary
    return {
        "domain": domain,
        "count": len(items),
        "items": items,
        "auth_required": meta["auth_required"],
        "chunked": meta["chunked"],
    }


def build_manifest(
    handle: str,
    post_items: list[dict[str, Any]],
    profile_file: str = "profile.json",
    method: str = "instaloader",
    collections: dict[str, Any] | None = None,
    skipped_reasons: list[str] | None = None,
) -> dict[str, Any]:
    """Build a versioned manifest dict describing scraped data for *handle*.

    Args:
        handle: Normalised Instagram handle (no leading ``@``).
        post_items: List of post dicts, each containing at least ``index``,
            ``shortcode``, ``folder``, ``media_count``, and ``comment_count``.
        profile_file: Filename of the accompanying profile JSON.
        method: Scraping method identifier.
        collections: Optional dict mapping domain names to lists of item dicts.
            Supported domains: posts, stories, highlights, tagged, saved,
            followers, followees. Each domain is stored with auth_required
            and chunked metadata.
        skipped_reasons: Optional list of human-readable reasons why certain
            items were skipped during scraping (e.g. rate-limit, private post).

    Returns:
        A manifest dict with ``version``, ``handle``, ``scraped_at``,
        ``method``, ``collections``, ``skipped_reasons``, and ``profile_file``
        keys.
    """
    sorted_posts = sorted(post_items, key=lambda p: p.get("index", 0))
    all_collections: list[dict[str, Any]] = [_build_collection_entry("posts", sorted_posts)]

    if collections:
        for domain, items in collections.items():
            if domain in _COLLECTION_META:
                all_collections.append(_build_collection_entry(domain, items))

    return {
        "version": 1,
        "handle": handle,
        "scraped_at": datetime.now(UTC).isoformat(),
        "method": method,
        "collections": all_collections,
        "skipped_reasons": list(skipped_reasons) if skipped_reasons else [],
        "profile_file": profile_file,
    }


def write_manifest(account_dir: Path, manifest: dict[str, Any]) -> Path:
    """Write *manifest* as ``manifest.json`` under *account_dir*.

    Args:
        account_dir: Directory that will contain the manifest file.
        manifest: Manifest dict produced by :func:`build_manifest`.

    Returns:
        The ``Path`` of the written file.
    """
    path = account_dir / "manifest.json"
    write_json(path, manifest)
    logger.info("Manifest written | %s", format_kv(path=path))
    return path


def write_profile(account_dir: Path, profile: dict[str, Any]) -> Path:
    """Write a cleaned *profile* dict as ``profile.json`` under *account_dir*.

    Keys prefixed with an underscore (``_``) are stripped before writing so
    that internal bookkeeping fields are not persisted.

    Args:
        account_dir: Directory that will contain the profile file.
        profile: Raw profile dict that may contain underscore-prefixed keys.

    Returns:
        The ``Path`` of the written file.
    """
    cleaned = {k: v for k, v in profile.items() if not k.startswith("_")}
    path = account_dir / "profile.json"
    write_json(path, cleaned)
    logger.info("Profile written | %s", format_kv(path=path, keys=len(cleaned)))
    return path
