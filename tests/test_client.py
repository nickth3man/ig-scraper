"""Tests for client.py — authentication client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ig_scraper.client import get_instaloader_client
from ig_scraper.exceptions import AuthError, IgScraperError


class TestGetInstaloaderClient:
    """Tests for get_instaloader_client function."""

    @patch("ig_scraper.client._load_env")
    def test_raises_igscraper_error_when_sessionid_missing(self, mock_load_env, monkeypatch):
        """Test that missing INSTAGRAM_SESSIONID raises IgScraperError when username also absent."""
        monkeypatch.delenv("INSTAGRAM_SESSIONID", raising=False)
        monkeypatch.delenv("INSTAGRAM_USERNAME", raising=False)
        monkeypatch.delenv("INSTAGRAM_PASSWORD", raising=False)
        with pytest.raises(
            IgScraperError,
            match="Either INSTAGRAM_SESSIONID or INSTAGRAM_USERNAME/INSTAGRAM_PASSWORD",
        ):
            get_instaloader_client()

    @patch("ig_scraper.client._load_env")
    @patch.dict("os.environ", {"INSTAGRAM_SESSIONID": "  "}, clear=False)
    def test_raises_igscraper_error_when_sessionid_whitespace_only(
        self, mock_load_env, monkeypatch
    ):
        """Test that whitespace-only INSTAGRAM_SESSIONID raises IgScraperError when username also absent."""
        monkeypatch.delenv("INSTAGRAM_USERNAME", raising=False)
        monkeypatch.delenv("INSTAGRAM_PASSWORD", raising=False)
        with pytest.raises(
            IgScraperError,
            match="Either INSTAGRAM_SESSIONID or INSTAGRAM_USERNAME/INSTAGRAM_PASSWORD",
        ):
            get_instaloader_client()

    @patch("ig_scraper.client._load_env")
    @patch("ig_scraper.client.Instaloader")
    @patch("ig_scraper.client.Profile")
    def test_successful_authentication_returns_loader(
        self, mock_profile_cls, mock_instaloader_cls, mock_load_env, monkeypatch
    ):
        """Test that valid username/password returns authenticated Instaloader client."""
        monkeypatch.delenv("INSTAGRAM_SESSIONID", raising=False)
        monkeypatch.setenv("INSTAGRAM_USERNAME", "test_user")
        monkeypatch.setenv("INSTAGRAM_PASSWORD", "test_pass")

        mock_loader = MagicMock()
        mock_instaloader_cls.return_value = mock_loader

        mock_account = MagicMock()
        mock_account.username = "test_user"
        mock_account.userid = 12345
        mock_account.is_private = False
        mock_account.is_verified = False
        mock_profile_cls.from_username.return_value = mock_account

        result = get_instaloader_client()

        assert result is mock_loader
        mock_loader.login.assert_called_once_with("test_user", "test_pass")
        mock_profile_cls.from_username.assert_called_once()

    @patch("ig_scraper.client._load_env")
    @patch("ig_scraper.client.Instaloader")
    @patch("ig_scraper.client.Profile")
    def test_auth_error_raised_on_two_factor_required(
        self, mock_profile_cls, mock_instaloader_cls, mock_load_env, monkeypatch
    ):
        """Test AuthError raised when TwoFactorAuthRequiredException occurs."""
        from instaloader.exceptions import TwoFactorAuthRequiredException

        monkeypatch.delenv("INSTAGRAM_SESSIONID", raising=False)
        monkeypatch.setenv("INSTAGRAM_USERNAME", "test_user")
        monkeypatch.setenv("INSTAGRAM_PASSWORD", "test_pass")

        mock_loader = MagicMock()
        mock_instaloader_cls.return_value = mock_loader
        mock_loader.login.side_effect = TwoFactorAuthRequiredException("2FA required")
        mock_profile_cls.from_username.return_value = MagicMock()

        with pytest.raises(AuthError, match="Two-factor authentication is not supported"):
            get_instaloader_client()

    @patch("ig_scraper.client._load_env")
    @patch("ig_scraper.client.Instaloader")
    @patch("ig_scraper.client.Profile")
    def test_auth_error_raised_on_bad_credentials(
        self, mock_profile_cls, mock_instaloader_cls, mock_load_env, monkeypatch
    ):
        """Test AuthError raised when BadCredentialsException occurs."""
        from instaloader.exceptions import BadCredentialsException

        monkeypatch.delenv("INSTAGRAM_SESSIONID", raising=False)
        monkeypatch.setenv("INSTAGRAM_USERNAME", "test_user")
        monkeypatch.setenv("INSTAGRAM_PASSWORD", "test_pass")

        mock_loader = MagicMock()
        mock_instaloader_cls.return_value = mock_loader
        mock_loader.login.side_effect = BadCredentialsException("Bad creds")
        mock_profile_cls.from_username.return_value = MagicMock()

        with pytest.raises(AuthError, match="Invalid Instagram credentials"):
            get_instaloader_client()

    @patch("ig_scraper.client._load_env")
    @patch("ig_scraper.client.Instaloader")
    @patch("ig_scraper.client.Profile")
    def test_auth_error_raised_on_connection_error(
        self, mock_profile_cls, mock_instaloader_cls, mock_load_env, monkeypatch
    ):
        """Test AuthError raised when ConnectionException occurs during login."""
        from instaloader.exceptions import ConnectionException

        monkeypatch.delenv("INSTAGRAM_SESSIONID", raising=False)
        monkeypatch.setenv("INSTAGRAM_USERNAME", "test_user")
        monkeypatch.setenv("INSTAGRAM_PASSWORD", "test_pass")

        mock_loader = MagicMock()
        mock_instaloader_cls.return_value = mock_loader
        mock_loader.login.side_effect = ConnectionException("Connection failed")
        mock_profile_cls.from_username.return_value = MagicMock()

        with pytest.raises(AuthError, match="Connection error during Instagram login"):
            get_instaloader_client()

    @patch("ig_scraper.client._load_env")
    @patch("ig_scraper.client.Instaloader")
    @patch("ig_scraper.client.Profile")
    def test_profile_from_username_validates_access(
        self, mock_profile_cls, mock_instaloader_cls, mock_load_env, monkeypatch
    ):
        """Test that Profile.from_username is called after login to validate access."""
        monkeypatch.delenv("INSTAGRAM_SESSIONID", raising=False)
        monkeypatch.setenv("INSTAGRAM_USERNAME", "valid_user")
        monkeypatch.setenv("INSTAGRAM_PASSWORD", "valid_pass")

        mock_loader = MagicMock()
        mock_instaloader_cls.return_value = mock_loader

        mock_account = MagicMock()
        mock_account.username = "valid_user"
        mock_account.userid = 99999
        mock_account.is_private = False
        mock_account.is_verified = False
        mock_profile_cls.from_username.return_value = mock_account

        get_instaloader_client()

        assert mock_loader.login.call_count == 1
        assert mock_profile_cls.from_username.call_count == 1

    @patch("ig_scraper.client._load_env")
    @patch("ig_scraper.client.load_cookies_from_file")
    @patch("ig_scraper.client.Instaloader")
    @patch("ig_scraper.client.Profile")
    def test_sessionid_path_uses_cookies_file_and_test_login(
        self,
        mock_profile_cls,
        mock_instaloader_cls,
        mock_load_cookies,
        mock_load_env,
        monkeypatch,
    ):
        """Test session-mode auth loads cookies and validates them via test_login."""
        monkeypatch.setenv("INSTAGRAM_SESSIONID", "session-token")
        monkeypatch.delenv("INSTAGRAM_USERNAME", raising=False)
        monkeypatch.delenv("INSTAGRAM_PASSWORD", raising=False)

        mock_loader = MagicMock()
        mock_loader.test_login.return_value = "cookie_user"
        mock_instaloader_cls.return_value = mock_loader
        mock_load_cookies.return_value = {"sessionid": "cookie-session"}

        mock_account = MagicMock()
        mock_account.username = "cookie_user"
        mock_account.userid = 321
        mock_account.is_private = False
        mock_account.is_verified = False
        mock_profile_cls.from_username.return_value = mock_account

        result = get_instaloader_client()

        assert result is mock_loader
        mock_load_cookies.assert_called_once()
        mock_loader.context.update_cookies.assert_called_once_with({"sessionid": "cookie-session"})
        mock_loader.test_login.assert_called_once_with()
        mock_loader.login.assert_not_called()
        mock_profile_cls.from_username.assert_called_once()

    @patch("ig_scraper.client._load_env")
    @patch("ig_scraper.client.load_cookies_from_file")
    @patch("ig_scraper.client.Instaloader")
    @patch("ig_scraper.client.Profile")
    def test_cookie_auth_empty_cookies_file_raises_auth_error(
        self,
        mock_profile_cls,
        mock_instaloader_cls,
        mock_load_cookies,
        mock_load_env,
        monkeypatch,
    ):
        """Test AuthError when cookies.txt is empty (load_cookies_from_file returns {})."""
        monkeypatch.setenv("INSTAGRAM_SESSIONID", "session-token")
        monkeypatch.delenv("INSTAGRAM_USERNAME", raising=False)
        monkeypatch.delenv("INSTAGRAM_PASSWORD", raising=False)

        mock_loader = MagicMock()
        mock_instaloader_cls.return_value = mock_loader
        mock_load_cookies.return_value = {}

        mock_account = MagicMock()
        mock_account.username = "cookie_user"
        mock_account.userid = 321
        mock_account.is_private = False
        mock_account.is_verified = False
        mock_profile_cls.from_username.return_value = mock_account

        with pytest.raises(AuthError, match="No cookies found"):
            get_instaloader_client()

    @patch("ig_scraper.client._load_env")
    @patch("ig_scraper.client.load_cookies_from_file")
    @patch("ig_scraper.client.Instaloader")
    @patch("ig_scraper.client.Profile")
    def test_cookie_auth_test_login_returns_none_raises_auth_error(
        self,
        mock_profile_cls,
        mock_instaloader_cls,
        mock_load_cookies,
        mock_load_env,
        monkeypatch,
    ):
        """Test AuthError when test_login() returns None (invalid or expired session)."""
        monkeypatch.setenv("INSTAGRAM_SESSIONID", "session-token")
        monkeypatch.delenv("INSTAGRAM_USERNAME", raising=False)
        monkeypatch.delenv("INSTAGRAM_PASSWORD", raising=False)

        mock_loader = MagicMock()
        mock_loader.test_login.return_value = None
        mock_instaloader_cls.return_value = mock_loader
        mock_load_cookies.return_value = {"sessionid": "cookie-session"}

        mock_account = MagicMock()
        mock_account.username = "cookie_user"
        mock_account.userid = 321
        mock_account.is_private = False
        mock_account.is_verified = False
        mock_profile_cls.from_username.return_value = mock_account

        with pytest.raises(AuthError, match="invalid or expired"):
            get_instaloader_client()

    @patch("ig_scraper.client._load_env")
    @patch("ig_scraper.client.load_cookies_from_file")
    @patch("ig_scraper.client.Instaloader")
    @patch("ig_scraper.client.Profile")
    def test_cookie_auth_generic_exception_triggers_fallback_to_username_password(
        self,
        mock_profile_cls,
        mock_instaloader_cls,
        mock_load_cookies,
        mock_load_env,
        monkeypatch,
    ):
        """Test cookie auth raises generic Exception, fallback to username/password succeeds."""
        monkeypatch.setenv("INSTAGRAM_SESSIONID", "session-token")
        monkeypatch.setenv("INSTAGRAM_USERNAME", "fallback_user")
        monkeypatch.setenv("INSTAGRAM_PASSWORD", "fallback_pass")

        mock_loader = MagicMock()
        mock_loader.test_login.side_effect = Exception("Unexpected session error")
        mock_instaloader_cls.return_value = mock_loader
        mock_load_cookies.return_value = {"sessionid": "cookie-session"}

        mock_account = MagicMock()
        mock_account.username = "fallback_user"
        mock_account.userid = 654
        mock_account.is_private = False
        mock_account.is_verified = False
        mock_profile_cls.from_username.return_value = mock_account

        result = get_instaloader_client()

        assert result is mock_loader
        mock_loader.test_login.assert_called_once()
        mock_loader.login.assert_called_once_with("fallback_user", "fallback_pass")
        mock_profile_cls.from_username.assert_called_once()

    @patch("ig_scraper.client._load_env")
    @patch("ig_scraper.client.Instaloader")
    @patch("ig_scraper.client.Profile")
    def test_profile_from_username_generic_exception_raises_auth_error(
        self,
        mock_profile_cls,
        mock_instaloader_cls,
        mock_load_env,
        monkeypatch,
    ):
        """Test AuthError wraps generic Exception from Profile.from_username."""
        monkeypatch.delenv("INSTAGRAM_SESSIONID", raising=False)
        monkeypatch.setenv("INSTAGRAM_USERNAME", "test_user")
        monkeypatch.setenv("INSTAGRAM_PASSWORD", "test_pass")

        mock_loader = MagicMock()
        mock_instaloader_cls.return_value = mock_loader
        mock_profile_cls.from_username.side_effect = Exception("Unexpected error")

        with pytest.raises(AuthError, match="Instagram authentication failed"):
            get_instaloader_client()

    @patch("ig_scraper.client._load_env")
    @patch("ig_scraper.client.Instaloader")
    @patch("ig_scraper.client.Profile")
    def test_profile_from_username_connection_exception_raises_auth_error(
        self,
        mock_profile_cls,
        mock_instaloader_cls,
        mock_load_env,
        monkeypatch,
    ):
        """Test AuthError raised when ConnectionException occurs during Profile.from_username."""
        from instaloader.exceptions import ConnectionException

        monkeypatch.delenv("INSTAGRAM_SESSIONID", raising=False)
        monkeypatch.setenv("INSTAGRAM_USERNAME", "test_user")
        monkeypatch.setenv("INSTAGRAM_PASSWORD", "test_pass")

        mock_loader = MagicMock()
        mock_instaloader_cls.return_value = mock_loader
        mock_profile_cls.from_username.side_effect = ConnectionException("Connection failed")

        with pytest.raises(AuthError, match="Instagram connection error"):
            get_instaloader_client()
