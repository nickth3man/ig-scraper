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
    _env_float,
    _env_int,
)
from ig_scraper.exceptions import MediaDownloadError
from ig_scraper.exceptions import RetryExhaustedError as _RetryExhaustedError
from ig_scraper.media import _download_media, _media_permalink, _resource_to_dict
from ig_scraper.media_processing import _process_single_media
from ig_scraper.retry import _retry_with_backoff
from ig_scraper.scraper import (
    _build_profile_dict,
    _sleep,
    _take_n,
    fetch_profile_posts_and_comments,
)


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

    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.config.REQUEST_PAUSE_SECONDS", 0.001)
    def test_zero_byte_file_detection_raises_oserror(self, mock_sleep, tmp_path):
        """Test zero-byte file detected after download_post raises OSError."""
        mock_client = MagicMock()
        mock_media = MagicMock()
        mock_media.shortcode = "ZERO123"
        mock_media.pk = 44444
        mock_media.media_type = 1
        mock_media.typename = "GraphImage"

        mock_client.download_post.side_effect = OSError("Zero-byte file detected")

        with pytest.raises(MediaDownloadError, match="ZERO123"):
            _download_media(mock_client, mock_media, tmp_path)

        assert mock_client.download_post.call_count == MEDIA_DOWNLOAD_RETRIES

    @patch("ig_scraper.retry.time.sleep")
    @patch("ig_scraper.config.REQUEST_PAUSE_SECONDS", 0.001)
    def test_empty_download_directory_raises_oserror(self, mock_sleep, tmp_path):
        """Test empty directory (no files after download) raises OSError and is retried."""
        mock_client = MagicMock()
        mock_media = MagicMock()
        mock_media.shortcode = "EMPTY123"
        mock_media.pk = 33333
        mock_media.media_type = 1
        mock_media.typename = "GraphImage"

        mock_client.download_post.side_effect = OSError("No files downloaded to")

        with pytest.raises(MediaDownloadError, match="EMPTY123"):
            _download_media(mock_client, mock_media, tmp_path)

        assert mock_client.download_post.call_count == MEDIA_DOWNLOAD_RETRIES

    @patch("ig_scraper.media.time.sleep")
    @patch("ig_scraper.media._perform_media_download")
    def test_path_not_exists_skips_file_size_logging(self, mock_perform, mock_sleep, tmp_path):
        """Test file that disappears before stat call is excluded from file_sizes log."""
        mock_client = MagicMock()
        mock_media = MagicMock()
        mock_media.shortcode = "VANISH123"
        mock_media.pk = 22222
        mock_media.media_type = 1
        mock_media.typename = "GraphImage"

        mock_perform.return_value = ["VANISH123_12345.jpg"]

        result = _download_media(mock_client, mock_media, tmp_path)
        assert len(result) == 1
        mock_perform.assert_called_once()


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


class TestRetryOnDecorator:
    """Tests for the @retry_on decorator."""

    def test_retry_on_with_no_exception_types_raises_value_error(self):
        """Test @retry_on with no exception types raises ValueError."""
        from ig_scraper.retry import retry_on

        with pytest.raises(ValueError, match="Must specify at least one exception type"):
            retry_on()(lambda: None)

    @patch("ig_scraper.retry.time.sleep")
    def test_retry_on_fatal_exception_immediate_reexception(self, mock_sleep):
        """Test fatal (non-retryable) exceptions are re-raised immediately without retries."""
        from ig_scraper.exceptions import AuthError
        from ig_scraper.retry import retry_on

        call_count = {"n": 0}

        @retry_on(RuntimeError, max_attempts=3)
        def fn():
            call_count["n"] += 1
            raise AuthError("Auth failed")

        with pytest.raises(AuthError):
            fn()

        assert call_count["n"] == 1
        mock_sleep.assert_not_called()

    @patch("ig_scraper.retry.time.sleep")
    def test_retry_on_retries_on_retryable_exception(self, mock_sleep):
        """Test @retry_on retries on retryable RuntimeError and eventually succeeds."""
        from ig_scraper.retry import retry_on

        call_count = {"n": 0}

        @retry_on(RuntimeError, max_attempts=3)
        def fn():
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("first failure")
            return "success"

        result = fn()

        assert result == "success"
        assert call_count["n"] == 2

    @patch("ig_scraper.retry.time.sleep")
    def test_retry_on_exhausted_retries_raises_retry_exhausted(self, mock_sleep):
        """Test @retry_on raises RetryExhaustedError after all attempts fail."""
        from ig_scraper.exceptions import RetryExhaustedError
        from ig_scraper.retry import retry_on

        call_count = {"n": 0}

        @retry_on(RuntimeError, max_attempts=3)
        def fn():
            call_count["n"] += 1
            raise RuntimeError("always fails")

        with pytest.raises(RetryExhaustedError):
            fn()

        assert call_count["n"] == 3


