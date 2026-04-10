"""Tests for session.py — cookie loading utilities."""

from __future__ import annotations

import json

import pytest

from ig_scraper.session import load_cookies_from_file


class TestLoadCookiesFromFile:
    """Tests for load_cookies_from_file function."""

    def test_valid_cookies_json_returns_name_value_dict(self, tmp_path):
        """Test valid cookies JSON returns dict of name-value pairs."""
        cookies_file = tmp_path / "cookies.json"
        cookies_data = [
            {"name": "sessionid", "value": "abc123"},
            {"name": "csrftoken", "value": "xyz789"},
        ]
        cookies_file.write_text(json.dumps(cookies_data), encoding="utf-8")

        result = load_cookies_from_file(cookies_file)

        assert result == {"sessionid": "abc123", "csrftoken": "xyz789"}

    def test_malformed_json_returns_empty_dict(self, tmp_path):
        """Test malformed JSON returns empty dict."""
        cookies_file = tmp_path / "bad.json"
        cookies_file.write_text("{ invalid json }", encoding="utf-8")

        result = load_cookies_from_file(cookies_file)

        assert result == {}

    def test_file_not_found_returns_empty_dict(self, tmp_path):
        """Test missing file returns empty dict."""
        nonexistent = tmp_path / "does_not_exist.json"

        result = load_cookies_from_file(nonexistent)

        assert result == {}

    def test_json_with_missing_name_or_value_filters_entries(self, tmp_path):
        """Test entries missing name or value keys are filtered out."""
        cookies_file = tmp_path / "partial.json"
        cookies_data = [
            {"name": "good_cookie", "value": "good_value"},
            {"value": "missing_name"},
            {"name": "missing_value"},
            {"other": "field"},
        ]
        cookies_file.write_text(json.dumps(cookies_data), encoding="utf-8")

        result = load_cookies_from_file(cookies_file)

        assert result == {"good_cookie": "good_value"}

    def test_empty_json_array_returns_empty_dict(self, tmp_path):
        """Test empty JSON array returns empty dict."""
        cookies_file = tmp_path / "empty.json"
        cookies_file.write_text("[]", encoding="utf-8")

        result = load_cookies_from_file(cookies_file)

        assert result == {}
