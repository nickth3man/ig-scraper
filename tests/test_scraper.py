"""Tests for scraper module — instaloader-based API interaction with retry logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ig_scraper.comments import _comment_to_dict
from ig_scraper.config import (
    COMMENTS_PAGE_SIZE,
    COMMENT_PAGE_RETRIES,
    MEDIA_DOWNLOAD_RETRIES,
    REQUEST_PAUSE_SECONDS,
)
from ig_scraper.exceptions import MediaDownloadError
from ig_scraper.exceptions import RetryExhaustedError as _RetryExhaustedError
from ig_scraper.media import _download_media, _media_permalink, _resource_to_dict
from ig_scraper.retry import _retry_with_backoff


# ----- helpers for mock logging callbacks -----

# ----- Test _retry_with_backoff -----


class TestRetryWithBackoff:
    """Tests for the _retry_with_backoff retry decorator."""

    def test_succeeds_on_first_attempt(self):
        """Test function succeeds immediately without retries."""
        counter = {"calls": 0}

        def fn():
            counter["calls"] += 1
            return "success"

        log_attempt, call_log = make_log_attempt_counter()
        result = _retry_with_backoff(
            fn, retries=3, exceptions=(ValueError,), log_attempt=log_attempt
        )

        assert result == "success"
        assert counter["calls"] == 1
        assert call_log == []  # No failures, so no logging

    def test_retries_on_specified_exception_and_succeeds(self):
        """Test retry on ValueError, succeeds on second attempt."""
        counter = {"calls": 0}

        def fn():
            counter["calls"] += 1
            if counter["calls"] == 1:
                raise ValueError("first failure")
            return "worked"

        log_attempt, call_log = make_log_attempt_counter()
        result = _retry_with_backoff(
            fn, retries=3, exceptions=(ValueError,), log_attempt=log_attempt
        )

        assert result == "worked"
        assert counter["calls"] == 2
        assert len(call_log) == 1
        assert call_log[0][0] == 1  # attempt 1 failed

    def test_raises_retry_exhausted_when_all_attempts_fail(self):
        """Test that _RetryExhaustedError is raised after all retries."""
        call_count = {"n": 0}

        def fn():
            call_count["n"] += 1
            raise RuntimeError("always fails")

        log_attempt, _ = make_log_attempt_counter()
        with pytest.raises(_RetryExhaustedError, match="always fails"):
            _retry_with_backoff(fn, retries=3, exceptions=(RuntimeError,), log_attempt=log_attempt)

        assert call_count["n"] == 3

    def test_only_retries_specified_exception_types(self):
        """Test that non-specified exceptions are not retried."""
        call_count = {"n": 0}

        def fn():
            call_count["n"] += 1
            raise TypeError("unexpected type")

        log_attempt, _ = make_log_attempt_counter()
        with pytest.raises(TypeError, match="unexpected type"):
            _retry_with_backoff(fn, retries=3, exceptions=(ValueError,), log_attempt=log_attempt)

        assert call_count["n"] == 1  # No retries — TypeError not in exceptions tuple

    def test_exponential_backoff_wait_increases(self):
        """Test that wait time grows exponentially with attempt number."""
        call_count = {"n": 0}
        wait_times = []

        def fn():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise RuntimeError(f"fail {call_count['n']}")
            return "ok"

        def track(attempt, exc, wait_seconds):
            wait_times.append(wait_seconds)

        _retry_with_backoff(fn, retries=3, exceptions=(RuntimeError,), log_attempt=track)

        assert len(wait_times) == 2
        # Each wait should be roughly 2x the previous (exponential backoff)
        assert wait_times[1] > wait_times[0]


class TestMediaPermalink:
    """Tests for _media_permalink using instaloader shortcode-based URLs."""

    def test_p_url_for_standard_posts(self):
        """Test standard post produces /p/ URL using instaloader shortcode."""
        mock_media = MagicMock()
        mock_media.shortcode = "POST123"

        url = _media_permalink("someuser", mock_media)
        assert "/p/POST123/" in url

    def test_p_url_for_reels(self):
        """Test reel/clip posts still use /p/ URL (instaloader convention)."""
        mock_media = MagicMock()
        mock_media.shortcode = "CLIP001"

        url = _media_permalink("someuser", mock_media)
        assert "/p/CLIP001/" in url


class TestResourceToDict:
    """Tests for _resource_to_dict."""

    def test_converts_all_fields(self):
        """Test all resource fields are stringified."""
        mock_res = MagicMock()
        mock_res.pk = 12345
        mock_res.media_type = 1
        mock_res.thumbnail_url = "https://example.com/thumb.jpg"
        mock_res.video_url = ""

        result = _resource_to_dict(mock_res)

        assert result["pk"] == "12345"
        assert result["media_type"] == 1
        assert result["thumbnail_url"] == "https://example.com/thumb.jpg"
        assert result["video_url"] == ""

    def test_handles_missing_attributes(self):
        """Test missing attributes default to safe values."""
        mock_res = MagicMock(spec=[])
        result = _resource_to_dict(mock_res)

        assert result["pk"] == ""
        assert result["media_type"] == 0
        assert result["thumbnail_url"] == ""
        assert result["video_url"] == ""


class TestDownloadMedia:
    """Tests for _download_media using instaloader's download_post."""

    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.config.REQUEST_PAUSE_SECONDS", 0.001)
    def test_downloads_photo_success(self, mock_sleep, tmp_path):
        """Test successful photo download via instaloader download_post."""
        mock_client = MagicMock()
        mock_media = MagicMock()
        mock_media.shortcode = "PHOTO123"
        mock_media.pk = 99999
        mock_media.media_type = 1
        mock_media.typename = "GraphImage"
        # Simulate files written to target directory by download_post
        photo_file = tmp_path / "PHOTO123_12345.jpg"
        photo_file.write_bytes(b"fake image content")

        result = _download_media(mock_client, mock_media, tmp_path)

        assert len(result) == 1
        assert "PHOTO123" in result[0]
        mock_client.download_post.assert_called_once()

    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.config.REQUEST_PAUSE_SECONDS", 0.001)
    def test_downloads_album_success(self, mock_sleep, tmp_path):
        """Test album download returns multiple filenames."""
        mock_client = MagicMock()
        mock_media = MagicMock()
        mock_media.shortcode = "ALBUM1"
        mock_media.pk = 88888
        mock_media.media_type = 8
        mock_media.typename = "GraphAlbum"
        album_file1 = tmp_path / "ALBUM1_1.jpg"
        album_file1.write_bytes(b"album image 1")
        album_file2 = tmp_path / "ALBUM1_2.jpg"
        album_file2.write_bytes(b"album image 2")

        result = _download_media(mock_client, mock_media, tmp_path)

        assert len(result) == 2
        mock_client.download_post.assert_called_once()

    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.config.REQUEST_PAUSE_SECONDS", 0.001)
    def test_downloads_clip_success(self, mock_sleep, tmp_path):
        """Test clip (reel) download via instaloader."""
        mock_client = MagicMock()
        mock_media = MagicMock()
        mock_media.shortcode = "REEL123"
        mock_media.pk = 77777
        mock_media.media_type = 2
        mock_media.typename = "GraphVideo"
        video_file = tmp_path / "REEL123_12345.mp4"
        video_file.write_bytes(b"fake video content")

        result = _download_media(mock_client, mock_media, tmp_path)

        assert len(result) == 1
        mock_client.download_post.assert_called_once()

    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.config.REQUEST_PAUSE_SECONDS", 0.001)
    def test_download_raises_media_download_error_after_retries(self, mock_sleep, tmp_path):
        """Test MediaDownloadError raised after exhausting retries."""
        mock_client = MagicMock()
        mock_media = MagicMock()
        mock_media.shortcode = "FAIL123"
        mock_media.pk = 66666
        mock_media.media_type = 1
        mock_media.typename = "GraphImage"
        mock_client.download_post.side_effect = OSError("Network error")

        with pytest.raises(MediaDownloadError, match="FAIL123"):
            _download_media(mock_client, mock_media, tmp_path)

        assert mock_client.download_post.call_count == MEDIA_DOWNLOAD_RETRIES

    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.config.REQUEST_PAUSE_SECONDS", 0.001)
    def test_download_retries_on_oserror(self, mock_sleep, tmp_path):
        """Test that OSError triggers retry before success."""
        mock_client = MagicMock()
        mock_media = MagicMock()
        mock_media.shortcode = "RETRY123"
        mock_media.pk = 55555
        mock_media.media_type = 1
        mock_media.typename = "GraphImage"

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise OSError(f"fail {call_count[0]}")
            (tmp_path / "RETRY123_12345.jpg").write_bytes(b"valid content after retry")

        mock_client.download_post.side_effect = side_effect

        result = _download_media(mock_client, mock_media, tmp_path)

        assert len(result) == 1
        assert mock_client.download_post.call_count == 3


