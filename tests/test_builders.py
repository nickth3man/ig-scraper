"""Tests for builders.py and _process_single_media."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ig_scraper.exceptions import MediaDownloadError
from ig_scraper.media_processing import _build_post_dict
from ig_scraper.scraper import (
    _build_profile_dict,
    _log_medias_fetch_attempt,
    _log_profile_fetch_attempt,
)


class TestBuildProfileDict:
    """Tests for _build_profile_dict function."""

    def test_all_attributes(self):
        """Test with mock user object having all attributes."""
        mock_user = MagicMock()
        mock_user.pk = 12345
        mock_user.username = "testuser"
        mock_user.full_name = "Test User"
        mock_user.biography = "Test bio"
        mock_user.follower_count = 1000
        mock_user.following_count = 500
        mock_user.media_count = 50
        mock_user.is_verified = True
        mock_user.is_business = False
        mock_user.profile_pic_url = "https://example.com/pic.jpg"
        mock_user.external_url = "https://example.com"

        result = _build_profile_dict(mock_user)

        assert result["id"] == "12345"
        assert result["username"] == "testuser"
        assert result["full_name"] == "Test User"
        assert result["followers_count"] == 1000
        assert result["follows_count"] == 500
        assert result["posts_count"] == 50
        assert result["verified"] is True
        assert result["is_business_account"] is False
        assert result["profile_pic_url"] == "https://example.com/pic.jpg"
        assert result["external_url"] == "https://example.com"

    def test_pk_coerced_to_string(self):
        """Test that pk is coerced to string."""
        mock_user = MagicMock()
        mock_user.pk = 99999
        mock_user.username = "user"
        mock_user.full_name = ""
        mock_user.biography = ""
        mock_user.follower_count = 0
        mock_user.following_count = 0
        mock_user.media_count = 0
        mock_user.is_verified = False
        mock_user.is_business = False
        mock_user.profile_pic_url = None
        mock_user.external_url = None

        result = _build_profile_dict(mock_user)
        assert result["id"] == "99999"
        assert isinstance(result["id"], str)

    def test_none_optional_fields(self):
        """Test with None values for optional fields."""
        mock_user = MagicMock()
        mock_user.pk = 1
        mock_user.username = "user"
        mock_user.full_name = None
        mock_user.biography = None
        mock_user.follower_count = 0
        mock_user.following_count = 0
        mock_user.media_count = 0
        mock_user.is_verified = False
        mock_user.is_business = False
        mock_user.profile_pic_url = None
        mock_user.external_url = None

        result = _build_profile_dict(mock_user)
        assert result["profile_pic_url"] == ""
        assert result["external_url"] == ""


class TestBuildPostDict:
    """Tests for _build_post_dict function."""

    def test_mock_media_object(self):
        """Test with mock media object."""
        mock_media = MagicMock()
        mock_media.pk = 12345
        mock_media.code = "ABC123"
        mock_media.product_type = "post"
        mock_media.caption_text = "Test caption"
        mock_media.comment_count = 10
        mock_media.like_count = 100
        mock_media.taken_at.isoformat.return_value = "2024-01-15T10:30:00"
        mock_media.media_type = 1
        mock_media.resources = []

        result = _build_post_dict(
            media=mock_media,
            username="testuser",
            user_full_name="Test User",
            user_pk="12345",
            media_url="https://instagram.com/p/ABC123/",
            media_files=[],
            post_folder=None,
            account_dir=None,
        )

        assert result["id"] == "12345"
        assert result["short_code"] == "ABC123"
        assert result["caption"] == "Test caption"
        assert result["comment_count"] == 10
        assert result["like_count"] == 100

    def test_resources_converted(self):
        """Test that resources are converted correctly."""
        mock_res = MagicMock()
        mock_res.pk = 999
        mock_res.media_type = 1
        mock_res.thumbnail_url = "https://example.com/thumb.jpg"
        mock_res.video_url = ""

        mock_media = MagicMock()
        mock_media.pk = 12345
        mock_media.code = "ABC123"
        mock_media.product_type = ""
        mock_media.caption_text = ""
        mock_media.comment_count = 0
        mock_media.like_count = 0
        mock_media.taken_at.isoformat.return_value = ""
        mock_media.media_type = 8
        mock_media.resources = [mock_res]

        result = _build_post_dict(
            media=mock_media,
            username="user",
            user_full_name="",
            user_pk="1",
            media_url="",
            media_files=[],
            post_folder=None,
            account_dir=None,
        )

        assert len(result["resources"]) == 1

    def test_post_folder_empty_when_no_account_dir(self):
        """Test post_folder is empty when account_dir is None."""
        mock_media = MagicMock()
        mock_media.pk = 1
        mock_media.code = "ABC123"
        mock_media.product_type = ""
        mock_media.caption_text = ""
        mock_media.comment_count = 0
        mock_media.like_count = 0
        mock_media.taken_at.isoformat.return_value = ""
        mock_media.media_type = 1
        mock_media.resources = []

        result = _build_post_dict(
            media=mock_media,
            username="user",
            user_full_name="",
            user_pk="1",
            media_url="",
            media_files=["file.jpg"],
            post_folder=None,
            account_dir=None,
        )

        assert result["post_folder"] == ""


class TestLogFunctions:
    """Tests for log functions."""

    def test_log_profile_fetch_attempt(self):
        """Test profile fetch attempt logs warning using mock."""
        mock_logger = MagicMock()
        with patch("ig_scraper.scraper.logger", mock_logger):
            exc = RuntimeError("Profile fetch failed")
            _log_profile_fetch_attempt("testuser", 1, exc, 1.0)
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0]
            assert "testuser" in call_args[1]

    def test_log_medias_fetch_attempt(self):
        """Test medias fetch attempt logs warning using mock."""
        mock_logger = MagicMock()
        with patch("ig_scraper.scraper.logger", mock_logger):
            exc = RuntimeError("Medias fetch failed")
            _log_medias_fetch_attempt("testuser", 2, exc, 2.0)
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0]
            assert "testuser" in call_args[1]


class TestProcessSingleMedia:
    """Tests for _process_single_media function."""

    @patch("ig_scraper.media_processing._download_media")
    @patch("ig_scraper.media_processing._fetch_all_comments")
    @patch("ig_scraper.media_processing._media_permalink")
    def test_success(self, mock_permalink, mock_fetch, mock_download):
        """Test successful media processing."""
        from ig_scraper.media_processing import _process_single_media

        mock_client = MagicMock()
        mock_media = MagicMock()
        mock_media.pk = 12345
        mock_media.code = "ABC123"
        mock_media.media_type = 1
        mock_media.product_type = ""
        mock_media.like_count = 100
        mock_media.comment_count = 10
        mock_user = MagicMock()
        mock_user.full_name = "Test User"
        mock_user.pk = "99999"

        mock_permalink.return_value = "https://instagram.com/p/ABC123/"
        mock_download.return_value = ["photo.jpg"]
        mock_fetch.return_value = [{"text": "Nice!"}]

        post, comments, _ = _process_single_media(
            client=mock_client,
            media=mock_media,
            username="testuser",
            user=mock_user,
            account_dir=None,
            posts_root=None,
            index=1,
            total_medias=10,
        )

        assert post["short_code"] == "ABC123"
        assert len(comments) == 1

    @patch("ig_scraper.media_processing._download_media")
    @patch("ig_scraper.media_processing._fetch_all_comments")
    @patch("ig_scraper.media_processing._media_permalink")
    def test_media_download_error_continues(self, mock_permalink, mock_fetch, mock_download):
        """Test MediaDownloadError handling continues with empty media_files."""
        from ig_scraper.media_processing import _process_single_media

        mock_client = MagicMock()
        mock_media = MagicMock()
        mock_media.pk = 12345
        mock_media.code = "ABC123"
        mock_media.media_type = 1
        mock_media.product_type = ""
        mock_media.like_count = 100
        mock_media.comment_count = 10
        mock_user = MagicMock()
        mock_user.full_name = "Test User"
        mock_user.pk = "99999"

        mock_permalink.return_value = "https://instagram.com/p/ABC123/"
        mock_download.side_effect = MediaDownloadError("Download failed")
        mock_fetch.return_value = []

        post, _, media_files = _process_single_media(
            client=mock_client,
            media=mock_media,
            username="testuser",
            user=mock_user,
            account_dir=None,
            posts_root=None,
            index=1,
            total_medias=10,
        )

        assert post["short_code"] == "ABC123"
        assert media_files == []

    @patch("ig_scraper.media_processing._download_media")
    @patch("ig_scraper.media_processing._fetch_all_comments")
    @patch("ig_scraper.media_processing._media_permalink")
    def test_comment_errors_continue(self, mock_permalink, mock_fetch, mock_download):
        """Test comment fetch error handling for RuntimeError, ConnectionError, TimeoutError."""
        from ig_scraper.media_processing import _process_single_media

        for exc_type in [RuntimeError, ConnectionError, TimeoutError]:
            mock_client = MagicMock()
            mock_media = MagicMock()
            mock_media.pk = 12345
            mock_media.code = "ABC123"
            mock_media.id = 99999
            mock_media.media_type = 1
            mock_media.product_type = ""
            mock_media.like_count = 100
            mock_media.comment_count = 10
            mock_user = MagicMock()
            mock_user.full_name = "Test User"
            mock_user.pk = "99999"

            mock_permalink.return_value = "https://instagram.com/p/ABC123/"
            mock_download.return_value = []
            mock_fetch.side_effect = exc_type("Error")

            _, comments, _ = _process_single_media(
                client=mock_client,
                media=mock_media,
                username="testuser",
                user=mock_user,
                account_dir=None,
                posts_root=None,
                index=1,
                total_medias=10,
            )

            assert comments == []

    @patch("ig_scraper.media_processing._download_media")
    @patch("ig_scraper.media_processing._fetch_all_comments")
    @patch("ig_scraper.media_processing._media_permalink")
    def test_none_account_dir_and_posts_root(self, mock_permalink, mock_fetch, mock_download):
        """Test with None account_dir and posts_root."""
        from ig_scraper.media_processing import _process_single_media

        mock_client = MagicMock()
        mock_media = MagicMock()
        mock_media.pk = 12345
        mock_media.code = "ABC123"
        mock_media.id = 99999
        mock_media.media_type = 1
        mock_media.product_type = ""
        mock_media.like_count = 100
        mock_media.comment_count = 10
        mock_user = MagicMock()
        mock_user.full_name = "Test User"
        mock_user.pk = "99999"

        mock_permalink.return_value = "https://instagram.com/p/ABC123/"
        mock_download.return_value = []
        mock_fetch.return_value = []

        post, _, _ = _process_single_media(
            client=mock_client,
            media=mock_media,
            username="testuser",
            user=mock_user,
            account_dir=None,
            posts_root=None,
            index=1,
            total_medias=10,
        )

        assert post["short_code"] == "ABC123"
        assert post["post_folder"] == ""
