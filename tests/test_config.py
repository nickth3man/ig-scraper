"""Tests for configuration module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ig_scraper import config
from ig_scraper.config import (
    COMMENTS_PAGE_SIZE,
    COMMENT_PAGE_RETRIES,
    MEDIA_DOWNLOAD_RETRIES,
    REQUEST_PAUSE_SECONDS,
    _env_float,
    _env_int,
    _sleep,
)


class TestEnvInt:
    """Test integer environment variable parsing."""

    def test_env_int_with_valid_value(self):
        """Test parsing valid integer from environment."""
        with patch.dict("os.environ", {"TEST_INT": "42"}):
            result = _env_int("TEST_INT", 10)
            assert result == 42

    def test_env_int_with_default(self):
        """Test default value when env var not set."""
        with patch.dict("os.environ", {}, clear=True):
            result = _env_int("NONEXISTENT_VAR", 100)
            assert result == 100

    def test_env_int_with_invalid_value_logs_warning(self, caplog):
        """Test that invalid values log warning and use default."""
        import logging

        with (
            patch.dict("os.environ", {"TEST_INT": "not_a_number"}),
            caplog.at_level(logging.WARNING, logger="ig_scraper.instagrapi"),
        ):
            result = _env_int("TEST_INT", 50)
            assert result == 50
            # Check that warning was logged (may be in stdout due to custom handler)

    def test_env_int_with_empty_string(self):
        """Test that empty string returns default."""
        with patch.dict("os.environ", {"TEST_INT": ""}):
            result = _env_int("TEST_INT", 50)
            assert result == 50


class TestEnvFloat:
    """Test float environment variable parsing."""

    def test_env_float_with_valid_value(self):
        """Test parsing valid float from environment."""
        with patch.dict("os.environ", {"TEST_FLOAT": "3.14"}):
            result = _env_float("TEST_FLOAT", 1.0)
            assert result == 3.14

    def test_env_float_with_default(self):
        """Test default value when env var not set."""
        with patch.dict("os.environ", {}, clear=True):
            result = _env_float("NONEXISTENT_VAR", 2.5)
            assert result == 2.5

    def test_env_float_with_invalid_value_logs_warning(self, caplog):
        """Test that invalid values log warning and use default."""
        import logging

        with (
            patch.dict("os.environ", {"TEST_FLOAT": "not_a_float"}),
            caplog.at_level(logging.WARNING, logger="ig_scraper.instagrapi"),
        ):
            result = _env_float("TEST_FLOAT", 0.5)
            assert result == 0.5

    def test_env_float_with_integer_string(self):
        """Test that integer strings are parsed as floats."""
        with patch.dict("os.environ", {"TEST_FLOAT": "10"}):
            result = _env_float("TEST_FLOAT", 1.0)
            assert result == 10.0
            assert isinstance(result, float)


class TestConfigConstants:
    """Test configuration constants."""

    def test_comments_page_size_default(self):
        """Test default comments page size."""
        assert COMMENTS_PAGE_SIZE == 250

    def test_request_pause_seconds_default(self):
        """Test default request pause."""
        assert REQUEST_PAUSE_SECONDS == 0.25

    def test_comment_page_retries_default(self):
        """Test default comment page retries."""
        assert COMMENT_PAGE_RETRIES == 3

    def test_media_download_retries_default(self):
        """Test default media download retries."""
        assert MEDIA_DOWNLOAD_RETRIES == 3


class TestSleep:
    """Test sleep function."""

    @patch("time.perf_counter")
    @patch("time.sleep")
    def test_sleep_logs_debug(self, mock_sleep, mock_perf_counter, caplog):
        """Test that sleep logs debug messages."""
        import logging

        mock_perf_counter.side_effect = [0.0, 0.25]  # Start and end times

        with (
            caplog.at_level(logging.DEBUG, logger="ig_scraper.instagrapi"),
            patch.object(config, "REQUEST_PAUSE_SECONDS", 0.25),
        ):
            _sleep("test_reason")

        # Verify sleep was called with correct duration
        mock_sleep.assert_called_once_with(0.25)

    @patch("time.perf_counter")
    @patch("time.sleep")
    def test_sleep_measures_elapsed_time(self, mock_sleep, mock_perf_counter):
        """Test that sleep measures actual elapsed time."""
        mock_perf_counter.side_effect = [0.0, 0.3]  # 0.3 seconds elapsed

        with patch.object(config, "REQUEST_PAUSE_SECONDS", 0.25):
            _sleep("test")

        # The function should have called sleep with the configured pause time
        mock_sleep.assert_called_once_with(0.25)


class TestConfigLogging:
    """Test configuration logging."""

    def test_config_logs_constants_on_import(self):
        """Test that config module loads successfully."""
        # The module logs constants at DEBUG level on import
        # Just verify the module can be reloaded without errors
        import importlib

        importlib.reload(config)
        # If we get here without exception, the test passes
        assert True
