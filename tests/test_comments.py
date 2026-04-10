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
    def test_single_page_no_cursor(self):
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

    def test_multi_page_advances_through_iterator(self):
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

    def test_empty_iterator(self):
        mock_post = MagicMock()
        mock_post.get_comments.return_value = iter([])
        result = _fetch_all_comments(MagicMock(), mock_post, "https://e.com/p/e")
        assert result == []

    def test_preserves_partial_on_exception(self):
        mock_post = MagicMock()
        mock_post.get_comments.side_effect = Exception("instaloader error")
        result = _fetch_all_comments(MagicMock(), mock_post, "https://e.com/p/p")
        assert result == []

    def test_progress_logged_at_100_comments(self):
        """Test progress log fires at page 100 (when comment count hits 100)."""
        from unittest.mock import call

        mock_post = MagicMock()
        comments_list = [_mock_comment(comment_id=i) for i in range(101)]
        mock_post.get_comments.return_value = iter(comments_list)

        with patch("ig_scraper.comments.logger") as mock_logger:
            result = _fetch_all_comments(MagicMock(), mock_post, "https://e.com/p/100")
            assert len(result) == 101
            progress_calls = [
                c for c in mock_logger.info.call_args_list if "Comment fetch progress" in str(c)
            ]
            assert len(progress_calls) == 1
            assert "page=100" in str(progress_calls[0])

    def test_retryable_exception_caught_and_partial_returned(self):
        """Test ConnectionException is caught, partial comments returned."""
        from instaloader.exceptions import ConnectionException

        def comment_generator():
            for i in range(5):
                yield _mock_comment(comment_id=i)
            raise ConnectionException("Rate limited")

        mock_post = MagicMock()
        mock_post.get_comments.return_value = comment_generator()

        result = _fetch_all_comments(MagicMock(), mock_post, "https://e.com/p/retry")
        assert len(result) == 5

    def test_keyboard_interrupt_reraised(self):
        """Test KeyboardInterrupt is re-raised and not caught by generic exception handler."""
        mock_post = MagicMock()
        mock_post.get_comments.side_effect = KeyboardInterrupt
        with pytest.raises(KeyboardInterrupt):
            _fetch_all_comments(MagicMock(), mock_post, "https://e.com/p/kbi")
