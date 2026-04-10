"""Tests for tagged collection via instaloader mocks."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from ig_scraper.tagged_collection import (
    TaggedCollectionResult,
    _post_to_dict,
    collect_tagged_posts,
)


if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_post(
    pk: int = 100,
    shortcode: str = "ABC123",
    typename: str = "GraphImage",
    caption: str = "Hello world!",
    likes: int = 42,
    comments: int = 3,
    date: str = "2024-06-15 12:00:00",
    owner_username: str = "poster",
    owner_full_name: str = "Poster Name",
    owner_id: int = 999,
    is_video: bool = False,
    video_url: str = "",
    url: str = "https://www.instagram.com/p/ABC123/",
    caption_mentions: list[str] | None = None,
    caption_hashtags: list[str] | None = None,
) -> MagicMock:
    """Build a mock instaloader Post for tagged posts."""
    return MagicMock(
        pk=pk,
        shortcode=shortcode,
        typename=typename,
        caption=caption,
        likes=likes,
        comments=comments,
        date=date,
        owner_username=owner_username,
        owner_full_name=owner_full_name,
        owner_id=owner_id,
        is_video=is_video,
        video_url=video_url,
        url=url,
        caption_mentions=caption_mentions or [],
        caption_hashtags=caption_hashtags or [],
    )


# ---------------------------------------------------------------------------
# _post_to_dict
# ---------------------------------------------------------------------------


class TestPostToDict:
    def test_converts_basic_post(self) -> None:
        post = _mock_post(pk=123, shortcode="XYZ789", caption="Test #python")
        result = _post_to_dict(post)
        assert result["pk"] == "123"
        assert result["shortcode"] == "XYZ789"
        assert result["typename"] == "GraphImage"
        assert result["caption"] == "Test #python"
        assert result["like_count"] == 42
        assert result["comment_count"] == 3
        assert result["owner_username"] == "poster"
        assert "XYZ789" in result["url"]

    def test_video_post_includes_video_url(self) -> None:
        post = _mock_post(
            is_video=True,
            video_url="https://cdn.example.com/video.mp4",
        )
        result = _post_to_dict(post)
        assert result["is_video"] is True
        assert result["video_url"] == "https://cdn.example.com/video.mp4"

    def test_mentions_and_hashtags_extracted(self) -> None:
        post = _mock_post(
            caption="@alice @bob #python #coding",
            caption_mentions=["alice", "bob"],
            caption_hashtags=["python", "coding"],
        )
        result = _post_to_dict(post)
        assert result["mentions"] == ["alice", "bob"]
        assert result["hashtags"] == ["python", "coding"]

    def test_missing_fields_default_empty(self) -> None:
        post = MagicMock(
            pk=None,
            shortcode="",
            typename=None,
            caption=None,
            likes=0,
            comments=None,
            date="",
            owner_username="",
            owner_full_name=None,
            owner_id=None,
            is_video=False,
            video_url="",
            url="",
            caption_mentions=None,
            caption_hashtags=None,
        )
        result = _post_to_dict(post)
        assert result["pk"] == ""
        assert result["caption"] == ""
        assert result["like_count"] == 0
        assert result["mentions"] == []
        assert result["hashtags"] == []


# ---------------------------------------------------------------------------
# collect_tagged_posts — success path
# ---------------------------------------------------------------------------


class TestCollectTaggedPostsSuccess:
    def test_no_posts_returns_empty_items(self, tmp_path: Path) -> None:
        profile = MagicMock(username="nope")
        profile.get_tagged_posts.return_value = []

        result = collect_tagged_posts(profile, tmp_path)

        assert result.skipped is False
        assert result.skip_reason is None
        assert result.items == []
        assert result.file_path is not None
        tagged_json = tmp_path / "tagged" / "posts.json"
        assert tagged_json.exists()
        data = json.loads(tagged_json.read_text(encoding="utf-8"))
        assert data["tagged_posts"] == []

    def test_single_tagged_post(self, tmp_path: Path) -> None:
        post = _mock_post(pk=50, shortcode="SINGLE", caption="Tag me!")
        profile = MagicMock(username="tagger")
        profile.get_tagged_posts.return_value = [post]

        result = collect_tagged_posts(profile, tmp_path)

        assert result.skipped is False
        assert len(result.items) == 1
        assert result.items[0]["pk"] == "50"
        assert result.items[0]["shortcode"] == "SINGLE"
        tagged_json = tmp_path / "tagged" / "posts.json"
        data = json.loads(tagged_json.read_text(encoding="utf-8"))
        assert len(data["tagged_posts"]) == 1

    def test_multiple_tagged_posts(self, tmp_path: Path) -> None:
        posts = [
            _mock_post(pk=10, shortcode="FIRST"),
            _mock_post(pk=20, shortcode="SECOND"),
            _mock_post(pk=30, shortcode="THIRD"),
        ]
        profile = MagicMock(username="popular")
        profile.get_tagged_posts.return_value = posts

        result = collect_tagged_posts(profile, tmp_path)

        assert result.skipped is False
        assert len(result.items) == 3
        tagged_json = tmp_path / "tagged" / "posts.json"
        data = json.loads(tagged_json.read_text(encoding="utf-8"))
        assert len(data["tagged_posts"]) == 3


# ---------------------------------------------------------------------------
# collect_tagged_posts — skip / error path
# ---------------------------------------------------------------------------


class TestCollectTaggedPostsSkip:
    def test_none_account_dir_skips(self) -> None:
        profile = MagicMock(username="skip")

        result = collect_tagged_posts(profile, None)

        assert result.skipped is True
        assert result.skip_reason == "no account_dir"
        assert result.items == []
        profile.get_tagged_posts.assert_not_called()

    def test_get_tagged_posts_exception_skips(self, tmp_path: Path) -> None:
        profile = MagicMock(username="fail")
        profile.get_tagged_posts.side_effect = RuntimeError("connection reset")

        result = collect_tagged_posts(profile, tmp_path)

        assert result.skipped is True
        assert "Error iterating tagged posts" in result.skip_reason
        assert result.items == []
