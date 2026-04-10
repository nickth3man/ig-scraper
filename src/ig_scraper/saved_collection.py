"""Saved posts collection for Instagram via instaloader.

Requires authentication — ``Profile.get_saved_posts()`` is only available
when logged in. Phase 2 contract: Returns SavedCollectionResult with chunk
summary metadata (count, items=[], chunks) instead of bloating manifest.json.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from ig_scraper.config import _sleep
from ig_scraper.logging_utils import format_kv, get_logger
from ig_scraper.saved_collection_models import ChunkInfo, SavedCollectionResult


if TYPE_CHECKING:
    from pathlib import Path


logger = get_logger("saved")


def _write_chunk(chunk_path: Path, posts: list[dict[str, Any]]) -> None:
    """Write a single chunk of posts to disk as JSON."""
    chunk_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(posts, indent=2, ensure_ascii=False)
    chunk_path.write_text(payload, encoding="utf-8")
    logger.info(
        "Chunk written | %s",
        format_kv(path=chunk_path, post_count=len(posts), bytes=len(payload.encode("utf-8"))),
    )


def collect_saved_posts(
    client: Any,
    profile: Any,
    account_dir: Path | None,
    chunk_size: int = 1000,
) -> SavedCollectionResult:
    """Collect all saved posts for the authenticated account with progressive chunking.

    Writes ``saved/posts__0001.json`` every *chunk_size* posts to avoid holding
    the entire dataset in memory. Remaining posts are written to a final chunk
    on completion.

    Args:
        client: An instaloader client instance.
        profile: The instaloader Profile object for the authenticated account.
        account_dir: The account directory path where ``saved/`` will be created.
        chunk_size: Number of posts per chunk file (default 1000).

    Returns:
        SavedCollectionResult with count, items=[], chunks metadata, and
        skipped flag. Raises nothing — auth absence triggers a graceful skip.
    """
    if not account_dir:
        logger.info("No account_dir; skipping saved collection")
        return SavedCollectionResult(
            skipped=True,
            skip_reason="No account directory provided",
        )

    is_logged_in = getattr(client.context, "is_logged_in", False)
    if not is_logged_in:
        logger.info(
            "Not authenticated; skipping saved collection | %s",
            format_kv(username=getattr(profile, "username", "unknown")),
        )
        return SavedCollectionResult(
            skipped=True,
            skip_reason="Not authenticated — saved posts require an authenticated session",
        )

    logger.info(
        "Starting saved posts collection | %s",
        format_kv(
            username=getattr(profile, "username", "unknown"),
            chunk_size=chunk_size,
        ),
    )

    t0 = time.perf_counter()
    saved_root = account_dir / "saved"
    saved_root.mkdir(parents=True, exist_ok=True)

    current_chunk: list[dict[str, Any]] = []
    chunk_number = 1
    total_saved = 0
    chunks: list[ChunkInfo] = []

    try:
        for post in profile.get_saved_posts():
            post_dict = _post_to_dict(post)
            current_chunk.append(post_dict)
            total_saved += 1

            if len(current_chunk) >= chunk_size:
                chunk_path = saved_root / f"posts__{chunk_number:04d}.json"
                _write_chunk(chunk_path, current_chunk)
                chunks.append(
                    ChunkInfo(
                        chunk_number=chunk_number,
                        file_path=str(chunk_path.relative_to(account_dir)),
                        post_count=len(current_chunk),
                    )
                )
                current_chunk = []
                chunk_number += 1

            _sleep("between saved post iterations")

    except Exception as exc:  # pragma: no cover
        logger.warning(
            "Saved posts collection failed; continuing | %s",
            format_kv(username=getattr(profile, "username", ""), error=exc),
        )
        if current_chunk:
            chunk_path = saved_root / f"posts__{chunk_number:04d}.json"
            _write_chunk(chunk_path, current_chunk)
            chunks.append(
                ChunkInfo(
                    chunk_number=chunk_number,
                    file_path=str(chunk_path.relative_to(account_dir)),
                    post_count=len(current_chunk),
                )
            )
            current_chunk = []
            chunk_number += 1

        elapsed = round(time.perf_counter() - t0, 3)
        logger.info(
            "Saved posts collection partial | %s",
            format_kv(
                username=getattr(profile, "username", ""),
                total_saved=total_saved,
                chunks_written=len(chunks),
                elapsed_seconds=elapsed,
            ),
        )
        return SavedCollectionResult(
            count=total_saved,
            chunks=chunks,
            skipped=False,
            file_path=str(saved_root.relative_to(account_dir)),
        )

    if current_chunk:
        chunk_path = saved_root / f"posts__{chunk_number:04d}.json"
        _write_chunk(chunk_path, current_chunk)
        chunks.append(
            ChunkInfo(
                chunk_number=chunk_number,
                file_path=str(chunk_path.relative_to(account_dir)),
                post_count=len(current_chunk),
            )
        )

    elapsed = round(time.perf_counter() - t0, 3)
    logger.info(
        "Saved posts collection complete | %s",
        format_kv(
            username=getattr(profile, "username", ""),
            total_saved=total_saved,
            chunks_written=len(chunks),
            elapsed_seconds=elapsed,
        ),
    )

    return SavedCollectionResult(
        count=total_saved,
        chunks=chunks,
        skipped=False,
        file_path=str(saved_root.relative_to(account_dir)),
    )


def _post_to_dict(post: Any) -> dict[str, Any]:
    """Convert an instaloader Post object to a plain dictionary.

    Uses the Post model for consistency with the rest of the scraper.
    """
    from ig_scraper.models import Post

    username = getattr(post, "owner_username", "") or ""
    user_id = getattr(post, "owner_id", "") or ""
    full_name = getattr(post, "owner_full_name", "") or ""

    post_model = Post.from_instaloader_post(
        post=post,
        username=username,
        user_full_name=full_name,
        user_id=user_id,
    )
    return post_model.to_dict()
