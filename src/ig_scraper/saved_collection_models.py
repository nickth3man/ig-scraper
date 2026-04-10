"""Result dataclasses for saved posts collection (Phase 2 contract)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChunkInfo:
    """Metadata for a single saved-post chunk file."""

    chunk_number: int
    file_path: str
    post_count: int


@dataclass
class SavedCollectionResult:
    """Result of a saved posts collection operation.

    Attributes:
        count: Total number of saved posts collected.
        items: Always empty list (saved posts stay chunked on disk; manifest
            uses summary metadata only per Oracle guidance).
        chunks: Per-chunk file metadata with relative paths and post counts.
        skipped: True when collection was skipped (not authenticated).
        skip_reason: Human-readable reason when skipped.
        file_path: Path to the saved/ directory if chunks were written.
    """

    count: int = 0
    items: list = field(default_factory=list)
    chunks: list[ChunkInfo] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None
    file_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for callers that expect a mapping."""
        return {
            "count": self.count,
            "items": self.items,
            "chunks": [
                {
                    "chunk_number": c.chunk_number,
                    "file_path": c.file_path,
                    "post_count": c.post_count,
                }
                for c in self.chunks
            ],
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "file_path": self.file_path,
        }
