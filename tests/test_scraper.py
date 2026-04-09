"""Tests for instagrapi_fallback.py — API interaction with retry logic."""

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
    """Tests for _media_permalink."""

    def test_reel_url_for_clips(self):
        """Test that clips product_type produces /reel/ URL."""
        mock_media = MagicMock()
        mock_media.code = "CLIP001"
        mock_media.product_type = "clips"

        url = _media_permalink("someuser", mock_media)
        assert "/reel/CLIP001/" in url

    def test_p_url_for_standard_posts(self):
        """Test standard post produces /p/ URL."""
        mock_media = MagicMock()
        mock_media.code = "POST123"
        mock_media.product_type = ""

        url = _media_permalink("someuser", mock_media)
        assert "/p/POST123/" in url

    def test_reel_url_when_product_type_is_none(self):
        """Test None product_type defaults to /p/."""
        mock_media = MagicMock()
        mock_media.code = "ABCDEF"
        mock_media.product_type = None

        url = _media_permalink("user", mock_media)
        assert "/p/ABCDEF/" in url


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
    """Tests for _download_media using mocked client."""

    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.config.REQUEST_PAUSE_SECONDS", 0.001)
    def test_downloads_photo_success(self, mock_sleep, tmp_path):
        """Test successful photo download returns filename."""
        mock_client = MagicMock()
        mock_media = MagicMock()
        mock_media.pk = 99999
        mock_media.code = "PHOTO123"
        mock_media.media_type = 1
        mock_media.product_type = ""
        mock_client.photo_download.return_value = str(tmp_path / "photo.jpg")

        result = _download_media(mock_client, mock_media, tmp_path)

        assert len(result) == 1
        mock_client.photo_download.assert_called_once_with(99999, folder=tmp_path)

    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.config.REQUEST_PAUSE_SECONDS", 0.001)
    def test_downloads_album_success(self, mock_sleep, tmp_path):
        """Test album download returns multiple filenames."""
        mock_client = MagicMock()
        mock_media = MagicMock()
        mock_media.pk = 88888
        mock_media.code = "ALBUM1"
        mock_media.media_type = 8
        mock_media.product_type = ""
        mock_client.album_download.return_value = [
            str(tmp_path / "img1.jpg"),
            str(tmp_path / "img2.jpg"),
        ]

        result = _download_media(mock_client, mock_media, tmp_path)

        assert len(result) == 2
        mock_client.album_download.assert_called_once_with(88888, folder=tmp_path)

    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.config.REQUEST_PAUSE_SECONDS", 0.001)
    def test_downloads_clip_success(self, mock_sleep, tmp_path):
        """Test clip (reel) download with product_type='clips'."""
        mock_client = MagicMock()
        mock_media = MagicMock()
        mock_media.pk = 77777
        mock_media.code = "REEL123"
        mock_media.media_type = 2
        mock_media.product_type = "clips"
        mock_client.clip_download.return_value = str(tmp_path / "clip.mp4")

        result = _download_media(mock_client, mock_media, tmp_path)

        assert len(result) == 1
        mock_client.clip_download.assert_called_once_with(77777, folder=tmp_path)

    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.config.REQUEST_PAUSE_SECONDS", 0.001)
    def test_download_raises_media_download_error_after_retries(self, mock_sleep, tmp_path):
        """Test MediaDownloadError raised after exhausting retries."""
        mock_client = MagicMock()
        mock_media = MagicMock()
        mock_media.pk = 66666
        mock_media.code = "FAIL123"
        mock_media.media_type = 1
        mock_media.product_type = ""
        mock_client.photo_download.side_effect = OSError("Network error")

        with pytest.raises(MediaDownloadError, match="FAIL123"):
            _download_media(mock_client, mock_media, tmp_path)

        assert mock_client.photo_download.call_count == MEDIA_DOWNLOAD_RETRIES

    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.config.REQUEST_PAUSE_SECONDS", 0.001)
    def test_download_retries_on_oserror(self, mock_sleep, tmp_path):
        """Test that OSError triggers retry before success."""
        mock_client = MagicMock()
        mock_media = MagicMock()
        mock_media.pk = 55555
        mock_media.code = "RETRY123"
        mock_media.media_type = 1
        mock_media.product_type = ""

        # Fail first two times, succeed on third
        mock_client.photo_download.side_effect = [
            OSError("fail 1"),
            OSError("fail 2"),
            str(tmp_path / "photo.jpg"),
        ]

        result = _download_media(mock_client, mock_media, tmp_path)

        assert len(result) == 1
        assert mock_client.photo_download.call_count == 3


class TestCommentToDict:
    """Tests for _comment_to_dict."""

    def test_converts_comment_fields(self):
        """Test comment fields are correctly extracted."""
        mock_user = MagicMock()
        mock_user.username = "commenter"
        mock_user.full_name = "Commenter Full"
        mock_user.profile_pic_url = "https://example.com/pic.jpg"

        mock_comment = MagicMock()
        mock_comment.pk = 12345
        mock_comment.text = "Great photo!"
        mock_comment.user = mock_user
        mock_comment.created_at_utc = MagicMock()
        mock_comment.created_at_utc.isoformat.return_value = "2024-01-15T10:30:00"
        mock_comment.like_count = 15
        mock_comment.child_comment_count = 2

        result = _comment_to_dict(mock_comment, "https://instagram.com/p/ABC123")

        assert result["id"] == "12345"
        assert result["text"] == "Great photo!"
        assert result["owner_username"] == "commenter"
        assert result["likes_count"] == 15
        assert result["replies_count"] == 2
        # _comment_to_dict does not include 'replies' key (not in the actual contract)
        assert "replies" not in result
        assert result["post_url"] == "https://instagram.com/p/ABC123"

    def test_comment_to_dict_does_not_include_replies_key(self):
        """Test that _comment_to_dict output does not include a 'replies' key."""
        mock_user = MagicMock()
        mock_user.username = "user"
        mock_user.full_name = ""
        mock_user.profile_pic_url = ""

        mock_comment = MagicMock(spec=[])
        mock_comment.pk = 1
        mock_comment.text = "Test"
        mock_comment.user = mock_user
        mock_comment.created_at_utc = None
        mock_comment.like_count = 0
        mock_comment.child_comment_count = 0

        result = _comment_to_dict(mock_comment, "https://example.com/p/1")

        # _comment_to_dict output does not include a 'replies' key
        assert "replies" not in result

    def test_handles_no_user(self):
        """Test _comment_to_dict handles missing user gracefully."""
        mock_comment = MagicMock(spec=[])
        mock_comment.pk = 999
        mock_comment.text = "Anonymous comment"
        mock_comment.user = None
        mock_comment.created_at_utc = None
        mock_comment.like_count = 0
        mock_comment.child_comment_count = 0

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
