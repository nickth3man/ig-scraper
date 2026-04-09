"""Tests for instagram_client.py — authentication client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ig_scraper.client import get_instagram_client
from ig_scraper.exceptions import AuthError, IgScraperError


class TestGetInstagramClient:
    """Tests for get_instagram_client function."""

    @patch("ig_scraper.client._load_env")
    def test_raises_igscraper_error_when_sessionid_missing(self, mock_load_env, monkeypatch):
        """Test that missing INSTAGRAM_SESSIONID raises IgScraperError."""
        monkeypatch.delenv("INSTAGRAM_SESSIONID", raising=False)
        with pytest.raises(IgScraperError, match="INSTAGRAM_SESSIONID is missing"):
            get_instagram_client()

    @patch("ig_scraper.client._load_env")
    @patch.dict("os.environ", {"INSTAGRAM_SESSIONID": "  "}, clear=False)
    def test_raises_igscraper_error_when_sessionid_whitespace_only(self, mock_load_env):
        """Test that whitespace-only INSTAGRAM_SESSIONID raises IgScraperError."""
        with pytest.raises(IgScraperError, match="INSTAGRAM_SESSIONID is missing"):
            get_instagram_client()

    @patch("ig_scraper.client._load_env")
    @patch.dict("os.environ", {"INSTAGRAM_SESSIONID": "valid_session_123"}, clear=False)
    @patch("ig_scraper.client.Client")
    def test_successful_authentication_returns_client(self, mock_client_cls, mock_load_env):
        """Test that valid sessionid returns authenticated client."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_account = MagicMock()
        mock_account.username = "test_user"
        mock_account.pk = 12345
        mock_client.login_by_sessionid.return_value = None
        mock_client.account_info.return_value = mock_account

        result = get_instagram_client()

        assert result is mock_client
        mock_client.login_by_sessionid.assert_called_once_with("valid_session_123")
        mock_client.account_info.assert_called_once()

    @patch("ig_scraper.client._load_env")
    @patch.dict("os.environ", {"INSTAGRAM_SESSIONID": "session_id"}, clear=False)
    @patch("ig_scraper.client.Client")
    def test_auth_error_raised_on_login_required(self, mock_client_cls, mock_load_env):
        """Test AuthError raised when LoginRequired exception occurs."""
        from instagrapi.exceptions import LoginRequired

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.login_by_sessionid.side_effect = LoginRequired("Session expired")
        mock_client.account_info.return_value = MagicMock()

        with pytest.raises(AuthError, match="Instagram authentication failed"):
            get_instagram_client()

    @patch("ig_scraper.client._load_env")
    @patch.dict("os.environ", {"INSTAGRAM_SESSIONID": "session_id"}, clear=False)
    @patch("ig_scraper.client.Client")
    def test_auth_error_raised_on_client_throttled(self, mock_client_cls, mock_load_env):
        """Test AuthError raised when ClientThrottledError occurs."""
        from instagrapi.exceptions import ClientThrottledError

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.login_by_sessionid.side_effect = ClientThrottledError("Rate limited")
        mock_client.account_info.return_value = MagicMock()

        with pytest.raises(AuthError, match="Instagram authentication failed"):
            get_instagram_client()

    @patch("ig_scraper.client._load_env")
    @patch.dict("os.environ", {"INSTAGRAM_SESSIONID": "session_id"}, clear=False)
    @patch("ig_scraper.client.Client")
    def test_auth_error_raised_on_challenge_required(self, mock_client_cls, mock_load_env):
        """Test AuthError raised when ChallengeRequired occurs."""
        from instagrapi.exceptions import ChallengeRequired

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.login_by_sessionid.side_effect = ChallengeRequired("Challenge needed")
        mock_client.account_info.return_value = MagicMock()

        with pytest.raises(AuthError, match="Instagram authentication failed"):
            get_instagram_client()

    @patch("ig_scraper.client._load_env")
    @patch.dict("os.environ", {"INSTAGRAM_SESSIONID": "session_id"}, clear=False)
    @patch("ig_scraper.client.Client")
    def test_auth_error_raised_on_feedback_required(self, mock_client_cls, mock_load_env):
        """Test AuthError raised when FeedbackRequired occurs."""
        from instagrapi.exceptions import FeedbackRequired

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.login_by_sessionid.side_effect = FeedbackRequired("Feedback required")
        mock_client.account_info.return_value = MagicMock()

        with pytest.raises(AuthError, match="Instagram authentication failed"):
            get_instagram_client()

    @patch("ig_scraper.client._load_env")
    @patch.dict("os.environ", {"INSTAGRAM_SESSIONID": "session_id"}, clear=False)
    @patch("ig_scraper.client.Client")
    def test_auth_error_raised_on_please_wait_few_minutes(self, mock_client_cls, mock_load_env):
        """Test AuthError raised when PleaseWaitFewMinutes occurs."""
        from instagrapi.exceptions import PleaseWaitFewMinutes

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.login_by_sessionid.side_effect = PleaseWaitFewMinutes("Please wait")
        mock_client.account_info.return_value = MagicMock()

        with pytest.raises(AuthError, match="Instagram authentication failed"):
            get_instagram_client()

    @patch("ig_scraper.client._load_env")
    @patch.dict("os.environ", {"INSTAGRAM_SESSIONID": "session_id"}, clear=False)
    @patch("ig_scraper.client.Client")
    def test_account_info_validates_access(self, mock_client_cls, mock_load_env):
        """Test that account_info is called after login to validate access."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_account = MagicMock()
        mock_account.username = "valid_user"
        mock_account.pk = 99999
        mock_client.login_by_sessionid.return_value = None
        mock_client.account_info.return_value = mock_account

        get_instagram_client()

        # Both calls must happen for successful authentication
        assert mock_client.login_by_sessionid.call_count == 1
        assert mock_client.account_info.call_count == 1
