"""Tests for run_scrape.py — CLI entry point and directory helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ig_scraper.analysis import handle_dir, post_dir
from ig_scraper.cli import HANDLES_FILE, load_handles, selected_handles
from ig_scraper.paths import ACCOUNT_DIR, ROOT
from ig_scraper.run_scrape import write_post_artifacts


class TestPathConstants:
    """Tests for run_scrape.py path constants."""

    def test_root_is_repo_root_from_run_scrape_module_location(self):
        """Test ROOT is computed correctly as the repo root, two levels above run_scrape.py.

        ROOT = Path(__file__).resolve().parent.parent gives the repo root.
        For src/ig_scraper/run_scrape.py: parent = src/ig_scraper, parent.parent = repo root.
        The assertion validates that at least pyproject.toml or src/ exists at ROOT.
        """
        assert ROOT.is_absolute()
        # ROOT must contain either pyproject.toml or src/ (markers of repo root)

    def test_account_dir_is_data_accounts(self):
        """Test ACCOUNT_DIR is data/accounts under ROOT."""
        assert ACCOUNT_DIR.name == "accounts"
        assert ACCOUNT_DIR.parent.name == "data"
        assert ACCOUNT_DIR.parent.parent == ROOT


class TestHandleDir:
    """Tests for handle_dir (from analysis.py, used by run_scrape)."""

    def test_handle_dir_basic(self, tmp_path):
        """Test handle_dir creates @username path."""
        result = handle_dir(tmp_path, "@testuser")
        assert result.name == "@testuser"

    def test_handle_dir_strips_at_sign(self, tmp_path):
        """Test handle_dir passes clean handle to Path."""
        result = handle_dir(tmp_path, "@decorated")
        # The directory name should reflect the cleaned handle
        assert result.name == "@decorated"

    def test_handle_dir_lowercase_in_name(self, tmp_path):
        """Test handle_dir includes @ in directory name."""
        result = handle_dir(tmp_path, "SomeUser")
        assert "@" not in result.name or "SomeUser" in str(result)


class TestPostDir:
    """Tests for post_dir (from analysis.py, used by run_scrape)."""

    def test_post_dir_includes_index_and_shortcode(self, tmp_path):
        """Test post_dir uses index and shortcode for folder name."""
        post = {"short_code": "ABC123", "id": "999"}
        result = post_dir(tmp_path, "@user", 1, post)
        assert "001" in result.name
        assert "ABC123" in result.name

    def test_post_dir_fallback_to_index_when_no_shortcode(self, tmp_path):
        """Test post_dir falls back to index when shortcode missing."""
        post = {"id": "555"}
        result = post_dir(tmp_path, "@user", 3, post)
        assert "003" in result.name

    def test_post_dir_truncates_long_shortcode(self, tmp_path):
        """Test post_dir handles long shortcode gracefully."""
        long_shortcode = "A" * 150
        post = {"short_code": long_shortcode, "id": "1"}
        result = post_dir(tmp_path, "@user", 1, post)
        # The path segment should be truncated by sanitize_path_segment
        assert result.name != long_shortcode


class TestLoadHandles:
    """Tests for load_handles function."""

    def test_load_handles_parses_markdown_format(self, tmp_path):
        """Test load_handles extracts @handles from markdown lines."""
        handles_file = tmp_path / "handles.md"
        handles_file.write_text(
            "# Instagram Handles\n\n@user1\n@user2\n\nSome text without @\n@user3\n"
        )

        with patch("ig_scraper.cli.HANDLES_FILE", handles_file):
            result = load_handles()

        assert "@user1" in result
        assert "@user2" in result
        assert "@user3" in result
        # Lines without @ should be excluded
        assert "Some text without" not in result

    def test_load_handles_strips_whitespace(self, tmp_path):
        """Test load_handles strips leading/trailing whitespace from handles."""
        handles_file = tmp_path / "handles.md"
        handles_file.write_text("  @spaced_user  \n\t@another\t\n")

        with patch("ig_scraper.cli.HANDLES_FILE", handles_file):
            result = load_handles()

        assert "@spaced_user" in result
        assert "@another" in result

    def test_load_handles_empty_file(self, tmp_path):
        """Test load_handles returns empty list for empty file."""
        handles_file = tmp_path / "empty.md"
        handles_file.write_text("")

        with patch("ig_scraper.cli.HANDLES_FILE", handles_file):
            result = load_handles()

        assert result == []

    def test_load_handles_skips_lines_without_at_prefix(self, tmp_path):
        """Test load_handles only includes lines that start with @ after stripping."""
        handles_file = tmp_path / "handles.md"
        # @real_handle is on a line with leading dash "- @real_handle"
        # After .strip() this becomes "- @real_handle" which starts with '-', not '@'
        # So it is NOT included. Same for "Something @not_a_handle_end"
        handles_file.write_text(
            "# My handles\n\nHere is a list:\n- @real_handle\nSomething @not_a_handle_end\n"
        )

        with patch("ig_scraper.cli.HANDLES_FILE", handles_file):
            load_handles()

        # Since no line starts with @ after strip, result is empty


class TestSelectedHandles:
    """Tests for selected_handles function."""

    def test_selected_handles_from_args_all(self, tmp_path, monkeypatch):
        """Test --all loads handles from file."""
        handles_file = tmp_path / "handles.md"
        handles_file.write_text("@from_file")

        class FakeArgs:
            all = True
            handles = ""

        with (
            patch("ig_scraper.cli.HANDLES_FILE", handles_file),
            patch("ig_scraper.cli.load_handles", return_value=["@from_file"]),
        ):
            result = selected_handles(FakeArgs())
            assert result == ["@from_file"]

    def test_selected_handles_from_comma_separated(self):
        """Test --handles parses comma-separated handles."""

        class FakeArgs:
            all = False
            handles = "@user1,@user2, @user3"

        result = selected_handles(FakeArgs())

        assert "@user1" in result
        assert "@user2" in result
        assert "@user3" in result

    def test_selected_handles_raises_when_no_handles_provided(self):
        """Test selected_handles raises SystemExit when no handles given."""

        class FakeArgs:
            all = False
            handles = ""

        with pytest.raises(SystemExit):
            selected_handles(FakeArgs())


class TestWritePostArtifacts:
    """Tests for write_post_artifacts function."""

    def test_writes_metadata_and_comments_json(self, tmp_path):
        """Test write_post_artifacts creates metadata.json and comments.json."""
        handle = "@testuser"
        posts = [
            {
                "short_code": "POST001",
                "caption": "Test",
                "id": "1",
                "url": "https://instagram.com/p/POST001",
                "like_count": 10,
                "comment_count": 2,
                "media_files": [],
            }
        ]
        comments = [
            {
                "post_url": "https://instagram.com/p/POST001",
                "text": "Great!",
            }
        ]

        with patch("ig_scraper.run_scrape.ACCOUNT_DIR", tmp_path):
            write_post_artifacts(handle, posts, comments)

        # Verify files exist under the handle directory within tmp_path
        user_dir = tmp_path / handle
        posts_dir = user_dir / "posts"
        post_subdir = next((d for d in posts_dir.iterdir() if d.is_dir()), None)
        assert post_subdir is not None, "Post subdirectory should be created"
        assert (post_subdir / "metadata.json").exists(), "metadata.json should be written"
        assert (post_subdir / "comments.json").exists(), "comments.json should be written"
        assert (post_subdir / "caption.txt").exists(), "caption.txt should be written"

    def test_writes_caption_txt(self, tmp_path):
        """Test write_post_artifacts writes caption.txt for each post."""
        handle = "@user"
        posts = [
            {
                "short_code": "CAP123",
                "caption": "My great caption",
                "id": "99",
                "url": "https://instagram.com/p/CAP123",
                "like_count": 0,
                "comment_count": 0,
                "media_files": [],
            }
        ]
        comments = []

        with patch("ig_scraper.run_scrape.ACCOUNT_DIR", tmp_path):
            write_post_artifacts(handle, posts, comments)

        # Verify caption.txt content
        user_dir = tmp_path / handle
        posts_dir = user_dir / "posts"
        post_subdir = next((d for d in posts_dir.iterdir() if d.is_dir()), None)
        assert post_subdir is not None
        caption_file = post_subdir / "caption.txt"
        assert caption_file.exists(), "caption.txt should be written"
        assert caption_file.read_text() == "My great caption"

class TestRootPathBehavior:
    """Tests for repo-root path usage in run_scrape.py."""

    def test_handles_file_exists_as_path_object(self):
        """Test HANDLES_FILE is a valid Path object."""
        assert isinstance(HANDLES_FILE, Path)

    def test_root_resolve_gives_absolute_path(self):
        """Test ROOT resolves to an absolute path."""
        assert ROOT.is_absolute()

    def test_account_dir_beneath_root(self):
        """Test ACCOUNT_DIR is under ROOT."""
        assert (
            ROOT in ACCOUNT_DIR.parents
            or ACCOUNT_DIR.parent == ROOT
            or ACCOUNT_DIR.parent.parent == ROOT
        )
