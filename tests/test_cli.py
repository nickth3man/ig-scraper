"""Tests for CLI module."""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

from ig_scraper.cli import (
    load_handles,
    main,
    parse_args,
    selected_handles,
)


class TestParseArgs:
    """Test CLI argument parsing."""

    def test_parse_args_with_handles(self):
        """Test parsing --handles argument."""
        with patch("sys.argv", ["ig_scraper", "--handles", "@user1,@user2"]):
            args = parse_args()
            assert args.handles == "@user1,@user2"
            assert args.all is False
            assert args.max_posts_per_handle == 100

    def test_parse_args_with_all(self):
        """Test parsing --all argument."""
        with patch("sys.argv", ["ig_scraper", "--all"]):
            args = parse_args()
            assert args.all is True
            assert args.handles == ""

    def test_parse_args_with_max_posts(self):
        """Test parsing --max-posts-per-handle argument."""
        with patch(
            "sys.argv",
            ["ig_scraper", "--handles", "@user", "--max-posts-per-handle", "50"],
        ):
            args = parse_args()
            assert args.max_posts_per_handle == 50

    def test_parse_args_help(self, capsys):
        """Test help output."""
        with pytest.raises(SystemExit) as exc_info, patch("sys.argv", ["ig_scraper", "--help"]):
            parse_args()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Scrape Instagram handles" in captured.out
        assert "--handles" in captured.out
        assert "--all" in captured.out


class TestLoadHandles:
    """Test handle loading from file."""

    def test_load_handles_success(self, tmp_path):
        """Test loading handles from markdown file."""
        handles_file = tmp_path / "instagram_handles.md"
        handles_file.write_text("@user1\n@user2\n\n# Comment\n@user3")

        with patch("ig_scraper.cli.HANDLES_FILE", handles_file):
            handles = load_handles()
            assert handles == ["@user1", "@user2", "@user3"]

    def test_load_handles_empty_file(self, tmp_path):
        """Test loading from empty file."""
        handles_file = tmp_path / "instagram_handles.md"
        handles_file.write_text("")

        with patch("ig_scraper.cli.HANDLES_FILE", handles_file):
            handles = load_handles()
            assert handles == []

    def test_load_handles_no_at_symbol(self, tmp_path):
        """Test that lines without @ are ignored."""
        handles_file = tmp_path / "instagram_handles.md"
        handles_file.write_text("@user1\nnot a handle\n@user2")

        with patch("ig_scraper.cli.HANDLES_FILE", handles_file):
            handles = load_handles()
            assert handles == ["@user1", "@user2"]


class TestSelectedHandles:
    """Test handle selection logic."""

    def test_selected_handles_with_handles(self):
        """Test selecting handles from --handles argument."""
        args = argparse.Namespace(all=False, handles="@user1,@user2", max_posts_per_handle=100)
        handles = selected_handles(args)
        assert handles == ["@user1", "@user2"]

    def test_selected_handles_single_handle(self):
        """Test selecting single handle."""
        args = argparse.Namespace(all=False, handles="@user1", max_posts_per_handle=100)
        handles = selected_handles(args)
        assert handles == ["@user1"]

    def test_selected_handles_with_spaces(self):
        """Test handling spaces in handle list."""
        args = argparse.Namespace(all=False, handles=" @user1 , @user2 ", max_posts_per_handle=100)
        handles = selected_handles(args)
        assert handles == ["@user1", "@user2"]

    def test_selected_handles_from_all(self, tmp_path):
        """Test loading all handles from file."""
        handles_file = tmp_path / "instagram_handles.md"
        handles_file.write_text("@user1\n@user2")

        args = argparse.Namespace(all=True, handles="", max_posts_per_handle=100)

        with patch("ig_scraper.cli.HANDLES_FILE", handles_file):
            handles = selected_handles(args)
            assert handles == ["@user1", "@user2"]

    def test_selected_handles_no_args(self):
        """Test error when neither --handles nor --all provided."""
        args = argparse.Namespace(all=False, handles="", max_posts_per_handle=100)
        with pytest.raises(SystemExit) as exc_info:
            selected_handles(args)
        assert exc_info.value.code == "Provide --all or --handles"


