"""Tests for comment pagination and conversion in comments.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ig_scraper.comments import _comment_to_dict, _fetch_all_comments, _fetch_comment_page
from ig_scraper.exceptions import RetryExhaustedError as _RetryExhaustedError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_comment(
    pk: int = 1,
    text: str = "Test",
    username: str = "user",
    full_name: str = "U",
    pic_url: str = "https://e.com/p.jpg",
    created_iso: str = "2024-01-01T00:00:00",
    likes: int = 0,
    replies: int = 0,
) -> MagicMock:
    user = MagicMock(username=username, full_name=full_name, profile_pic_url=pic_url)
    created = MagicMock()
    created.isoformat.return_value = created_iso
    return MagicMock(
        pk=pk,
        text=text,
        user=user,
        created_at_utc=created,
        like_count=likes,
        child_comment_count=replies,
    )


# ---------------------------------------------------------------------------
# _comment_to_dict
# ---------------------------------------------------------------------------


class TestCommentToDict:
    def test_converts_valid_comment(self):
        c = _mock_comment(
            pk=98765, text="Nice!", username="fan", full_name="Fan User", likes=42, replies=3
        )
        result = _comment_to_dict(c, "https://ig.com/p/ABC")
        assert result["id"] == "98765"
        assert result["text"] == "Nice!"
        assert result["owner_username"] == "fan"
        assert result["likes_count"] == 42
        assert result["replies_count"] == 3
        assert result["post_url"] == "https://ig.com/p/ABC"
        assert "#comment-98765" in result["comment_url"]

    def test_handles_missing_user(self):
        c = _mock_comment(pk=2, username="", full_name="", pic_url="")
        c.user = None
        result = _comment_to_dict(c, "https://e.com/p/X")
        assert result["owner_username"] == ""
        assert result["owner_full_name"] == ""
        assert result["owner_profile_pic_url"] == ""

    def test_handles_missing_text(self):
        c = _mock_comment(pk=3, text=None)
        result = _comment_to_dict(c, "https://e.com/p/Y")
        assert result["text"] == ""

    def test_handles_none_like_count(self):
        c = _mock_comment(pk=4, likes=None)
        result = _comment_to_dict(c, "https://e.com/p/Z")
        assert result["likes_count"] == 0


# ---------------------------------------------------------------------------
# _fetch_comment_page
# ---------------------------------------------------------------------------


class TestFetchCommentPage:
    @patch("ig_scraper.comments.time.perf_counter", return_value=0.0)
    @patch("ig_scraper.comments.time.sleep")
    @patch("ig_scraper.config.REQUEST_PAUSE_SECONDS", 0.001)
    def test_returns_comments_and_cursor(self, ms, mp):
        mock_client = MagicMock()
        mock_client.media_comments_chunk.return_value = ([MagicMock(), MagicMock()], "next123")
        comments, next_min = _fetch_comment_page(mock_client, "media_x")
        assert len(comments) == 2
        assert next_min == "next123"

    @patch("ig_scraper.comments.time.perf_counter", return_value=0.0)
    @patch("ig_scraper.comments.time.sleep")
    @patch("ig_scraper.config.REQUEST_PAUSE_SECONDS", 0.001)
    def test_returns_empty_list(self, ms, mp):
        mock_client = MagicMock()
        mock_client.media_comments_chunk.return_value = ([], None)
        comments, next_min = _fetch_comment_page(mock_client, "media_empty")
        assert comments == []
        assert next_min is None

    @patch("ig_scraper.comments.time.perf_counter", return_value=0.0)
    @patch("ig_scraper.comments.time.sleep")
    @patch("ig_scraper.config.REQUEST_PAUSE_SECONDS", 0.001)
    def test_passes_min_id(self, ms, mp):
        mock_client = MagicMock()
        mock_client.media_comments_chunk.return_value = ([], None)
        _fetch_comment_page(mock_client, "media_y", min_id="min_abc")
        mock_client.media_comments_chunk.assert_called_once_with(
            "media_y", max_amount=250, min_id="min_abc"
        )

    @patch("ig_scraper.comments.time.perf_counter", return_value=0.0)
    @patch("ig_scraper.comments.time.sleep")
    @patch("ig_scraper.config.REQUEST_PAUSE_SECONDS", 0.001)
    def test_custom_page_size(self, ms, mp):
        mock_client = MagicMock()
        mock_client.media_comments_chunk.return_value = ([], None)
        _fetch_comment_page(mock_client, "media_z", page_size=100)
        mock_client.media_comments_chunk.assert_called_once_with("media_z", max_amount=100)


# ---------------------------------------------------------------------------
# _fetch_all_comments
# ---------------------------------------------------------------------------


class TestFetchAllComments:
    @patch("ig_scraper.comments._sleep")
    @patch("ig_scraper.comments._fetch_comment_page")
    def test_single_page_no_cursor(self, mock_page, mock_sleep):
        mock_page.return_value = ([_mock_comment(pk=1), _mock_comment(pk=2)], None)
        result = _fetch_all_comments(MagicMock(), "m1", "https://e.com/p/1")
        assert len(result) == 2
        mock_page.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("ig_scraper.comments._sleep")
    @patch("ig_scraper.comments._fetch_comment_page")
    def test_multi_page_advances_cursor(self, mock_page, mock_sleep):
        mock_page.side_effect = [
            ([_mock_comment(pk=1)], "c2"),
            ([_mock_comment(pk=2)], "c3"),
            ([_mock_comment(pk=3)], None),
        ]
        result = _fetch_all_comments(MagicMock(), "mm", "https://e.com/p/m")
        assert len(result) == 3
        assert result[0]["id"] == "1"
        assert result[2]["id"] == "3"
        assert mock_page.call_count == 3

    @patch("ig_scraper.comments._sleep")
    @patch("ig_scraper.comments._fetch_comment_page")
    def test_stops_on_empty_page(self, mock_page, mock_sleep):
        mock_page.return_value = ([], None)
        result = _fetch_all_comments(MagicMock(), "me", "https://e.com/p/e")
        assert result == []
        mock_page.assert_called_once()

    @patch("ig_scraper.comments._sleep")
    @patch("ig_scraper.comments._fetch_comment_page")
    def test_stops_on_unchanged_cursor(self, mock_page, mock_sleep):
        # Break fires after page 2 is fetched (unchanged cursor detected on next iteration)
        mock_page.return_value = ([_mock_comment(pk=1)], "same_cursor")
        result = _fetch_all_comments(MagicMock(), "ms", "https://e.com/p/s")
        assert len(result) == 2
        assert mock_page.call_count == 2

    @patch("ig_scraper.comments._sleep")
    @patch("ig_scraper.comments._fetch_comment_page")
    def test_retry_exhausted_returns_empty(self, mock_page, mock_sleep):
        mock_page.side_effect = _RetryExhaustedError("failed")
        result = _fetch_all_comments(MagicMock(), "mf", "https://e.com/p/f")
        assert result == []

    @patch("ig_scraper.comments._sleep")
    @patch("ig_scraper.comments._fetch_comment_page")
    def test_retry_exhausted_preserves_partial(self, mock_page, mock_sleep):
        mock_page.side_effect = [
            ([_mock_comment(pk=10), _mock_comment(pk=11)], "c2"),
            _RetryExhaustedError("failed on page 2"),
        ]
        result = _fetch_all_comments(MagicMock(), "mp", "https://e.com/p/p")
        assert len(result) == 2
        assert result[0]["id"] == "10"
        assert result[1]["id"] == "11"
