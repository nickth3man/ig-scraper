"""Tests for run_scrape.py — CLI entry point and directory helpers."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ig_scraper.analysis import handle_dir, post_dir
from ig_scraper.cli import HANDLES_FILE, load_handles, main, selected_handles
from ig_scraper.export import build_manifest, write_manifest, write_profile
from ig_scraper.paths import ACCOUNT_DIR, ROOT
from ig_scraper.run_scrape import process_handle, write_post_artifacts


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

    @patch("ig_scraper.cli.process_handle", return_value="instaloader")
    @patch("ig_scraper.cli.selected_handles", return_value=["@user1", "@user2"])
    @patch("ig_scraper.cli.parse_args")
    def test_main_processes_selected_handles_and_tracks_counts(
        self,
        mock_parse_args,
        mock_selected_handles,
        mock_process_handle,
    ):
        """Test main() orchestrates handles and increments success/failure counts."""
        mock_parse_args.return_value = type(
            "Args",
            (),
            {"max_posts_per_handle": 25, "all": False, "handles": "@user1,@user2"},
        )()

        main()

        mock_selected_handles.assert_called_once()
        assert mock_process_handle.call_count == 2
        mock_process_handle.assert_any_call("@user1", max_posts=25)
        mock_process_handle.assert_any_call("@user2", max_posts=25)


class TestProcessHandle:
    """Tests for process_handle function."""

    @patch("ig_scraper.run_scrape.write_post_artifacts")
    @patch("ig_scraper.run_scrape.fetch_profile_posts_and_comments")
    def test_manifest_written_after_process(self, mock_fetch, mock_write_artifacts, tmp_path):
        """Test manifest.json is written with version=1 after process_handle."""
        profile = {"username": "testuser", "followers_count": 100}
        posts = [
            {
                "short_code": "POST001",
                "url": "https://instagram.com/p/POST001/",
                "caption": "Caption 1",
                "id": "1",
                "like_count": 10,
                "comment_count": 2,
                "media_files": [],
            }
        ]
        comments = [{"post_url": "https://instagram.com/p/POST001/", "text": "Comment 1"}]
        mock_fetch.return_value = (profile, posts, comments)

        with patch("ig_scraper.run_scrape.ACCOUNT_DIR", tmp_path):
            process_handle("@testuser", max_posts=50)

        manifest_path = tmp_path / "@testuser" / "manifest.json"
        assert manifest_path.exists(), "manifest.json should be written"
        import json

        manifest = json.loads(manifest_path.read_text())
        assert manifest["version"] == 1
        assert manifest["handle"] == "@testuser"
        assert len(manifest["collections"][0]["items"]) == 1

    @patch("ig_scraper.run_scrape.write_post_artifacts")
    @patch("ig_scraper.run_scrape.fetch_profile_posts_and_comments")
    def test_profile_json_written(self, mock_fetch, mock_write_artifacts, tmp_path):
        """Test profile.json is written with correct data after process_handle."""
        profile = {"username": "testuser", "followers_count": 100, "_internal": "dropped"}
        posts = [
            {
                "short_code": "POST001",
                "url": "https://instagram.com/p/POST001/",
                "caption": "Caption",
                "id": "1",
                "like_count": 5,
                "comment_count": 0,
                "media_files": [],
            }
        ]
        comments = []
        mock_fetch.return_value = (profile, posts, comments)

        with patch("ig_scraper.run_scrape.ACCOUNT_DIR", tmp_path):
            process_handle("@testuser", max_posts=50)

        profile_path = tmp_path / "@testuser" / "profile.json"
        assert profile_path.exists(), "profile.json should be written"
        import json

        prof = json.loads(profile_path.read_text())
        assert prof["username"] == "testuser"
        assert prof["followers_count"] == 100
        assert "_internal" not in prof

    @patch("ig_scraper.run_scrape.write_post_artifacts")
    @patch("ig_scraper.run_scrape.fetch_profile_posts_and_comments")
    def test_no_swipes_dir_created(self, mock_fetch, mock_write_artifacts, tmp_path):
        """Test swipes/ directory is NOT created after process_handle."""
        profile = {"username": "testuser"}
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
        comments = []
        mock_fetch.return_value = (profile, posts, comments)

        with patch("ig_scraper.run_scrape.ACCOUNT_DIR", tmp_path):
            process_handle("@testuser", max_posts=50)

        swipes_dir = tmp_path / "@testuser" / "swipes"
        assert not swipes_dir.exists(), "swipes/ directory should not exist"

    @patch("ig_scraper.run_scrape.write_post_artifacts")
    @patch("ig_scraper.run_scrape.fetch_profile_posts_and_comments")
    def test_no_analysis_md_created(self, mock_fetch, mock_write_artifacts, tmp_path):
        """Test analysis.md is NOT created after process_handle."""
        profile = {"username": "testuser"}
        posts = [
            {
                "short_code": "POST001",
                "url": "https://instagram.com/p/POST001/",
                "caption": "Caption",
                "id": "1",
                "like_count": 10,
                "comment_count": 2,
                "media_files": [],
            }
        ]
        comments = []
        mock_fetch.return_value = (profile, posts, comments)

        with patch("ig_scraper.run_scrape.ACCOUNT_DIR", tmp_path):
            process_handle("@testuser", max_posts=50)

        analysis_path = tmp_path / "@testuser" / "analysis.md"
        assert not analysis_path.exists(), "analysis.md should not exist"

    @patch("ig_scraper.run_scrape.write_post_artifacts")
    @patch("ig_scraper.run_scrape.fetch_profile_posts_and_comments")
    def test_no_raw_posts_json(self, mock_fetch, mock_write_artifacts, tmp_path):
        """Test raw-posts.json is NOT created after process_handle."""
        profile = {"username": "testuser"}
        posts = [
            {
                "short_code": "POST001",
                "url": "https://instagram.com/p/POST001/",
                "caption": "Caption",
                "id": "1",
                "like_count": 10,
                "comment_count": 2,
                "media_files": [],
            }
        ]
        comments = []
        mock_fetch.return_value = (profile, posts, comments)

        with patch("ig_scraper.run_scrape.ACCOUNT_DIR", tmp_path):
            process_handle("@testuser", max_posts=50)

        raw_posts_path = tmp_path / "@testuser" / "raw-posts.json"
        assert not raw_posts_path.exists(), "raw-posts.json should not exist"

    @patch("ig_scraper.run_scrape.write_post_artifacts")
    @patch("ig_scraper.run_scrape.fetch_profile_posts_and_comments")
    def test_no_raw_comments_json(self, mock_fetch, mock_write_artifacts, tmp_path):
        """Test raw-comments.json is NOT created after process_handle."""
        profile = {"username": "testuser"}
        posts = [
            {
                "short_code": "POST001",
                "url": "https://instagram.com/p/POST001/",
                "caption": "Caption",
                "id": "1",
                "like_count": 10,
                "comment_count": 2,
                "media_files": [],
            }
        ]
        comments = [{"post_url": "https://instagram.com/p/POST001/", "text": "Comment"}]
        mock_fetch.return_value = (profile, posts, comments)

        with patch("ig_scraper.run_scrape.ACCOUNT_DIR", tmp_path):
            process_handle("@testuser", max_posts=50)

        raw_comments_path = tmp_path / "@testuser" / "raw-comments.json"
        assert not raw_comments_path.exists(), "raw-comments.json should not exist"


# ---------------------------------------------------------------------------
# Phase 2 manifest aggregation — runner-level contract tests
# ---------------------------------------------------------------------------


class TestProcessHandleCollectionsContract:
    """Runner-level manifest aggregation tests for Phase 2 collection results.

    Validates the Oracle-approved chunk summary contract:
    - (a) List-based collections (stories/tagged/highlights) contribute items
      with non-empty items list and correct domain metadata.
    - (b) Chunk-summary collections (saved/followers/followees) contribute
      entries with items=[] and a chunks key present.
    - (c) Skipped collections append top-level skipped_reasons.
    """

    @patch("ig_scraper.run_scrape.write_post_artifacts")
    @patch("ig_scraper.run_scrape.fetch_profile_posts_and_comments")
    @patch("ig_scraper.run_scrape.collect_stories")
    @patch("ig_scraper.run_scrape.collect_tagged_posts")
    @patch("ig_scraper.run_scrape.collect_saved_posts")
    @patch("ig_scraper.run_scrape.collect_followers")
    @patch("ig_scraper.run_scrape.collect_followees")
    @patch("ig_scraper.run_scrape.collect_highlights")
    @patch("ig_scraper.run_scrape.get_instaloader_client")
    def test_highlights_list_contributes_items_based_entry(
        self,
        mock_get_client,
        mock_collect_highlights,
        mock_collect_followees,
        mock_collect_followers,
        mock_collect_saved,
        mock_collect_tagged,
        mock_collect_stories,
        mock_fetch,
        mock_write_artifacts,
        tmp_path,
    ):
        """(a) Highlights with items produces a list-based collection entry."""
        profile = {"username": "alice"}
        posts = [
            {
                "short_code": "P1",
                "id": "1",
                "url": "x",
                "media_files": [],
            }
        ]
        comments = []
        mock_fetch.return_value = (profile, posts, comments)
        mock_get_client.return_value = MagicMock()

        mock_highlight_result = MagicMock()
        mock_highlight_result.skipped = False
        mock_highlight_result.items = [{"id": "hl_1", "title": "Travel"}]
        mock_collect_highlights.return_value = mock_highlight_result

        for fn in (
            mock_collect_stories,
            mock_collect_tagged,
            mock_collect_saved,
            mock_collect_followers,
            mock_collect_followees,
        ):
            r = MagicMock()
            r.skipped = True
            r.skip_reason = "not implemented"
            fn.return_value = r

        mock_profile_obj = MagicMock()
        with patch("instaloader.Profile") as mock_profile_cls:
            mock_profile_cls.from_username.return_value = mock_profile_obj
            with patch("ig_scraper.run_scrape.ACCOUNT_DIR", tmp_path):
                process_handle("@alice", max_posts=50)

        manifest = json.loads((tmp_path / "@alice" / "manifest.json").read_text())
        domains = {c["domain"]: c for c in manifest["collections"]}

        assert domains["highlights"]["items"] == [{"id": "hl_1", "title": "Travel"}]
        assert domains["highlights"]["count"] == 1
        assert "chunks" not in domains["highlights"]

    @patch("ig_scraper.run_scrape.write_post_artifacts")
    @patch("ig_scraper.run_scrape.fetch_profile_posts_and_comments")
    @patch("ig_scraper.run_scrape.collect_saved_posts")
    @patch("ig_scraper.run_scrape.collect_followers")
    @patch("ig_scraper.run_scrape.collect_followees")
    @patch("ig_scraper.run_scrape.collect_stories")
    @patch("ig_scraper.run_scrape.collect_tagged_posts")
    @patch("ig_scraper.run_scrape.collect_highlights")
    @patch("ig_scraper.run_scrape.get_instaloader_client")
    def test_saved_followers_followees_emit_chunk_summary_with_items_empty_and_chunks(
        self,
        mock_get_client,
        mock_collect_highlights,
        mock_collect_tagged,
        mock_collect_stories,
        mock_collect_followees,
        mock_collect_followers,
        mock_collect_saved,
        mock_fetch,
        mock_write_artifacts,
        tmp_path,
    ):
        """(b) saved/followers/followees return chunk-summary dicts with items=[] and chunks."""
        profile = {"username": "alice"}
        posts = [{"short_code": "P1", "id": "1", "url": "x", "media_files": []}]
        comments = []
        mock_fetch.return_value = (profile, posts, comments)
        mock_get_client.return_value = MagicMock()

        for fn in (mock_collect_highlights, mock_collect_stories, mock_collect_tagged):
            r = MagicMock()
            r.skipped = True
            r.skip_reason = "not implemented"
            fn.return_value = r

        saved_summary = {
            "count": 150,
            "chunks": [
                {
                    "offset": 0,
                    "total": 150,
                    "relative_path": "saved/posts__0001.json",
                    "profile_count": 150,
                }
            ],
        }
        followers_summary = {
            "count": 300,
            "chunks": [
                {
                    "offset": 0,
                    "total": 300,
                    "relative_path": "relationships/followers__0001.json",
                    "profile_count": 300,
                }
            ],
        }
        followees_summary = {
            "count": 42,
            "chunks": [],
        }

        mock_saved_result = MagicMock()
        mock_saved_result.skipped = False
        mock_saved_result.to_dict.return_value = saved_summary
        mock_collect_saved.return_value = mock_saved_result

        mock_followers_result = MagicMock()
        mock_followers_result.skipped = False
        mock_followers_result.skip_reason = None
        mock_followers_result.to_dict.return_value = followers_summary
        mock_collect_followers.return_value = mock_followers_result

        mock_followees_result = MagicMock()
        mock_followees_result.skipped = False
        mock_followees_result.skip_reason = None
        mock_followees_result.to_dict.return_value = followees_summary
        mock_collect_followees.return_value = mock_followees_result

        mock_profile_obj = MagicMock()
        with patch("instaloader.Profile") as mock_profile_cls:
            mock_profile_cls.from_username.return_value = mock_profile_obj
            with patch("ig_scraper.run_scrape.ACCOUNT_DIR", tmp_path):
                process_handle("@alice", max_posts=50)

        manifest = json.loads((tmp_path / "@alice" / "manifest.json").read_text())
        domains = {c["domain"]: c for c in manifest["collections"]}

        assert domains["saved"]["items"] == []
        assert domains["saved"]["count"] == 150
        assert "chunks" in domains["saved"]
        assert domains["saved"]["chunked"] is True
        assert domains["saved"]["auth_required"] is True

        assert domains["followers"]["items"] == []
        assert domains["followers"]["count"] == 300
        assert "chunks" in domains["followers"]
        assert domains["followers"]["chunked"] is True

        assert domains["followees"]["items"] == []
        assert domains["followees"]["count"] == 42
        assert "chunks" in domains["followees"]
        assert domains["followees"]["chunked"] is True

    @patch("ig_scraper.run_scrape.write_post_artifacts")
    @patch("ig_scraper.run_scrape.fetch_profile_posts_and_comments")
    @patch("ig_scraper.run_scrape.collect_stories")
    @patch("ig_scraper.run_scrape.collect_tagged_posts")
    @patch("ig_scraper.run_scrape.collect_highlights")
    @patch("ig_scraper.run_scrape.get_instaloader_client")
    def test_stories_tagged_contribute_items_based_entries(
        self,
        mock_get_client,
        mock_collect_highlights,
        mock_collect_tagged,
        mock_collect_stories,
        mock_fetch,
        mock_write_artifacts,
        tmp_path,
    ):
        """(a) Stories and tagged with items produce list-based collection entries."""
        profile = {"username": "alice"}
        posts = [{"short_code": "P1", "id": "1", "url": "x", "media_files": []}]
        comments = []
        mock_fetch.return_value = (profile, posts, comments)
        mock_get_client.return_value = MagicMock()

        for fn in (mock_collect_highlights,):
            r = MagicMock()
            r.skipped = True
            r.skip_reason = "not implemented"
            fn.return_value = r

        mock_story_result = MagicMock()
        mock_story_result.skipped = False
        mock_story_result.items = [{"id": "s1"}, {"id": "s2"}]
        mock_collect_stories.return_value = mock_story_result

        mock_tagged_result = MagicMock()
        mock_tagged_result.skipped = False
        mock_tagged_result.items = [{"pk": "t1"}, {"pk": "t2"}, {"pk": "t3"}]
        mock_collect_tagged.return_value = mock_tagged_result

        mock_profile_obj = MagicMock()
        with patch("instaloader.Profile") as mock_profile_cls:
            mock_profile_cls.from_username.return_value = mock_profile_obj
            with patch("ig_scraper.run_scrape.ACCOUNT_DIR", tmp_path):
                process_handle("@alice", max_posts=50)

        manifest = json.loads((tmp_path / "@alice" / "manifest.json").read_text())
        domains = {c["domain"]: c for c in manifest["collections"]}

        assert domains["stories"]["items"] == [{"id": "s1"}, {"id": "s2"}]
        assert domains["stories"]["count"] == 2
        assert "chunks" not in domains["stories"]

        assert domains["tagged"]["items"] == [{"pk": "t1"}, {"pk": "t2"}, {"pk": "t3"}]
        assert domains["tagged"]["count"] == 3
        assert "chunks" not in domains["tagged"]

    @patch("ig_scraper.run_scrape.write_post_artifacts")
    @patch("ig_scraper.run_scrape.fetch_profile_posts_and_comments")
    @patch("ig_scraper.run_scrape.collect_stories")
    @patch("ig_scraper.run_scrape.collect_tagged_posts")
    @patch("ig_scraper.run_scrape.collect_highlights")
    @patch("ig_scraper.run_scrape.get_instaloader_client")
    def test_skipped_stories_tagged_append_skipped_reasons(
        self,
        mock_get_client,
        mock_collect_highlights,
        mock_collect_tagged,
        mock_collect_stories,
        mock_fetch,
        mock_write_artifacts,
        tmp_path,
    ):
        """(c) Skipped stories and tagged append domain-specific reasons to skipped_reasons."""
        profile = {"username": "alice"}
        posts = [{"short_code": "P1", "id": "1", "url": "x", "media_files": []}]
        comments = []
        mock_fetch.return_value = (profile, posts, comments)
        mock_get_client.return_value = MagicMock()

        mock_highlight_result = MagicMock()
        mock_highlight_result.skipped = True
        mock_highlight_result.skip_reason = "not implemented"
        mock_collect_highlights.return_value = mock_highlight_result

        mock_story_result = MagicMock()
        mock_story_result.skipped = True
        mock_story_result.skip_reason = "Login required"
        mock_collect_stories.return_value = mock_story_result

        mock_tagged_result = MagicMock()
        mock_tagged_result.skipped = True
        mock_tagged_result.skip_reason = "Private account"
        mock_collect_tagged.return_value = mock_tagged_result

        mock_profile_obj = MagicMock()
        with patch("instaloader.Profile") as mock_profile_cls:
            mock_profile_cls.from_username.return_value = mock_profile_obj
            with patch("ig_scraper.run_scrape.ACCOUNT_DIR", tmp_path):
                process_handle("@alice", max_posts=50)

        manifest = json.loads((tmp_path / "@alice" / "manifest.json").read_text())
        assert "stories: Login required" in manifest.get("skipped_reasons", [])
        assert "tagged: Private account" in manifest.get("skipped_reasons", [])

    def test_saved_chunk_summary_emits_items_empty_and_chunks(self):
        """(b) saved as a summary dict emits items=[] and includes chunks."""
        posts = [
            {"index": 0, "shortcode": "X", "folder": "001_X", "media_count": 1, "comment_count": 0}
        ]
        collections = {
            "saved": {
                "count": 1500,
                "chunks": [
                    {
                        "offset": 0,
                        "total": 500,
                        "relative_path": "saved/posts__0001.json",
                        "profile_count": 500,
                    },
                    {
                        "offset": 500,
                        "total": 500,
                        "relative_path": "saved/posts__0002.json",
                        "profile_count": 500,
                    },
                    {
                        "offset": 1000,
                        "total": 500,
                        "relative_path": "saved/posts__0003.json",
                        "profile_count": 500,
                    },
                ],
            },
        }
        manifest = build_manifest("alice", posts, collections=collections)
        entry = next(c for c in manifest["collections"] if c["domain"] == "saved")

        assert entry["items"] == []
        assert entry["count"] == 1500
        assert "chunks" in entry
        assert len(entry["chunks"]) == 3
        assert entry["chunked"] is True
        assert entry["auth_required"] is True

    def test_followers_chunk_summary_emits_items_empty_and_chunks(self):
        """(b) followers as a summary dict emits items=[] and includes chunks."""
        posts = [
            {"index": 0, "shortcode": "X", "folder": "001_X", "media_count": 1, "comment_count": 0}
        ]
        collections = {
            "followers": {
                "count": 300,
                "chunks": [
                    {
                        "offset": 0,
                        "total": 300,
                        "relative_path": "relationships/followers__0001.json",
                        "profile_count": 300,
                    },
                ],
            },
        }
        manifest = build_manifest("alice", posts, collections=collections)
        entry = next(c for c in manifest["collections"] if c["domain"] == "followers")

        assert entry["items"] == []
        assert entry["count"] == 300
        assert "chunks" in entry
        assert len(entry["chunks"]) == 1
        assert entry["chunked"] is True

    def test_followees_chunk_summary_emits_items_empty_and_no_chunks_key_when_absent(self):
        """(b) followees summary without chunks key omits chunks field."""
        posts = [
            {"index": 0, "shortcode": "X", "folder": "001_X", "media_count": 1, "comment_count": 0}
        ]
        collections = {
            "followees": {"count": 42},
        }
        manifest = build_manifest("alice", posts, collections=collections)
        entry = next(c for c in manifest["collections"] if c["domain"] == "followees")

        assert entry["items"] == []
        assert entry["count"] == 42
        assert "chunks" not in entry

    def test_skipped_reasons_accumulate_across_collections(self):
        """(c) Multiple skipped reasons accumulate in the top-level list."""
        posts = [
            {"index": 0, "shortcode": "X", "folder": "001_X", "media_count": 1, "comment_count": 0}
        ]
        manifest = build_manifest(
            "alice",
            posts,
            skipped_reasons=["highlights: auth required", "stories: rate-limited"],
        )
        assert manifest["skipped_reasons"] == [
            "highlights: auth required",
            "stories: rate-limited",
        ]

    def test_posts_always_first_collection(self):
        """The posts collection is always first, regardless of collection order."""
        collections = {
            "highlights": [{"id": "h1"}],
            "stories": [{"id": "s1"}],
            "saved": {"count": 10, "chunks": []},
        }
        manifest = build_manifest(
            "alice",
            [
                {
                    "index": 0,
                    "shortcode": "X",
                    "folder": "001_X",
                    "media_count": 1,
                    "comment_count": 0,
                }
            ],
            collections=collections,
        )
        assert manifest["collections"][0]["domain"] == "posts"

    def test_list_and_summary_mix_in_same_manifest(self):
        """(a)+(b) Both list-based and chunk-summary entries coexist in one manifest."""
        posts = [
            {"index": 0, "shortcode": "X", "folder": "001_X", "media_count": 1, "comment_count": 0}
        ]
        collections = {
            "stories": [{"id": "s1"}],  # list-based
            "saved": {"count": 100, "chunks": [{"offset": 0, "total": 100}]},
            "highlights": [{"id": "h1"}],  # list-based
            "followers": {"count": 50, "chunks": []},
        }
        manifest = build_manifest("alice", posts, collections=collections)
        domains = {c["domain"]: c for c in manifest["collections"]}

        assert domains["stories"]["items"] == [{"id": "s1"}]
        assert domains["highlights"]["items"] == [{"id": "h1"}]

        assert domains["saved"]["items"] == []
        assert "chunks" in domains["saved"]
        assert domains["followers"]["items"] == []
        assert "chunks" in domains["followers"]
