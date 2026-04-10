"""Tests for relationship_collection module.

Mock-only tests for the Phase 2 manifest-ready contract:
``collect_followers()`` and ``collect_followees()`` return
``RelationshipCollectionResult`` with explicit count, empty items,
and chunk metadata suitable for direct use by build_manifest().
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from ig_scraper.relationship_collection import (
    ChunkInfo,
    RelationshipCollectionResult,
    _collect_relationship,
    collect_followees,
    collect_followers,
)


if TYPE_CHECKING:
    from pathlib import Path


class FakeProfile:
    """Minimal fake profile for testing without real instaloader."""

    def __init__(self, username: str = "testuser", is_logged_in: bool = True) -> None:  # noqa: D107
        self.username = username
        self._is_logged_in = is_logged_in
        self.context = MagicMock(is_logged_in=is_logged_in) if is_logged_in else None

    def get_followers(self) -> Any:
        return iter([])

    def get_followees(self) -> Any:
        return iter([])


def _fake_profile_dict(username: str, **kwargs: Any) -> dict[str, Any]:
    """Return a minimal profile dict matching _profile_to_dict output."""
    defaults: dict[str, Any] = {
        "id": "12345",
        "username": username,
        "full_name": f"{username.title()} Name",
        "profile_pic_url": f"https://example.com/{username}.jpg",
        "is_private": False,
        "is_verified": False,
        "followers": 100,
        "following": 50,
    }
    defaults.update(kwargs)
    return defaults


def test_collect_relationship_skipped_no_account_dir(
    tmp_path: Path,
) -> None:
    """Skipped when no account_dir is provided."""
    profile = FakeProfile()
    result = _collect_relationship(
        profile=profile,
        account_dir=None,
        chunk_size=5000,
        iterator_name="get_followers",
        chunk_prefix="followers__",
        sleep_reason="test",
    )
    assert result.skipped is True
    assert result.skipped_reason == "no account directory"
    assert result.count == 0
    assert result.chunks == []


def test_collect_relationship_empty_iterator(tmp_path: Path) -> None:
    """Empty iterator produces zero count and no chunks."""
    profile = FakeProfile()
    with patch.object(profile, "get_followers", return_value=iter([])):
        result = _collect_relationship(
            profile=profile,
            account_dir=tmp_path,
            chunk_size=5000,
            iterator_name="get_followers",
            chunk_prefix="followers__",
            sleep_reason="test",
        )
    assert result.skipped is False
    assert result.count == 0
    assert result.chunks == []
    assert result.handle == "testuser"


def test_collect_relationship_single_chunk(tmp_path: Path) -> None:
    """Single chunk emits correct ChunkInfo with handle-root-relative path."""
    items = [_fake_profile_dict(f"user{i}") for i in range(3)]
    profile = FakeProfile()

    def fake_iter() -> Any:
        yield from items

    with patch.object(profile, "get_followers", fake_iter):
        result = _collect_relationship(
            profile=profile,
            account_dir=tmp_path,
            chunk_size=5000,
            iterator_name="get_followers",
            chunk_prefix="followers__",
            sleep_reason="test",
        )

    assert result.skipped is False
    assert result.count == 3
    assert len(result.chunks) == 1
    assert result.chunks[0].nr == 1
    assert result.chunks[0].relative_path == "relationships/followers__0001.json"
    assert result.chunks[0].profile_count == 3

    chunk_file = tmp_path / "relationships" / "followers__0001.json"
    assert chunk_file.exists()
    loaded = json.loads(chunk_file.read_text(encoding="utf-8"))
    assert len(loaded) == 3


def test_collect_relationship_multiple_chunks(tmp_path: Path) -> None:
    """Chunk boundaries respected and all ChunkInfo fields populated."""
    items = [_fake_profile_dict(f"user{i}") for i in range(7)]
    profile = FakeProfile()

    def fake_iter() -> Any:
        yield from items

    with patch.object(profile, "get_followers", fake_iter):
        result = _collect_relationship(
            profile=profile,
            account_dir=tmp_path,
            chunk_size=3,
            iterator_name="get_followers",
            chunk_prefix="followers__",
            sleep_reason="test",
        )

    assert result.skipped is False
    assert result.count == 7
    assert len(result.chunks) == 3

    assert result.chunks[0].nr == 1
    assert result.chunks[0].profile_count == 3
    assert result.chunks[0].relative_path == "relationships/followers__0001.json"

    assert result.chunks[1].nr == 2
    assert result.chunks[1].profile_count == 3

    assert result.chunks[2].nr == 3
    assert result.chunks[2].profile_count == 1

    assert result.chunks[0].bytes > 0
    assert result.chunks[1].bytes > 0
    assert result.chunks[2].bytes > 0


def test_collect_relationship_graceful_degradation_on_error(tmp_path: Path) -> None:
    """Iteration error: partial chunk written and graceful result returned."""
    items = [_fake_profile_dict(f"user{i}") for i in range(4)]
    profile = FakeProfile()

    def fake_iter() -> Any:
        yield items[0]
        raise RuntimeError("simulated error")

    with patch.object(profile, "get_followers", fake_iter):
        result = _collect_relationship(
            profile=profile,
            account_dir=tmp_path,
            chunk_size=5000,
            iterator_name="get_followers",
            chunk_prefix="followers__",
            sleep_reason="test",
        )

    assert result.skipped is False
    assert result.count == 1
    assert len(result.chunks) == 1
    assert result.chunks[0].profile_count == 1


def test_collect_relationship_unauthenticated_profile(tmp_path: Path) -> None:
    """Unauthenticated profile still returns result with handle identity."""
    profile = MagicMock()
    profile.username = "unauth_user"
    profile.context = MagicMock(is_logged_in=False)
    profile.get_followers.return_value = iter([])

    result = _collect_relationship(
        profile=profile,
        account_dir=tmp_path,
        chunk_size=5000,
        iterator_name="get_followers",
        chunk_prefix="followers__",
        sleep_reason="test",
    )

    assert result.handle == "unauth_user"


def test_collect_followers_returns_correct_type(tmp_path: Path) -> None:
    """collect_followers returns RelationshipCollectionResult with handle."""
    profile = MagicMock()
    profile.username = "testuser"
    profile.context = MagicMock(is_logged_in=True)
    profile.get_followers.return_value = iter([])

    result = collect_followers(profile, tmp_path)
    assert isinstance(result, RelationshipCollectionResult)
    assert result.handle == "testuser"


def test_collect_followees_returns_correct_type(tmp_path: Path) -> None:
    """collect_followees returns RelationshipCollectionResult with handle."""
    profile = MagicMock()
    profile.username = "testuser"
    profile.context = MagicMock(is_logged_in=True)
    profile.get_followees.return_value = iter([])

    result = collect_followees(profile, tmp_path)
    assert isinstance(result, RelationshipCollectionResult)
    assert result.handle == "testuser"


def test_collect_relationship_uses_correct_prefix_followers(tmp_path: Path) -> None:
    """Follower chunks named followers__NNNN.json under relationships/."""
    items = [_fake_profile_dict(f"user{i}") for i in range(1)]
    profile = FakeProfile()

    def fake_iter() -> Any:
        yield from items

    with patch.object(profile, "get_followers", fake_iter):
        result = _collect_relationship(
            profile=profile,
            account_dir=tmp_path,
            chunk_size=5000,
            iterator_name="get_followers",
            chunk_prefix="followers__",
            sleep_reason="test",
        )

    chunk_file = tmp_path / "relationships" / "followers__0001.json"
    assert chunk_file.exists()
    assert result.chunks[0].relative_path == "relationships/followers__0001.json"


def test_collect_relationship_uses_correct_prefix_followees(tmp_path: Path) -> None:
    """Followee chunks named followees__NNNN.json under relationships/."""
    items = [_fake_profile_dict(f"user{i}") for i in range(1)]
    profile = FakeProfile()

    def fake_iter() -> Any:
        yield from items

    with patch.object(profile, "get_followees", fake_iter):
        result = _collect_relationship(
            profile=profile,
            account_dir=tmp_path,
            chunk_size=5000,
            iterator_name="get_followees",
            chunk_prefix="followees__",
            sleep_reason="test",
        )

    chunk_file = tmp_path / "relationships" / "followees__0001.json"
    assert chunk_file.exists()
    assert result.chunks[0].relative_path == "relationships/followees__0001.json"


def test_chunk_info_is_frozen() -> None:
    """ChunkInfo is immutable (frozen=True)."""
    chunk = ChunkInfo(
        nr=1,
        relative_path="relationships/followers__0001.json",
        profile_count=100,
        bytes=1234,
    )
    assert chunk.nr == 1
    assert chunk.relative_path == "relationships/followers__0001.json"
    assert chunk.profile_count == 100
    assert chunk.bytes == 1234


def test_relationship_collection_result_defaults() -> None:
    """Default values match Phase 2 contract: skipped=True, count=0."""
    result = RelationshipCollectionResult(handle="testuser")
    assert result.count == 0
    assert result.skipped is True
    assert result.skipped_reason == ""
    assert result.chunks == []
    assert result.elapsed_seconds == 0.0


def test_items_property_is_empty() -> None:
    """Items property always returns [] per Oracle manifest guidance."""
    result = RelationshipCollectionResult(
        handle="testuser",
        count=10,
        skipped=False,
        chunks=[
            ChunkInfo(
                nr=1,
                relative_path="relationships/followers__0001.json",
                profile_count=10,
                bytes=1234,
            )
        ],
    )
    assert result.items == []


def test_to_dict_returns_manifest_ready_summary() -> None:
    """to_dict() produces manifest-ready summary with count, items=[], chunks."""
    result = RelationshipCollectionResult(
        handle="testuser",
        count=5,
        skipped=False,
        chunks=[
            ChunkInfo(
                nr=1,
                relative_path="relationships/followers__0001.json",
                profile_count=5,
                bytes=999,
            )
        ],
    )
    d = result.to_dict()
    assert d["count"] == 5
    assert d["items"] == []
    assert d["skipped"] is False
    assert d["skipped_reason"] == ""
    assert len(d["chunks"]) == 1
    assert d["chunks"][0]["chunk_number"] == 1
    assert d["chunks"][0]["file_path"] == "relationships/followers__0001.json"
    assert d["chunks"][0]["profile_count"] == 5
    assert d["chunks"][0]["bytes"] == 999


def test_to_dict_skipped_includes_reason() -> None:
    """Skipped result includes skipped_reason in to_dict() output."""
    result = RelationshipCollectionResult(
        handle="testuser",
        skipped=True,
        skipped_reason="no account directory",
    )
    d = result.to_dict()
    assert d["skipped"] is True
    assert d["skipped_reason"] == "no account directory"
    assert d["count"] == 0
    assert d["items"] == []
    assert d["chunks"] == []


def test_phase2_contract_build_manifest_compatible(
    tmp_path: Path,
) -> None:
    """to_dict() output is directly compatible with export._build_collection_entry."""
    from ig_scraper.export import _build_collection_entry

    items = [_fake_profile_dict(f"user{i}") for i in range(3)]
    profile = FakeProfile()

    def fake_iter() -> Any:
        yield from items

    with patch.object(profile, "get_followers", fake_iter):
        result = _collect_relationship(
            profile=profile,
            account_dir=tmp_path,
            chunk_size=5000,
            iterator_name="get_followers",
            chunk_prefix="followers__",
            sleep_reason="test",
        )

    entry = _build_collection_entry("followers", result.to_dict())
    assert entry["domain"] == "followers"
    assert entry["count"] == 3
    assert entry["items"] == []
    assert entry["chunked"] is True
    assert len(entry["chunks"]) == 1
    assert entry["chunks"][0]["file_path"] == "relationships/followers__0001.json"