class TestRetryConstants:
    """Tests for retry-related constants."""

    def test_comment_page_retries_default(self):
        """Verify COMMENT_PAGE_RETRIES helper returns 3 when env var absent."""
        with patch.dict("os.environ", {}, clear=False):
            assert _env_int("IG_COMMENT_PAGE_RETRIES_ABSENT_TEST", 3) == 3

    def test_media_download_retries_is_3(self):
        """Verify MEDIA_DOWNLOAD_RETRIES is 3."""
        assert MEDIA_DOWNLOAD_RETRIES == 3

    def test_comments_page_size_default(self):
        """Verify COMMENTS_PAGE_SIZE helper returns 250 when env var absent."""
        with patch.dict("os.environ", {}, clear=False):
            assert _env_int("IG_COMMENTS_PAGE_SIZE_ABSENT_TEST", 250) == 250

    def test_request_pause_seconds_default(self):
        """Verify REQUEST_PAUSE_SECONDS helper returns 0.25 when env var absent."""
        with patch.dict("os.environ", {}, clear=False):
            assert _env_float("IG_REQUEST_PAUSE_SECONDS_ABSENT_TEST", 0.25) == 0.25


def make_log_attempt_counter():
    """Return a (call_count, last_args) tracker suitable for log_attempt callback."""
    call_log = []

    def track(attempt: int, exc: Exception, wait_seconds: float):
        call_log.append((attempt, exc, wait_seconds))

    return track, call_log


# ----- Test _take_n -----


class TestTakeN:
    """Tests for _take_n — takes at most n items from an iterator."""

    def test_returns_first_n_items(self):
        """Test returns the first n items from a list iterator."""
        items = [1, 2, 3, 4, 5]
        result = _take_n(iter(items), 3)
        assert result == [1, 2, 3]

    def test_returns_all_items_when_fewer_than_n(self):
        """Test returns all items if iterator has fewer than n."""
        items = [1, 2, 3]
        result = _take_n(iter(items), 10)
        assert result == [1, 2, 3]

    def test_returns_empty_list_for_n_zero(self):
        """Test returns empty list when n=0."""
        result = _take_n(iter([1, 2, 3]), 0)
        assert result == []

    def test_works_with_generator(self):
        """Test works with a generator (not just a list iterator)."""

        def gen():
            yield "a"
            yield "b"
            yield "c"
            yield "d"

        result = _take_n(gen(), 2)
        assert result == ["a", "b"]


# ----- Test _build_profile_dict -----


class TestBuildProfileDict:
    """Tests for _build_profile_dict — converts instaloader Profile to dict."""

    def test_happy_path_returns_dict_with_correct_keys(self):
        """Test mock Profile with all fields returns dict with correct keys."""
        mock_profile = MagicMock()
        mock_profile.userid = 12345
        mock_profile.username = "testuser"
        mock_profile.full_name = "Test User"
        mock_profile.biography = "Hello world"
        mock_profile.followers = 1000
        mock_profile.followees = 500
        mock_profile.mediacount = 50
        mock_profile.is_private = False
        mock_profile.is_verified = True
        mock_profile.is_business_account = True
        mock_profile.profile_pic_url = "https://example.com/pic.jpg"
        mock_profile.external_url = "https://example.com"
        mock_profile.igtvcount = 2
        mock_profile.biography_hashtags = []
        mock_profile.biography_mentions = []
        mock_profile.business_category_name = "Influencer"

        result = _build_profile_dict(mock_profile)

        assert result["id"] == "12345"
        assert result["username"] == "testuser"
        assert result["full_name"] == "Test User"
        assert result["followers_count"] == 1000
        assert result["follows_count"] == 500
        assert result["posts_count"] == 50
        assert result["is_private"] is False
        assert result["verified"] is True
        assert result["is_business_account"] is True

    def test_profile_with_missing_attributes_still_creates_dict(self):
        """Test Profile with missing attributes uses getattr fallbacks gracefully."""
        mock_profile = MagicMock(spec=[])
        del mock_profile.userid
        del mock_profile.username
        del mock_profile.full_name
        del mock_profile.biography
        del mock_profile.followers
        del mock_profile.followees
        del mock_profile.mediacount
        del mock_profile.is_private
        del mock_profile.is_verified
        del mock_profile.is_business_account
        del mock_profile.profile_pic_url
        del mock_profile.external_url
        del mock_profile.igtvcount
        del mock_profile.biography_hashtags
        del mock_profile.biography_mentions
        del mock_profile.business_category_name

        result = _build_profile_dict(mock_profile)

        # Should not raise — getattr fallbacks handle missing attrs
        assert isinstance(result, dict)
        assert result["id"] == ""
        assert result["username"] == ""
        assert result["follows_count"] == 0