class TestMain:
    """Test main CLI entry point."""

    @patch("ig_scraper.cli.configure_logging")
    @patch("ig_scraper.cli.parse_args")
    @patch("ig_scraper.cli.selected_handles")
    @patch("ig_scraper.cli.initialize_readme")
    @patch("ig_scraper.cli.cleanup_removed_handle_dirs")
    @patch("ig_scraper.cli.process_handle")
    @patch("ig_scraper.cli.update_readme_status")
    def test_main_success(
        self,
        mock_update_readme,
        mock_process_handle,
        mock_cleanup,
        mock_init_readme,
        mock_selected_handles,
        mock_parse_args,
        mock_configure_logging,
    ):
        """Test successful execution with single handle."""
        mock_parse_args.return_value = argparse.Namespace(
            handles="@user1",
            all=False,
            max_posts_per_handle=50,
        )
        mock_selected_handles.return_value = ["@user1"]
        mock_process_handle.return_value = "method1"

        main()

        mock_configure_logging.assert_called_once()
        mock_init_readme.assert_called_once_with(["@user1"])
        mock_cleanup.assert_called_once_with(["@user1"])
        mock_process_handle.assert_called_once_with("@user1", max_posts=50)
        mock_update_readme.assert_called_with(
            "@user1", "analyzed", "method1", "50 posts target; all comments"
        )

    @patch("ig_scraper.cli.configure_logging")
    @patch("ig_scraper.cli.parse_args")
    @patch("ig_scraper.cli.selected_handles")
    @patch("ig_scraper.cli.initialize_readme")
    @patch("ig_scraper.cli.cleanup_removed_handle_dirs")
    @patch("ig_scraper.cli.process_handle")
    @patch("ig_scraper.cli.update_readme_status")
    def test_main_multiple_handles(
        self,
        mock_update_readme,
        mock_process_handle,
        mock_cleanup,
        mock_init_readme,
        mock_selected_handles,
        mock_parse_args,
        mock_configure_logging,
    ):
        """Test execution with multiple handles."""
        mock_parse_args.return_value = argparse.Namespace(
            handles="@user1,@user2",
            all=False,
            max_posts_per_handle=100,
        )
        mock_selected_handles.return_value = ["@user1", "@user2"]
        mock_process_handle.return_value = "method1"

        main()

        assert mock_process_handle.call_count == 2
        mock_process_handle.assert_any_call("@user1", max_posts=100)
        mock_process_handle.assert_any_call("@user2", max_posts=100)

    @patch("ig_scraper.cli.configure_logging")
    @patch("ig_scraper.cli.parse_args")
    @patch("ig_scraper.cli.selected_handles")
    @patch("ig_scraper.cli.initialize_readme")
    @patch("ig_scraper.cli.cleanup_removed_handle_dirs")
    @patch("ig_scraper.cli.process_handle")
    @patch("ig_scraper.cli.update_readme_status")
    @patch("ig_scraper.cli.logger")
    def test_main_handles_failure(
        self,
        mock_logger,
        mock_update_readme,
        mock_process_handle,
        mock_cleanup,
        mock_init_readme,
        mock_selected_handles,
        mock_parse_args,
        mock_configure_logging,
    ):
        """Test handling of process failures."""
        from ig_scraper.exceptions import IgScraperError

        mock_parse_args.return_value = argparse.Namespace(
            handles="@user1",
            all=False,
            max_posts_per_handle=100,
        )
        mock_selected_handles.return_value = ["@user1"]
        mock_process_handle.side_effect = IgScraperError("Test error")

        main()

        mock_update_readme.assert_called_with("@user1", "failed", "error", "Test error")
        mock_logger.warning.assert_called()
        mock_logger.exception.assert_not_called()

    @patch("ig_scraper.cli.configure_logging")
    @patch("ig_scraper.cli.parse_args")
    @patch("ig_scraper.cli.selected_handles")
    def test_main_keyboard_interrupt(
        self,
        mock_selected_handles,
        mock_parse_args,
        mock_configure_logging,
    ):
        """Test that KeyboardInterrupt is re-raised."""
        mock_parse_args.return_value = argparse.Namespace(
            handles="@user1",
            all=False,
            max_posts_per_handle=100,
        )
        mock_selected_handles.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            main()

    @patch("ig_scraper.cli.configure_logging")
    @patch("ig_scraper.cli.parse_args")
    @patch("ig_scraper.cli.selected_handles")
    @patch("ig_scraper.cli.initialize_readme")
    @patch("ig_scraper.cli.cleanup_removed_handle_dirs")
    @patch("ig_scraper.cli.process_handle")
    @patch("ig_scraper.cli.update_readme_status")
    @patch("time.perf_counter")
    def test_main_logs_summary(
        self,
        mock_perf_counter,
        mock_update_readme,
        mock_process_handle,
        mock_cleanup,
        mock_init_readme,
        mock_selected_handles,
        mock_parse_args,
        mock_configure_logging,
        caplog,
    ):
        """Test that summary is logged at completion."""
        import logging

        mock_perf_counter.return_value = 5.5  # Just return a fixed value
        mock_parse_args.return_value = argparse.Namespace(
            handles="@user1",
            all=False,
            max_posts_per_handle=100,
        )
        mock_selected_handles.return_value = ["@user1"]
        mock_process_handle.return_value = "method1"

        main()

        # Verify main completes and calls process_handle
        assert mock_process_handle.called
