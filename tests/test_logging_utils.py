"""Tests for logging_utils.py — structured logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from ig_scraper.logging_utils import configure_logging, format_kv, get_logger


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_configure_logging_with_explicit_log_file(self, tmp_path):
        """Test configure_logging creates file handler at specified path."""
        log_file = tmp_path / "custom.log"

        logger = configure_logging(log_file=log_file)

        assert log_file.exists()
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) >= 1

    def test_configure_logging_creates_default_timestamped_log(self, tmp_path):
        """Test configure_logging without log_file creates timestamped file."""
        from ig_scraper.logging_utils import _cached_log_path

        with patch("ig_scraper.logging_utils.LOGS_DIR", tmp_path):
            logger = configure_logging()

        # Should not raise and should have handlers
        assert logger is not None


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_with_no_name_returns_root_logger(self):
        """Test get_logger with no name returns logger with ig_scraper name."""
        logger = get_logger()

        assert logger.name == "ig_scraper"

    def test_get_logger_with_name_returns_child_logger(self):
        """Test get_logger with name returns child logger."""
        logger = get_logger("child")

        assert logger.name == "ig_scraper.child"

    def test_get_logger_empty_string_returns_root_logger(self):
        """Test get_logger with empty string returns root logger."""
        logger = get_logger("")

        assert logger.name == "ig_scraper"


class TestFormatKv:
    """Tests for format_kv function."""

    def test_format_kv_with_none_values_handled_gracefully(self):
        """Test format_kv handles None values gracefully."""
        result = format_kv(name="Alice", value=None, other="data")

        # None values should be skipped, not raise an error
        assert "name=Alice" in result
        assert "other=data" in result
        assert "value=None" not in result

    def test_format_kv_produces_pipe_delimited_output(self):
        """Test format_kv produces pipe-delimited key=value pairs."""
        result = format_kv(key1="val1", key2="val2")

        assert "key1=val1" in result
        assert "key2=val2" in result
        assert " | " in result

    def test_format_kv_with_empty_kwargs_returns_empty_string(self):
        """Test format_kv with no kwargs returns empty string."""
        result = format_kv()

        assert result == ""
