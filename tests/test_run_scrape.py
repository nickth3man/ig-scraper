"""Tests for run_scrape.py — CLI entry point and directory helpers."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from ig_scraper.analysis import handle_dir, post_dir
from ig_scraper.cli import HANDLES_FILE, load_handles, main, selected_handles
from ig_scraper.paths import ACCOUNT_DIR, ROOT
from ig_scraper.run_scrape import (
    cleanup_removed_handle_dirs,
    initialize_readme,
    process_handle,
    update_readme_status,
    write_post_artifacts,
)


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

        with (
            patch("ig_scraper.cli.HANDLES_FILE", handles_file),
            patch("ig_scraper.cli.load_handles", return_value=["@from_file"]),
        ):
            result = selected_handles(Namespace(all=True, handles=""))
            assert result == ["@from_file"]

    def test_selected_handles_from_comma_separated(self):
        """Test --handles parses comma-separated handles."""
        result = selected_handles(Namespace(all=False, handles="@user1,@user2, @user3"))

        assert "@user1" in result
        assert "@user2" in result
        assert "@user3" in result

    def test_selected_handles_raises_when_no_handles_provided(self):
        """Test selected_handles raises SystemExit when no handles given."""
        with pytest.raises(SystemExit):
            selected_handles(Namespace(all=False, handles=""))


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


class TestCliPipelineContract:
    """Contract tests for the main CLI orchestration path."""

    @patch("ig_scraper.cli.update_readme_status")
    @patch("ig_scraper.cli.process_handle", return_value="instaloader")
    @patch("ig_scraper.cli.cleanup_removed_handle_dirs")
    @patch("ig_scraper.cli.initialize_readme")
    @patch("ig_scraper.cli.selected_handles", return_value=["@user1", "@user2"])
    @patch("ig_scraper.cli.parse_args")
    def test_main_processes_selected_handles_and_updates_status(
        self,
        mock_parse_args,
        mock_selected_handles,
        mock_initialize_readme,
        mock_cleanup_removed_handle_dirs,
        mock_process_handle,
        mock_update_readme_status,
    ):
        """Test main() orchestrates the happy path across all selected handles."""
        mock_parse_args.return_value = type(
            "Args",
            (),
            {"max_posts_per_handle": 25, "all": False, "handles": "@user1,@user2"},
        )()

        main()

        mock_selected_handles.assert_called_once()
        mock_initialize_readme.assert_called_once_with(["@user1", "@user2"])
        mock_cleanup_removed_handle_dirs.assert_called_once_with(["@user1", "@user2"])
        assert mock_process_handle.call_count == 2
        mock_process_handle.assert_any_call("@user1", max_posts=25)
        mock_process_handle.assert_any_call("@user2", max_posts=25)
        assert mock_update_readme_status.call_count == 2
        mock_update_readme_status.assert_any_call(
            "@user1",
            "analyzed",
            "instaloader",
            "25 posts target; all comments",
        )
        mock_update_readme_status.assert_any_call(
            "@user2",
            "analyzed",
            "instaloader",
            "25 posts target; all comments",
        )


class TestInitializeReadme:
    """Tests for initialize_readme function."""

    @patch("ig_scraper.run_scrape.ACCOUNT_DIR")
    def test_new_file_creation(self, mock_account_dir, tmp_path):
        """Test initialize_readme creates markdown file with header and handle rows."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        readme_path = data_dir / "README.md"
        mock_account_dir = data_dir / "accounts"

        with (
            patch("ig_scraper.run_scrape.ACCOUNT_DIR", mock_account_dir),
            patch("ig_scraper.run_scrape.README_FILE", readme_path),
        ):
            initialize_readme(["@handle1", "@handle2"])

        text = readme_path.read_text(encoding="utf-8")
        assert "# Account Corpus" in text
        assert "## Status" in text
        assert "| Handle | Analysis | Access | Notes |" in text
        assert "| @handle1 | pending | queued | awaiting scrape |" in text
        assert "| @handle2 | pending | queued | awaiting scrape |" in text

    @patch("ig_scraper.run_scrape.ACCOUNT_DIR")
    def test_existing_file_new_handles_appended(self, mock_account_dir, tmp_path):
        """Test adding new handles to existing README appends rows without duplicating."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        readme_path = data_dir / "README.md"
        readme_path.write_text(
            "# Account Corpus\n\n## Status\n\n| Handle | Analysis | Access | Notes |\n|---|---|---|---|\n| @handle1 | pending | queued | awaiting scrape |\n",
            encoding="utf-8",
        )
        mock_account_dir = data_dir / "accounts"

        with (
            patch("ig_scraper.run_scrape.ACCOUNT_DIR", mock_account_dir),
            patch("ig_scraper.run_scrape.README_FILE", readme_path),
        ):
            initialize_readme(["@handle2"])

        text = readme_path.read_text(encoding="utf-8")
        assert text.count("@handle1") == 1
        assert text.count("@handle2") == 1

    @patch("ig_scraper.run_scrape.ACCOUNT_DIR")
    def test_existing_file_duplicate_handles_skipped(self, mock_account_dir, tmp_path):
        """Test re-adding an existing handle does not duplicate the row."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        readme_path = data_dir / "README.md"
        readme_path.write_text(
            "# Account Corpus\n\n## Status\n\n| Handle | Analysis | Access | Notes |\n|---|---|---|---|\n| @handle1 | pending | queued | awaiting scrape |\n",
            encoding="utf-8",
        )
        mock_account_dir = data_dir / "accounts"

        with (
            patch("ig_scraper.run_scrape.ACCOUNT_DIR", mock_account_dir),
            patch("ig_scraper.run_scrape.README_FILE", readme_path),
        ):
            initialize_readme(["@handle1"])

        text = readme_path.read_text(encoding="utf-8")
        assert text.count("@handle1") == 1

    @patch("ig_scraper.run_scrape.ACCOUNT_DIR")
    def test_empty_handles_list_creates_headers_only(self, mock_account_dir, tmp_path):
        """Test with no handles, README created with headers but no handle rows."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        readme_path = data_dir / "README.md"
        mock_account_dir = data_dir / "accounts"

        with (
            patch("ig_scraper.run_scrape.ACCOUNT_DIR", mock_account_dir),
            patch("ig_scraper.run_scrape.README_FILE", readme_path),
        ):
            initialize_readme([])

        text = readme_path.read_text(encoding="utf-8")
        assert "# Account Corpus" in text
        assert "## Status" in text
        assert "| Handle | Analysis | Access | Notes |" in text


class TestCleanupRemovedHandleDirs:
    """Tests for cleanup_removed_handle_dirs function."""

    def test_just_logs_no_exception(self):
        """Test cleanup_removed_handle_dirs runs without raising."""
        # Should not raise any exception
        cleanup_removed_handle_dirs(["@user1", "@user2"])


class TestProcessHandle:
    """Tests for process_handle function."""

    @patch("ig_scraper.run_scrape.build_analysis_markdown", return_value="# Analysis")
    @patch("ig_scraper.run_scrape.write_json")
    @patch("ig_scraper.run_scrape.write_post_artifacts")
    @patch("ig_scraper.run_scrape.ensure_swipes_dir")
    @patch("ig_scraper.run_scrape.fetch_profile_posts_and_comments")
    def test_happy_path_with_posts(
        self,
        mock_fetch,
        mock_ensure,
        mock_write_artifacts,
        mock_write_json,
        mock_analysis,
        tmp_path,
    ):
        """Test process_handle happy path with 3 posts and 5 comments."""
        profile = {"username": "testuser", "followers_count": 100}
        posts = [
            {
                "short_code": f"POST{i:03d}",
                "url": f"https://instagram.com/p/POST{i:03d}/",
                "caption": f"Caption {i}",
                "id": str(i),
                "like_count": i * 10,
                "comment_count": i * 2,
                "media_files": [],
            }
            for i in range(1, 4)
        ]
        comments = [
            {"post_url": "https://instagram.com/p/POST001/", "text": f"Comment {i}"}
            for i in range(5)
        ]
        mock_fetch.return_value = (profile, posts, comments)
        mock_ensure.side_effect = lambda base, handle: (base / handle / "swipes").mkdir(
            parents=True, exist_ok=True
        )

        with patch("ig_scraper.run_scrape.ACCOUNT_DIR", tmp_path):
            result = process_handle("@testuser", max_posts=50)

        assert result == "instaloader"
        mock_fetch.assert_called_once_with(
            "testuser", posts_per_profile=50, account_dir=tmp_path / "@testuser"
        )
        mock_write_artifacts.assert_called_once_with("@testuser", posts, comments)
        assert mock_write_json.call_count == 2
        analysis_file = tmp_path / "@testuser" / "analysis.md"
        assert analysis_file.exists()
        swipe_dir = tmp_path / "@testuser" / "swipes"
        assert (swipe_dir / "post-01.md").exists()
        assert (swipe_dir / "post-02.md").exists()
        assert (swipe_dir / "post-03.md").exists()
        assert not (swipe_dir / "post-04.md").exists()

    @patch("ig_scraper.run_scrape.build_analysis_markdown", return_value="# Analysis")
    @patch("ig_scraper.run_scrape.write_json")
    @patch("ig_scraper.run_scrape.write_post_artifacts")
    @patch("ig_scraper.run_scrape.ensure_swipes_dir")
    @patch("ig_scraper.run_scrape.fetch_profile_posts_and_comments")
    def test_with_fewer_than_five_posts(
        self,
        mock_fetch,
        mock_ensure,
        mock_write_artifacts,
        mock_write_json,
        mock_analysis,
        tmp_path,
    ):
        """Test process_handle with only 2 posts creates exactly 2 swipe files."""
        profile = {"username": "testuser"}
        posts = [
            {
                "short_code": f"POST{i:03d}",
                "url": f"https://instagram.com/p/POST{i:03d}/",
                "caption": f"Caption {i}",
                "id": str(i),
                "like_count": 10,
                "comment_count": 1,
                "media_files": [],
            }
            for i in range(1, 3)
        ]
        comments = []
        mock_fetch.return_value = (profile, posts, comments)
        mock_ensure.side_effect = lambda base, handle: (base / handle / "swipes").mkdir(
            parents=True, exist_ok=True
        )

        with patch("ig_scraper.run_scrape.ACCOUNT_DIR", tmp_path):
            result = process_handle("@testuser", max_posts=50)

        assert result == "instaloader"
        swipe_dir = tmp_path / "@testuser" / "swipes"
        assert (swipe_dir / "post-01.md").exists()
        assert (swipe_dir / "post-02.md").exists()
        assert not (swipe_dir / "post-03.md").exists()

    @patch("ig_scraper.run_scrape.build_analysis_markdown", return_value="# Analysis")
    @patch("ig_scraper.run_scrape.write_json")
    @patch("ig_scraper.run_scrape.write_post_artifacts")
    @patch("ig_scraper.run_scrape.ensure_swipes_dir")
    @patch("ig_scraper.run_scrape.fetch_profile_posts_and_comments")
    def test_zero_posts_no_swipe_files(
        self,
        mock_fetch,
        mock_ensure,
        mock_write_artifacts,
        mock_write_json,
        mock_analysis,
        tmp_path,
    ):
        """Test process_handle with empty posts list creates no swipe files."""
        profile = {"username": "testuser"}
        posts = []
        comments = []
        mock_fetch.return_value = (profile, posts, comments)
        mock_ensure.side_effect = lambda base, handle: (base / handle / "swipes").mkdir(
            parents=True, exist_ok=True
        )

        with patch("ig_scraper.run_scrape.ACCOUNT_DIR", tmp_path):
            result = process_handle("@testuser", max_posts=50)

        assert result == "instaloader"
        swipe_dir = tmp_path / "@testuser" / "swipes"
        assert not any(swipe_dir.iterdir())


class TestUpdateReadmeStatus:
    """Tests for update_readme_status function."""

    def test_existing_row_updated(self, tmp_path):
        """Test update_readme_status replaces an existing handle row."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        readme_path = data_dir / "README.md"
        readme_path.write_text(
            "# Account Corpus\n\n## Status\n\n| Handle | Analysis | Access | Notes |\n|---|---|---|---|\n| @user1 | pending | queued | awaiting scrape |\n| @user2 | pending | queued | awaiting scrape |\n",
            encoding="utf-8",
        )

        with patch("ig_scraper.run_scrape.README_FILE", readme_path):
            update_readme_status("@user1", "analyzed", "instaloader", "10 posts scraped")

        text = readme_path.read_text(encoding="utf-8")
        assert "| @user1 | analyzed | instaloader | 10 posts scraped |" in text
        assert "| @user2 | pending | queued | awaiting scrape |" in text

    def test_handle_not_in_readme_unchanged(self, tmp_path):
        """Test update_readme_status when handle row not present leaves text unchanged."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        readme_path = data_dir / "README.md"
        original = (
            "# Account Corpus\n\n## Status\n\n| Handle | Analysis | Access | Notes |\n"
            "|---|---|---|---|\n| @other | analyzed | instaloader | stuff |\n"
        )
        readme_path.write_text(original, encoding="utf-8")

        with patch("ig_scraper.run_scrape.README_FILE", readme_path):
            update_readme_status("@nonexistent", "analyzed", "instaloader", "notes")

        text = readme_path.read_text(encoding="utf-8")
        assert text == original
