"""Tests for highlight collection via instaloader mocks."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from ig_scraper.highlight_collection import (
    HighlightCollectionResult,
    _highlight_to_dict,
    _story_item_to_dict,
    collect_highlights,
)


if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_highlight(
    highlight_id: str = "hl_001",
    title: str = "Travel",
    cover_url: str = "https://cdn.example.com/cover.jpg",
    cover_cropped_url: str = "https://cdn.example.com/cover_crop.jpg",
    items: list[MagicMock] | None = None,
) -> MagicMock:
    """Build a mock instaloader Highlight."""
    hl = MagicMock(
        id=highlight_id,
        title=title,
        cover_url=cover_url,
        cover_cropped_url=cover_cropped_url,
    )
    hl.get_items.return_value = items or []
    return hl


def _mock_highlight_item(
    mediaid: int = 200,
    pk: int = 200,
    shortcode: str = "ABC123",
    typename: str = "GraphStoryImage",
    code: str = "ABC123",
    date: str = "2024-06-15 12:00:00",
    likes: int = 5,
) -> MagicMock:
    """Build a mock instaloader StoryItem for highlights."""
    return MagicMock(
        mediaid=mediaid,
        pk=pk,
        shortcode=shortcode,
        typename=typename,
        code=code,
        date=date,
        likes=likes,
    )


# ---------------------------------------------------------------------------
# _highlight_to_dict
# ---------------------------------------------------------------------------


class TestHighlightToDict:
    def test_converts_basic_highlight(self) -> None:
        hl = _mock_highlight(highlight_id="hl_99", title="Food")
        result = _highlight_to_dict(hl, "hl_99/items.json", 3)
        assert result["id"] == "hl_99"
        assert result["title"] == "Food"
        assert result["item_count"] == 3
        assert result["items_file"] == "hl_99/items.json"

    def test_missing_title_defaults_empty(self) -> None:
        hl = MagicMock(id="hl_x", title=None, cover_url="", cover_cropped_url="")
        result = _highlight_to_dict(hl, "x/items.json", 0)
        assert result["title"] == ""


# ---------------------------------------------------------------------------
# _story_item_to_dict
# ---------------------------------------------------------------------------


class TestStoryItemToDict:
    def test_converts_basic_item(self) -> None:
        item = _mock_highlight_item(mediaid=300, shortcode="XYZ")
        result = _story_item_to_dict(item, "hl_42")
        assert result["id"] == "300"
        assert result["pk"] == "200"
        assert result["shortcode"] == "XYZ"
        assert result["likes"] == 5
        assert "hl_42" in result["url"]

    def test_missing_fields_default_empty(self) -> None:
        item = MagicMock(
            mediaid="",
            pk="",
            shortcode="",
            typename="",
            code="",
            date="",
            likes=0,
        )
        result = _story_item_to_dict(item, "hl_0")
        assert result["id"] == ""
        assert result["likes"] == 0


# ---------------------------------------------------------------------------
# collect_highlights — success path
# ---------------------------------------------------------------------------


class TestCollectHighlightsSuccess:
    def test_no_highlights_returns_empty_items(self, tmp_path: Path) -> None:
        client = MagicMock()
        client.get_highlights.return_value = []
        profile = MagicMock(username="nobody")

        result = collect_highlights(client, profile, tmp_path)

        assert result.skipped is False
        assert result.skip_reason is None
        assert result.items == []
        assert result.file_path is not None

    def test_single_highlight_with_items(self, tmp_path: Path) -> None:
        item = _mock_highlight_item(mediaid=10, pk=10)
        hl = _mock_highlight(highlight_id="hl_1", title="Pets", items=[item])
        client = MagicMock()
        client.get_highlights.return_value = [hl]
        profile = MagicMock(username="petlover")

        with patch("ig_scraper.highlight_collection._download_media", return_value=[]):
            result = collect_highlights(client, profile, tmp_path)

        assert result.skipped is False
        assert len(result.items) == 1
        hl_dir = tmp_path / "highlights" / "hl_1"
        items_file = hl_dir / "items.json"
        assert items_file.exists()
        items_data = json.loads(items_file.read_text(encoding="utf-8"))
        assert len(items_data) == 1
        assert items_data[0]["id"] == "10"

    def test_multiple_highlights(self, tmp_path: Path) -> None:
        hl_a = _mock_highlight(highlight_id="a", items=[_mock_highlight_item()])
        hl_b = _mock_highlight(highlight_id="b", items=[_mock_highlight_item()])
        client = MagicMock()
        client.get_highlights.return_value = [hl_a, hl_b]
        profile = MagicMock(username="multi")

        with patch("ig_scraper.highlight_collection._download_media", return_value=[]):
            result = collect_highlights(client, profile, tmp_path)

        assert result.skipped is False
        assert len(result.items) == 2
        highlights_json = tmp_path / "highlights" / "highlights.json"
        assert highlights_json.exists()
        data = json.loads(highlights_json.read_text(encoding="utf-8"))
        assert len(data["highlights"]) == 2


# ---------------------------------------------------------------------------
# collect_highlights — skip / auth failure
# ---------------------------------------------------------------------------


class TestCollectHighlightsSkip:
    def test_none_account_dir_skips(self) -> None:
        client = MagicMock()
        profile = MagicMock(username="skip")

        result = collect_highlights(client, profile, None)

        assert result.skipped is True
        assert result.skip_reason == "no account_dir"
        assert result.items == []
        client.get_highlights.assert_not_called()

    def test_get_highlights_exception_skips(self, tmp_path: Path) -> None:
        from instaloader.exceptions import ConnectionException

        client = MagicMock()
        client.get_highlights.side_effect = ConnectionException("timeout")
        profile = MagicMock(username="fail")

        result = collect_highlights(client, profile, tmp_path)

        assert result.skipped is True
        assert result.skip_reason is not None
        assert result.items == []
