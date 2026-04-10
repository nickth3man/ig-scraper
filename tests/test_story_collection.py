"""Tests for story collection via instaloader mocks."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from ig_scraper.story_collection import (
    StoryCollectionResult,
    _build_story_item,
    _format_datetime,
    _write_json,
    collect_stories,
)


if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_story_item(
    mediaid: int = 100,
    caption: str = "hello",
    hashtags: list[str] | None = None,
    mentions: list[str] | None = None,
    is_video: bool = False,
    video_url: str | None = None,
    url: str = "https://cdn.example.com/img.jpg",
    date_utc: datetime | None = None,
) -> MagicMock:
    """Build a mock instaloader StoryItem."""
    return MagicMock(
        mediaid=mediaid,
        caption=caption,
        caption_hashtags=hashtags or [],
        caption_mentions=mentions or [],
        is_video=is_video,
        video_url=video_url,
        url=url,
        date_utc=date_utc or datetime(2024, 6, 15, 12, 0, 0),
    )


def _mock_story(
    story_id: int = 1,
    username: str = "alice",
    items: list[MagicMock] | None = None,
) -> MagicMock:
    """Build a mock instaloader Story (highlight feed item)."""
    story = MagicMock(id=story_id, username=username)
    story.get_items.return_value = items or []
    return story


# ---------------------------------------------------------------------------
# _format_datetime
# ---------------------------------------------------------------------------


class TestFormatDatetime:
    def test_none_returns_empty_string(self) -> None:
        assert _format_datetime(None) == ""

    def test_datetime_isoformat(self) -> None:
        dt = datetime(2024, 3, 10, 8, 30, 0)
        assert _format_datetime(dt) == "2024-03-10T08:30:00"

    def test_string_passthrough(self) -> None:
        assert _format_datetime("2024-01-01") == "2024-01-01"


# ---------------------------------------------------------------------------
# _write_json
# ---------------------------------------------------------------------------


class TestWriteJson:
    def test_creates_file_and_parents(self, tmp_path: Path) -> None:
        target = tmp_path / "deep" / "nested" / "out.json"
        _write_json(target, {"key": "value"})
        assert target.exists()
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["key"] == "value"


# ---------------------------------------------------------------------------
# collect_stories — success path
# ---------------------------------------------------------------------------


class TestCollectStoriesSuccess:
    def test_no_stories_returns_empty_items(self, tmp_path: Path) -> None:
        client = MagicMock()
        client.get_stories.return_value = []
        profile = MagicMock(username="nobody")

        result = collect_stories(client, profile, tmp_path)

        assert result.items == []
        assert result.skipped is False
        assert result.skip_reason is None

    def test_single_story_with_items(self, tmp_path: Path) -> None:
        item = _mock_story_item(mediaid=10, caption="sunset", hashtags=["sky"])
        story = _mock_story(story_id=42, username="bob", items=[item])
        client = MagicMock()
        client.get_stories.return_value = [story]
        profile = MagicMock(username="bob")

        result = collect_stories(client, profile, tmp_path)

        assert len(result.items) == 1
        assert result.skipped is False

        story_file = tmp_path / "stories" / "42" / "42.json"
        assert story_file.exists()
        data = json.loads(story_file.read_text(encoding="utf-8"))
        assert data["owner_username"] == "bob"
        assert data["media_count"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["caption"] == "sunset"
        assert data["items"][0]["hashtags"] == ["sky"]

    def test_multiple_stories_with_multiple_items(self, tmp_path: Path) -> None:
        items_a = [_mock_story_item(mediaid=i) for i in range(3)]
        items_b = [_mock_story_item(mediaid=i + 100) for i in range(2)]
        story_a = _mock_story(story_id=1, items=items_a)
        story_b = _mock_story(story_id=2, items=items_b)
        client = MagicMock()
        client.get_stories.return_value = [story_a, story_b]
        profile = MagicMock(username="multi")

        result = collect_stories(client, profile, tmp_path)

        assert len(result.items) == 2

    def test_story_item_with_video(self, tmp_path: Path) -> None:
        item = _mock_story_item(
            mediaid=55,
            is_video=True,
            video_url="https://cdn.example.com/vid.mp4",
        )
        story = _mock_story(story_id=99, items=[item])
        client = MagicMock()
        client.get_stories.return_value = [story]
        profile = MagicMock(username="videouser")

        collect_stories(client, profile, tmp_path)

        story_file = tmp_path / "stories" / "99" / "99.json"
        data = json.loads(story_file.read_text(encoding="utf-8"))
        assert data["items"][0]["is_video"] is True
        assert data["items"][0]["video_url"] == "https://cdn.example.com/vid.mp4"

    def test_story_item_null_caption_fields(self, tmp_path: Path) -> None:
        """Graceful handling: caption, hashtags, mentions may be None."""
        item = MagicMock(
            caption=None,
            caption_hashtags=None,
            caption_mentions=None,
            is_video=False,
            video_url=None,
            url="https://cdn.example.com/img.jpg",
            date_utc=datetime(2024, 1, 1, 0, 0, 0),
        )
        story = _mock_story(story_id=7, items=[item])
        client = MagicMock()
        client.get_stories.return_value = [story]
        profile = MagicMock(username="nullfields")

        collect_stories(client, profile, tmp_path)

        story_file = tmp_path / "stories" / "7" / "7.json"
        data = json.loads(story_file.read_text(encoding="utf-8"))
        assert data["items"][0]["caption"] == ""
        assert data["items"][0]["hashtags"] == []
        assert data["items"][0]["mentions"] == []

    def test_latest_media_utc_from_last_item(self, tmp_path: Path) -> None:
        dt_early = datetime(2024, 1, 1, 0, 0, 0)
        dt_late = datetime(2024, 6, 15, 12, 0, 0)
        items = [_mock_story_item(date_utc=dt_early), _mock_story_item(date_utc=dt_late)]
        story = _mock_story(story_id=10, items=items)
        client = MagicMock()
        client.get_stories.return_value = [story]
        profile = MagicMock(username="dates")

        collect_stories(client, profile, tmp_path)

        story_file = tmp_path / "stories" / "10" / "10.json"
        data = json.loads(story_file.read_text(encoding="utf-8"))
        assert data["latest_media_utc"] == "2024-06-15T12:00:00"


# ---------------------------------------------------------------------------
# collect_stories — graceful degradation / auth failure
# ---------------------------------------------------------------------------


class TestCollectStoriesGraceful:
    def test_connection_exception_returns_skipped(self, tmp_path: Path) -> None:
        from instaloader.exceptions import ConnectionException

        client = MagicMock()
        client.get_stories.side_effect = ConnectionException("network error")
        profile = MagicMock(username="fail")

        result = collect_stories(client, profile, tmp_path)

        assert result.skipped is True
        assert result.skip_reason is not None
        assert "unexpected error" in result.skip_reason

    def test_auth_exception_returns_skipped(self, tmp_path: Path) -> None:
        from instaloader.exceptions import LoginRequiredException

        client = MagicMock()
        client.get_stories.side_effect = LoginRequiredException("login needed")
        profile = MagicMock(username="noauth")

        result = collect_stories(client, profile, tmp_path)

        assert result.skipped is True
        assert result.skip_reason is not None
        assert "auth" in result.skip_reason.lower()

    def test_empty_items_story_still_writes_json(self, tmp_path: Path) -> None:
        story = _mock_story(story_id=3, items=[])
        client = MagicMock()
        client.get_stories.return_value = [story]
        profile = MagicMock(username="empty")

        collect_stories(client, profile, tmp_path)

        story_file = tmp_path / "stories" / "3" / "3.json"
        assert story_file.exists()
        data = json.loads(story_file.read_text(encoding="utf-8"))
        assert data["media_count"] == 0
        assert data["items"] == []

    @patch("ig_scraper.story_collection._write_json")
    def test_write_failure_caught_gracefully(self, mock_write: MagicMock, tmp_path: Path) -> None:
        mock_write.side_effect = OSError("disk full")
        item = _mock_story_item()
        story = _mock_story(story_id=1, items=[item])
        client = MagicMock()
        client.get_stories.return_value = [story]
        profile = MagicMock(username="diskfull")

        result = collect_stories(client, profile, tmp_path)

        assert result.skipped is True
        assert result.skip_reason is not None
        assert "disk full" in result.skip_reason

    def test_result_contains_manifest_friendly_items(self, tmp_path: Path) -> None:
        item = _mock_story_item(mediaid=10)
        story = _mock_story(story_id=5, items=[item])
        client = MagicMock()
        client.get_stories.return_value = [story]
        profile = MagicMock(username="manifest")

        result = collect_stories(client, profile, tmp_path)

        assert len(result.items) == 1
        assert result.items[0]["story_id"] == "5"
        assert result.items[0]["media_count"] == 1
        assert result.file_path is not None