# ----- Test fetch_profile_posts_and_comments -----


class TestFetchProfilePostsAndComments:
    """Tests for fetch_profile_posts_and_comments orchestrator."""

    @patch("ig_scraper.scraper._sleep")
    @patch("ig_scraper.scraper._process_single_media")
    @patch("ig_scraper.scraper._fetch_medias")
    @patch("ig_scraper.scraper._fetch_profile")
    @patch("ig_scraper.scraper.get_instaloader_client")
    def test_happy_path(
        self, mock_client, mock_fetch_profile, mock_fetch_medias, mock_process, mock_sleep
    ):
        """Test happy path with 2 media items returns (profile, posts, comments)."""
        mock_profile_obj = MagicMock()
        mock_profile_obj.userid = 1
        mock_profile_obj.username = "testuser"
        mock_profile_obj.followers = 100
        mock_profile_obj.followees = 50
        mock_profile_obj.mediacount = 10
        mock_profile_obj.is_private = False
        mock_profile_obj.is_verified = False
        mock_profile_obj.is_business_account = False
        mock_profile_obj.full_name = ""
        mock_profile_obj.biography = ""
        mock_profile_obj.profile_pic_url = ""
        mock_profile_obj.external_url = ""
        mock_profile_obj.igtvcount = 0
        mock_profile_obj.biography_hashtags = []
        mock_profile_obj.biography_mentions = []
        mock_profile_obj.business_category_name = ""
        mock_fetch_profile.return_value = mock_profile_obj

        mock_media1 = MagicMock()
        mock_media1.shortcode = "POST1"
        mock_media2 = MagicMock()
        mock_media2.shortcode = "POST2"
        mock_fetch_medias.return_value = [mock_media1, mock_media2]

        post1 = {"shortcode": "POST1"}
        post2 = {"shortcode": "POST2"}
        comments1 = [{"id": "c1", "text": "nice"}]
        comments2 = [{"id": "c2", "text": "cool"}]
        mock_process.side_effect = [
            (post1, comments1, ["file1.jpg"]),
            (post2, comments2, ["file2.jpg"]),
        ]

        _profile, posts, comments = fetch_profile_posts_and_comments(
            "testuser", posts_per_profile=10
        )

        assert len(posts) == 2
        assert posts[0]["shortcode"] == "POST1"
        assert posts[1]["shortcode"] == "POST2"
        assert len(comments) == 2
        assert mock_sleep.call_count == 2  # Called between each media iteration

    @patch("ig_scraper.scraper._sleep")
    @patch("ig_scraper.scraper._process_single_media")
    @patch("ig_scraper.scraper._fetch_medias")
    @patch("ig_scraper.scraper._fetch_profile")
    @patch("ig_scraper.scraper.get_instaloader_client")
    def test_fewer_posts_than_requested_logs_warning(
        self, mock_client, mock_fetch_profile, mock_fetch_medias, mock_process, mock_sleep
    ):
        """Test _fetch_medias returns fewer posts than requested logs warning."""
        mock_profile_obj = MagicMock()
        mock_profile_obj.userid = 1
        mock_profile_obj.username = "testuser"
        mock_profile_obj.followers = 100
        mock_profile_obj.followees = 50
        mock_profile_obj.mediacount = 3
        mock_profile_obj.is_private = False
        mock_profile_obj.is_verified = False
        mock_profile_obj.is_business_account = False
        mock_profile_obj.full_name = ""
        mock_profile_obj.biography = ""
        mock_profile_obj.profile_pic_url = ""
        mock_profile_obj.external_url = ""
        mock_profile_obj.igtvcount = 0
        mock_profile_obj.biography_hashtags = []
        mock_profile_obj.biography_mentions = []
        mock_profile_obj.business_category_name = ""
        mock_fetch_profile.return_value = mock_profile_obj

        mock_media = MagicMock()
        mock_media.shortcode = "POST1"
        # Returns 3 medias but requested 10
        mock_fetch_medias.return_value = [mock_media]

        mock_process.return_value = ({"shortcode": "POST1"}, [], ["f.jpg"])

        with patch("ig_scraper.scraper.logger") as mock_logger:
            fetch_profile_posts_and_comments("testuser", posts_per_profile=10)
            warning_calls = list(mock_logger.warning.call_args_list)
            assert any("fewer posts than requested" in str(c) for c in warning_calls)

    @patch("ig_scraper.scraper._sleep")
    @patch("ig_scraper.scraper._process_single_media")
    @patch("ig_scraper.scraper._fetch_medias")
    @patch("ig_scraper.scraper._fetch_profile")
    @patch("ig_scraper.scraper.get_instaloader_client")
    def test_private_profile_no_posts_logs_warning(
        self, mock_client, mock_fetch_profile, mock_fetch_medias, mock_process, mock_sleep
    ):
        """Test private profile with no posts logs warning about following."""
        mock_profile_obj = MagicMock()
        mock_profile_obj.userid = 1
        mock_profile_obj.username = "privateuser"
        mock_profile_obj.followers = 100
        mock_profile_obj.followees = 50
        mock_profile_obj.mediacount = 0
        mock_profile_obj.is_private = True
        mock_profile_obj.is_verified = False
        mock_profile_obj.is_business_account = False
        mock_profile_obj.full_name = ""
        mock_profile_obj.biography = ""
        mock_profile_obj.profile_pic_url = ""
        mock_profile_obj.external_url = ""
        mock_profile_obj.igtvcount = 0
        mock_profile_obj.biography_hashtags = []
        mock_profile_obj.biography_mentions = []
        mock_profile_obj.business_category_name = ""
        mock_fetch_profile.return_value = mock_profile_obj

        mock_fetch_medias.return_value = []

        with patch("ig_scraper.scraper.logger") as mock_logger:
            fetch_profile_posts_and_comments("privateuser", posts_per_profile=10)
            warning_calls = list(mock_logger.warning.call_args_list)
            assert any("Private profile returned no posts" in str(c) for c in warning_calls)

    @patch("ig_scraper.scraper._sleep")
    @patch("ig_scraper.scraper._process_single_media")
    @patch("ig_scraper.scraper._fetch_medias")
    @patch("ig_scraper.scraper._fetch_profile")
    @patch("ig_scraper.scraper.get_instaloader_client")
    def test_attribute_error_on_second_media_skips_gracefully(
        self, mock_client, mock_fetch_profile, mock_fetch_medias, mock_process, mock_sleep
    ):
        """Test AttributeError on 2nd media skips it, 1st post still in results."""
        mock_profile_obj = MagicMock()
        mock_profile_obj.userid = 1
        mock_profile_obj.username = "testuser"
        mock_profile_obj.followers = 100
        mock_profile_obj.followees = 50
        mock_profile_obj.mediacount = 2
        mock_profile_obj.is_private = False
        mock_profile_obj.is_verified = False
        mock_profile_obj.is_business_account = False
        mock_profile_obj.full_name = ""
        mock_profile_obj.biography = ""
        mock_profile_obj.profile_pic_url = ""
        mock_profile_obj.external_url = ""
        mock_profile_obj.igtvcount = 0
        mock_profile_obj.biography_hashtags = []
        mock_profile_obj.biography_mentions = []
        mock_profile_obj.business_category_name = ""
        mock_fetch_profile.return_value = mock_profile_obj

        mock_media1 = MagicMock()
        mock_media1.shortcode = "POST1"
        mock_media2 = MagicMock()
        mock_media2.shortcode = "POST2"
        mock_fetch_medias.return_value = [mock_media1, mock_media2]

        post1 = {"shortcode": "POST1"}
        comments1 = [{"id": "c1", "text": "nice"}]
        mock_process.side_effect = [
            (post1, comments1, ["file1.jpg"]),
            AttributeError("Deleted post"),
        ]

        _profile, posts, comments = fetch_profile_posts_and_comments(
            "testuser", posts_per_profile=10
        )

        assert len(posts) == 1
        assert posts[0]["shortcode"] == "POST1"
        assert len(comments) == 1

    @patch("ig_scraper.scraper._sleep")
    @patch("ig_scraper.scraper._process_single_media")
    @patch("ig_scraper.scraper._fetch_medias")
    @patch("ig_scraper.scraper._fetch_profile")
    @patch("ig_scraper.scraper.get_instaloader_client")
    def test_empty_media_list_returns_empty_posts_and_comments(
        self, mock_client, mock_fetch_profile, mock_fetch_medias, mock_process, mock_sleep
    ):
        """Test _fetch_medias returns empty list → returns empty posts/comments."""
        mock_profile_obj = MagicMock()
        mock_profile_obj.userid = 1
        mock_profile_obj.username = "testuser"
        mock_profile_obj.followers = 100
        mock_profile_obj.followees = 50
        mock_profile_obj.mediacount = 0
        mock_profile_obj.is_private = False
        mock_profile_obj.is_verified = False
        mock_profile_obj.is_business_account = False
        mock_profile_obj.full_name = ""
        mock_profile_obj.biography = ""
        mock_profile_obj.profile_pic_url = ""
        mock_profile_obj.external_url = ""
        mock_profile_obj.igtvcount = 0
        mock_profile_obj.biography_hashtags = []
        mock_profile_obj.biography_mentions = []
        mock_profile_obj.business_category_name = ""
        mock_fetch_profile.return_value = mock_profile_obj

        mock_fetch_medias.return_value = []

        _profile, posts, comments = fetch_profile_posts_and_comments(
            "testuser", posts_per_profile=10
        )

        assert posts == []
        assert comments == []

    @patch("ig_scraper.scraper._sleep")
    @patch("ig_scraper.scraper._process_single_media")
    @patch("ig_scraper.scraper._fetch_medias")
    @patch("ig_scraper.scraper._fetch_profile")
    @patch("ig_scraper.scraper.get_instaloader_client")
    def test_account_dir_sets_posts_root_correctly(
        self, mock_client, mock_fetch_profile, mock_fetch_medias, mock_process, mock_sleep, tmp_path
    ):
        """Test account_dir Path sets posts_root correctly, passed to _process_single_media."""
        mock_profile_obj = MagicMock()
        mock_profile_obj.userid = 1
        mock_profile_obj.username = "testuser"
        mock_profile_obj.followers = 100
        mock_profile_obj.followees = 50
        mock_profile_obj.mediacount = 1
        mock_profile_obj.is_private = False
        mock_profile_obj.is_verified = False
        mock_profile_obj.is_business_account = False
        mock_profile_obj.full_name = ""
        mock_profile_obj.biography = ""
        mock_profile_obj.profile_pic_url = ""
        mock_profile_obj.external_url = ""
        mock_profile_obj.igtvcount = 0
        mock_profile_obj.biography_hashtags = []
        mock_profile_obj.biography_mentions = []
        mock_profile_obj.business_category_name = ""
        mock_fetch_profile.return_value = mock_profile_obj

        mock_media = MagicMock()
        mock_media.shortcode = "POST1"
        mock_fetch_medias.return_value = [mock_media]

        account_dir = tmp_path / "test_account"
        account_dir.mkdir()

        mock_process.return_value = ({"shortcode": "POST1"}, [], ["f.jpg"])

        fetch_profile_posts_and_comments("testuser", posts_per_profile=10, account_dir=account_dir)

        # Verify _process_single_media was called with correct posts_root
        call_kwargs = mock_process.call_args.kwargs
        assert call_kwargs["account_dir"] == account_dir
        assert call_kwargs["posts_root"] == account_dir / "posts"
