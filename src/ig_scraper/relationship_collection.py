"""Relationship collection (followers/followees) for Instagram via Instaloader.

Requires authentication — ``Profile.get_followers()`` and ``Profile.get_followees()``
require a logged-in session. This module collects relationship data with
progressive chunking to handle large follower/following lists efficiently.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from ig_scraper.config import _sleep
from ig_scraper.logging_utils import format_kv, get_logger
from ig_scraper.relationship_io import (
    FOLLOW_CHUNK_SIZE,
    _profile_to_dict,
    _write_chunk,
)
from ig_scraper.relationship_result import (
    ChunkInfo,
    RelationshipCollectionResult,
)


if TYPE_CHECKING:
    from pathlib import Path


logger = get_logger("relationships")


def _check_auth(profile: Any) -> bool:
    is_logged_in = getattr(profile, "context", None) and getattr(
        profile.context, "is_logged_in", False
    )
    if not is_logged_in:
        logger.warning(
            "Not logged in; relationship data may be unavailable or incomplete | %s",
            format_kv(username=getattr(profile, "username", "unknown")),
        )
    return bool(is_logged_in)


def _make_relative_path(chunk_path: Path, account_dir: Path) -> str:
    """Return chunk path relative to account_dir as a forward-slash string."""
    return chunk_path.relative_to(account_dir).as_posix()


def _collect_relationship(
    profile: Any,
    account_dir: Path | None,
    chunk_size: int,
    iterator_name: str,
    chunk_prefix: str,
    sleep_reason: str,
) -> RelationshipCollectionResult:
    handle = getattr(profile, "username", "") or "unknown"

    if not account_dir:
        logger.info("No account_dir; skipping %s collection", iterator_name)
        return RelationshipCollectionResult(
            handle=handle,
            skipped=True,
            skipped_reason="no account directory",
        )

    _check_auth(profile)

    logger.info(
        "Starting %s collection | %s",
        iterator_name,
        format_kv(username=handle, chunk_size=chunk_size),
    )

    t0 = time.perf_counter()
    rel_root = account_dir / "relationships"
    rel_root.mkdir(parents=True, exist_ok=True)

    iterator_method = getattr(profile, iterator_name)
    current_chunk: list[dict[str, Any]] = []
    chunk_number = 1
    count = 0
    chunks: list[ChunkInfo] = []

    try:
        for item in iterator_method():
            current_chunk.append(_profile_to_dict(item))
            count += 1
            if len(current_chunk) >= chunk_size:
                chunk_path = rel_root / f"{chunk_prefix}{chunk_number:04d}.json"
                byte_count = _write_chunk(chunk_path, current_chunk)
                chunks.append(
                    ChunkInfo(
                        nr=chunk_number,
                        relative_path=_make_relative_path(chunk_path, account_dir),
                        profile_count=len(current_chunk),
                        bytes=byte_count,
                    )
                )
                current_chunk = []
                chunk_number += 1
            _sleep(sleep_reason)
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "%s collection failed; continuing | %s",
            iterator_name,
            format_kv(username=handle, error=exc),
        )
        if current_chunk:
            chunk_path = rel_root / f"{chunk_prefix}{chunk_number:04d}.json"
            byte_count = _write_chunk(chunk_path, current_chunk)
            chunks.append(
                ChunkInfo(
                    nr=chunk_number,
                    relative_path=_make_relative_path(chunk_path, account_dir),
                    profile_count=len(current_chunk),
                    bytes=byte_count,
                )
            )
            current_chunk = []
            chunk_number += 1
        elapsed = round(time.perf_counter() - t0, 3)
        return RelationshipCollectionResult(
            handle=handle,
            count=count,
            skipped=False,
            chunks=chunks,
            elapsed_seconds=elapsed,
        )

    if current_chunk:
        chunk_path = rel_root / f"{chunk_prefix}{chunk_number:04d}.json"
        byte_count = _write_chunk(chunk_path, current_chunk)
        chunks.append(
            ChunkInfo(
                nr=chunk_number,
                relative_path=_make_relative_path(chunk_path, account_dir),
                profile_count=len(current_chunk),
                bytes=byte_count,
            )
        )

    elapsed = round(time.perf_counter() - t0, 3)
    logger.info(
        "%s collection complete | %s",
        iterator_name,
        format_kv(
            username=handle,
            count=count,
            chunk_count=len(chunks),
            elapsed_seconds=elapsed,
        ),
    )
    return RelationshipCollectionResult(
        handle=handle,
        count=count,
        skipped=False,
        chunks=chunks,
        elapsed_seconds=elapsed,
    )


def collect_followers(
    profile: Any,
    account_dir: Path | None,
    chunk_size: int = FOLLOW_CHUNK_SIZE,
) -> RelationshipCollectionResult:
    """Collect all followers for a profile with progressive chunking."""
    return _collect_relationship(
        profile=profile,
        account_dir=account_dir,
        chunk_size=chunk_size,
        iterator_name="get_followers",
        chunk_prefix="followers__",
        sleep_reason="between follower iterations",
    )


def collect_followees(
    profile: Any,
    account_dir: Path | None,
    chunk_size: int = FOLLOW_CHUNK_SIZE,
) -> RelationshipCollectionResult:
    """Collect all followees for a profile with progressive chunking."""
    return _collect_relationship(
        profile=profile,
        account_dir=account_dir,
        chunk_size=chunk_size,
        iterator_name="get_followees",
        chunk_prefix="followees__",
        sleep_reason="between followee iterations",
    )
