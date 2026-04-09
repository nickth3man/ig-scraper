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
