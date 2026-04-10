"""Tests for saved posts collection via instaloader mocks."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest


if TYPE_CHECKING:
    from pathlib import Path

from ig_scraper.saved_collection import (
    ChunkInfo,
    SavedCollectionResult,
    _post_to_dict,
    _write_chunk,
    collect_saved_posts,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_post(
    mediaid: int = 1000,
    shortcode: str = "POST1",
    caption: str = "hello world",
    is_video: bool = False,
    likes: int = 10,
    comments: int = 2,
    owner_username: str = "author",
    owner_id: str = "42",
    owner_full_name: str = "Author Name",
) -> MagicMock:
    """Build a mock instaloader Post object."""
    from datetime import datetime

    return MagicMock(
        mediaid=mediaid,
        shortcode=shortcode,
        caption=caption,
        is_video=is_video,
        likes=likes,
        comments=comments,
        date_utc=datetime(2024, 6, 15, 12, 0, 0),
        url="https://cdn.example.com/img.jpg",
        video_url="",
        typename="GraphImage",
        media_type=1,
        owner_username=owner_username,
        owner_id=owner_id,
        owner_full_name=owner_full_name,
        caption_hashtags=[],
        caption_mentions=[],
        resources=[],
        view_count=0,
        tagged_users=[],
        sponsor_users=[],
        video_play_count=0,
        video_view_count=0,
        is_sponsored=False,
        title="",
        accessibility_caption="",
        product_type="",
        location=None,
    )


def _logged_in_client() -> MagicMock:
    """Build a mock client with is_logged_in=True."""
    client = MagicMock()
    client.context.is_logged_in = True
    return client


# ---------------------------------------------------------------------------
# _write_chunk
# ---------------------------------------------------------------------------


class TestWriteChunk:
    def test_creates_file_with_posts(self, tmp_path: Path) -> None:
        posts = [{"id": "1"}, {"id": "2"}]
        chunk_path = tmp_path / "saved" / "posts__0001.json"

        _write_chunk(chunk_path, posts)

        assert chunk_path.exists()
        data = json.loads(chunk_path.read_text(encoding="utf-8"))
        assert len(data) == 2


# ---------------------------------------------------------------------------
# _post_to_dict
# ---------------------------------------------------------------------------


class TestPostToDict:
    def test_converts_mock_post_to_dict(self) -> None:
        post = _mock_post(mediaid=999, shortcode="ABCD", caption="test")
        result = _post_to_dict(post)

        assert result["id"] == "999"
        assert result["short_code"] == "ABCD"
        assert result["caption"] == "test"


# ---------------------------------------------------------------------------
# collect_saved_posts — success path
# ---------------------------------------------------------------------------


class TestCollectSavedPostsSuccess:
    def test_no_saved_posts_returns_zero(self, tmp_path: Path) -> None:
        client = _logged_in_client()
        profile = MagicMock(username="empty", get_saved_posts=MagicMock(return_value=iter([])))

        result = collect_saved_posts(client, profile, tmp_path)

        assert result.count == 0
        assert result.skipped is False
        assert result.items == []

    def test_few_posts_single_chunk(self, tmp_path: Path) -> None:
        posts = [_mock_post(mediaid=i) for i in range(3)]
        client = _logged_in_client()
        profile = MagicMock(username="user", get_saved_posts=MagicMock(return_value=iter(posts)))

        with patch("ig_scraper.saved_collection._sleep"):
            result = collect_saved_posts(client, profile, tmp_path, chunk_size=10)

        assert result.count == 3
        assert result.skipped is False
        assert len(result.chunks) == 1
        assert result.chunks[0].post_count == 3
        chunk_file = tmp_path / "saved" / "posts__0001.json"
        assert chunk_file.exists()

    def test_chunking_splits_at_boundary(self, tmp_path: Path) -> None:
        posts = [_mock_post(mediaid=i) for i in range(5)]
        client = _logged_in_client()
        profile = MagicMock(username="chunky", get_saved_posts=MagicMock(return_value=iter(posts)))

        with patch("ig_scraper.saved_collection._sleep"):
            result = collect_saved_posts(client, profile, tmp_path, chunk_size=2)

        assert result.count == 5
        assert len(result.chunks) == 3
        assert result.chunks[0].post_count == 2
        assert result.chunks[1].post_count == 2
        assert result.chunks[2].post_count == 1
        assert (tmp_path / "saved" / "posts__0001.json").exists()
        assert (tmp_path / "saved" / "posts__0002.json").exists()
        assert (tmp_path / "saved" / "posts__0003.json").exists()

    def test_exact_chunk_size_no_remainder(self, tmp_path: Path) -> None:
        posts = [_mock_post(mediaid=i) for i in range(4)]
        client = _logged_in_client()
        profile = MagicMock(username="exact", get_saved_posts=MagicMock(return_value=iter(posts)))

        with patch("ig_scraper.saved_collection._sleep"):
            result = collect_saved_posts(client, profile, tmp_path, chunk_size=2)

        assert result.count == 4
        assert len(result.chunks) == 2

    def test_to_dict_returns_serializable_dict(self, tmp_path: Path) -> None:
        posts = [_mock_post(mediaid=i) for i in range(2)]
        client = _logged_in_client()
        profile = MagicMock(
            username="dict_test", get_saved_posts=MagicMock(return_value=iter(posts))
        )

        with patch("ig_scraper.saved_collection._sleep"):
            result = collect_saved_posts(client, profile, tmp_path, chunk_size=10)

        d = result.to_dict()
        assert d["count"] == 2
        assert d["items"] == []
        assert d["skipped"] is False
        assert len(d["chunks"]) == 1
        assert d["chunks"][0]["post_count"] == 2


# ---------------------------------------------------------------------------
# collect_saved_posts — graceful skip
# ---------------------------------------------------------------------------


class TestCollectSavedPostsGracefulSkip:
    def test_not_logged_in_returns_skipped_result(self, tmp_path: Path) -> None:
        client = MagicMock()
        client.context.is_logged_in = False
        profile = MagicMock(username="anon")

        result = collect_saved_posts(client, profile, tmp_path)

        assert result.skipped is True
        assert "authenticated session" in (result.skip_reason or "")
        assert result.count == 0
        assert result.items == []
        assert result.chunks == []

    def test_none_account_dir_returns_skipped_result(self) -> None:
        client = _logged_in_client()
        profile = MagicMock(username="skip")

        result = collect_saved_posts(client, profile, None)

        assert result.skipped is True
        assert "account directory" in (result.skip_reason or "").lower()
        assert result.count == 0

    def test_get_saved_posts_exception_writes_partial(self, tmp_path: Path) -> None:
        """Exception during iteration writes accumulated partial chunk."""

        def fail_after_two():
            yield _mock_post(mediaid=1)
            yield _mock_post(mediaid=2)
            raise RuntimeError("API blew up")

        client = _logged_in_client()
        profile = MagicMock(username="partial", get_saved_posts=fail_after_two)

        with patch("ig_scraper.saved_collection._sleep"):
            result = collect_saved_posts(client, profile, tmp_path, chunk_size=100)

        assert result.count == 2
        assert result.skipped is False
        assert len(result.chunks) == 1
        assert result.chunks[0].post_count == 2
        chunk = json.loads((tmp_path / "saved" / "posts__0001.json").read_text(encoding="utf-8"))
        assert len(chunk) == 2

    def test_chunk_info_contains_relative_path(self, tmp_path: Path) -> None:
        posts = [_mock_post(mediaid=i) for i in range(3)]
        client = _logged_in_client()
        profile = MagicMock(
            username="path_test", get_saved_posts=MagicMock(return_value=iter(posts))
        )

        with patch("ig_scraper.saved_collection._sleep"):
            result = collect_saved_posts(client, profile, tmp_path, chunk_size=10)

        assert len(result.chunks) == 1
        assert result.chunks[0].chunk_number == 1
        assert "posts__0001.json" in str(result.chunks[0].file_path)
        assert result.file_path is not None