class TestCommentToDict:
    """Tests for _comment_to_dict using instaloader comment fields."""

    def test_converts_comment_fields(self):
        """Test comment fields are correctly extracted from instaloader Comment."""
        mock_owner = MagicMock()
        mock_owner.username = "commenter"
        mock_owner.full_name = "Commenter Full"
        mock_owner.profile_pic_url = "https://example.com/pic.jpg"

        mock_comment = MagicMock()
        mock_comment.id = 12345
        mock_comment.text = "Great photo!"
        mock_comment.owner = mock_owner
        mock_comment.created_at_utc = MagicMock()
        mock_comment.created_at_utc.isoformat.return_value = "2024-01-15T10:30:00"
        mock_comment.likes_count = 15
        mock_comment.answers_count = 2

        result = _comment_to_dict(mock_comment, "https://instagram.com/p/ABC123")

        assert result["id"] == "12345"
        assert result["text"] == "Great photo!"
        assert result["owner_username"] == "commenter"
        assert result["likes_count"] == 15
        assert result["replies_count"] == 2
        assert "replies" not in result
        assert result["post_url"] == "https://instagram.com/p/ABC123"

    def test_comment_to_dict_does_not_include_replies_key(self):
        """Test that _comment_to_dict output does not include a 'replies' key."""
        mock_owner = MagicMock()
        mock_owner.username = "user"
        mock_owner.full_name = ""
        mock_owner.profile_pic_url = ""

        mock_comment = MagicMock(spec=[])
        mock_comment.id = 1
        mock_comment.text = "Test"
        mock_comment.owner = mock_owner
        mock_comment.created_at_utc = None
        mock_comment.likes_count = 0
        mock_comment.answers_count = 0

        result = _comment_to_dict(mock_comment, "https://example.com/p/1")

        assert "replies" not in result

    def test_handles_no_owner(self):
        """Test _comment_to_dict handles missing owner gracefully."""
        mock_comment = MagicMock(spec=[])
        mock_comment.id = 999
        mock_comment.text = "Anonymous comment"
        mock_comment.owner = None
        mock_comment.created_at_utc = None
        mock_comment.likes_count = 0
        mock_comment.answers_count = 0

        result = _comment_to_dict(mock_comment, "https://example.com/p/999")

        assert result["owner_username"] == ""
        assert result["owner_full_name"] == ""
        assert result["owner_profile_pic_url"] == ""


class TestRetryConstants:
    """Tests for retry-related constants."""

    def test_comment_page_retries_is_3(self):
        """Verify COMMENT_PAGE_RETRIES is 3."""
        assert COMMENT_PAGE_RETRIES == 3

    def test_media_download_retries_is_3(self):
        """Verify MEDIA_DOWNLOAD_RETRIES is 3."""
        assert MEDIA_DOWNLOAD_RETRIES == 3

    def test_comments_page_size_is_250(self):
        """Verify COMMENTS_PAGE_SIZE is 250."""
        assert COMMENTS_PAGE_SIZE == 250

    def test_request_pause_seconds_is_025(self):
        """Verify REQUEST_PAUSE_SECONDS is 0.25."""
        assert REQUEST_PAUSE_SECONDS == 0.25


def make_log_attempt_counter():
    """Return a (call_count, last_args) tracker suitable for log_attempt callback."""
    call_log = []

    def track(attempt: int, exc: Exception, wait_seconds: float):
        call_log.append((attempt, exc, wait_seconds))

    return track, call_log
