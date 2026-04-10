"""Result types for relationship collection (followers/followees).

Phase 2 contract: ``RelationshipCollectionResult`` carries explicit
``count``, an empty ``items`` list (relationship data stays chunked on
disk per Oracle guidance), and ``chunks`` metadata. Serialise via
``to_dict()`` for direct use by ``export.build_manifest()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChunkInfo:
    """Metadata for a single chunk file on disk.

    Attributes:
        nr: 1-based chunk sequence number.
        relative_path: Handle-root-relative path to the chunk file
            (e.g. ``"relationships/followers__0001.json"``).
        profile_count: Number of profile records in this chunk.
        bytes: Byte size of the chunk file on disk.
    """

    nr: int
    relative_path: str
    profile_count: int
    bytes: int


@dataclass
class RelationshipCollectionResult:
    """Result of a followers or followees collection pass.

    Phase 2 manifest-ready contract: ``count`` is explicit (not derived
    from items), ``items`` is always an empty list (relationship data
    stays chunked on disk), and ``chunks`` carries per-file metadata with
    handle-root-relative paths.

    Attributes:
        handle: Instagram handle for identity only (not persisted into
            manifest by ``_build_collection_entry``).
        count: Total profiles collected; 0 when skipped.
        skipped: True when collection was skipped (no account_dir or auth
            failure).
        skipped_reason: Human-readable reason when skipped.
        chunks: Ordered list of ChunkInfo for every chunk file written.
        elapsed_seconds: Wall-clock time for the collection pass.
    """

    handle: str
    count: int = 0
    skipped: bool = True
    skipped_reason: str = ""
    chunks: list[ChunkInfo] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    @property
    def items(self) -> list[Any]:
        """Always empty — relationship data stays chunked, not in manifest."""
        return []

    def to_dict(self) -> dict[str, Any]:
        """Serialize for direct use by ``export._build_collection_entry()``.

        Produces a summary dict with ``count``, ``items=[]``, and ``chunks``
        so the manifest builder can emit explicit metadata without accessing
        chunk files. When ``skipped`` is True the dict still carries the
        skipped flag so callers can handle graceful degradation.
        """
        result: dict[str, Any] = {
            "count": self.count,
            "items": [],
            "skipped": self.skipped,
            "skipped_reason": self.skipped_reason,
            "chunks": [
                {
                    "chunk_number": c.nr,
                    "file_path": c.relative_path,
                    "profile_count": c.profile_count,
                    "bytes": c.bytes,
                }
                for c in self.chunks
            ],
        }
        return result
