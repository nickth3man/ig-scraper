"""Tests for comment pagination and conversion in comments.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ig_scraper.comments import _comment_to_dict, _fetch_all_comments


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_comment(
    comment_id: int | str = 1,
    text: str | None = "Test",
    username: str = "user",
    full_name: str = "U",
    pic_url: str = "https://e.com/p.jpg",
    created_iso: str = "2024-01-01T00:00:00",
    likes_count: int | None = 0,
    answers_count: int = 0,
) -> MagicMock:
    """Build a mock instaloader Comment with owner and standard fields."""
    owner = MagicMock(username=username, full_name=full_name, profile_pic_url=pic_url)
    created = MagicMock()
    created.isoformat.return_value = created_iso
    return MagicMock(
        id=comment_id,
        text=text,
        owner=owner,
        created_at_utc=created,
        likes_count=likes_count,
        answers_count=answers_count,
    )


# ---------------------------------------------------------------------------
# _comment_to_dict
# ---------------------------------------------------------------------------


class TestCommentToDict:
    def test_converts_valid_comment(self):
        c = _mock_comment(
            comment_id=98765,
            text="Nice!",
            username="fan",
            full_name="Fan User",
            likes_count=42,
            answers_count=3,
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
        c = _mock_comment(comment_id=2, username="", full_name="", pic_url="")
        c.owner = None
        result = _comment_to_dict(c, "https://e.com/p/X")
        assert result["owner_username"] == ""
        assert result["owner_full_name"] == ""
        assert result["owner_profile_pic_url"] == ""

    def test_handles_missing_text(self):
        c = _mock_comment(comment_id=3, text=None)
        result = _comment_to_dict(c, "https://e.com/p/Y")
        assert result["text"] == ""

    def test_handles_none_like_count(self):
        c = _mock_comment(comment_id=4, likes_count=None)
        result = _comment_to_dict(c, "https://e.com/p/Z")
        assert result["likes_count"] == 0


# ---------------------------------------------------------------------------
# _fetch_all_comments
# ---------------------------------------------------------------------------


class TestFetchAllComments:
    @patch("ig_scraper.comments._sleep")
    def test_single_page_no_cursor(self, mock_sleep):
        mock_post = MagicMock()
        mock_post.get_comments.return_value = iter(
            [
                _mock_comment(comment_id=1),
                _mock_comment(comment_id=2),
            ]
        )
        result = _fetch_all_comments(MagicMock(), mock_post, "https://e.com/p/1")
        assert len(result) == 2
        mock_post.get_comments.assert_called_once()
        assert mock_sleep.call_count == 2

    @patch("ig_scraper.comments._sleep")
    def test_multi_page_advances_through_iterator(self, mock_sleep):
        mock_post = MagicMock()
        mock_post.get_comments.return_value = iter(
            [
                _mock_comment(comment_id=1),
                _mock_comment(comment_id=2),
                _mock_comment(comment_id=3),
            ]
        )
        result = _fetch_all_comments(MagicMock(), mock_post, "https://e.com/p/m")
        assert len(result) == 3
        assert result[0]["id"] == "1"
        assert result[2]["id"] == "3"

    @patch("ig_scraper.comments._sleep")
    def test_empty_iterator(self, mock_sleep):
        mock_post = MagicMock()
        mock_post.get_comments.return_value = iter([])
        result = _fetch_all_comments(MagicMock(), mock_post, "https://e.com/p/e")
        assert result == []
        mock_sleep.assert_not_called()

    @patch("ig_scraper.comments._sleep")
    def test_preserves_partial_on_exception(self, mock_sleep):
        mock_post = MagicMock()
        mock_post.get_comments.side_effect = Exception("instaloader error")
        result = _fetch_all_comments(MagicMock(), mock_post, "https://e.com/p/p")
        assert result == []
