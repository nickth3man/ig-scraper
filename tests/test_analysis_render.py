"""Tests for analysis_render.py — Markdown rendering for account analysis."""

from __future__ import annotations

from collections import Counter

from ig_scraper.analysis_render import (
    _compute_analysis_stats,
    _render_access_log,
    _render_patterns_section,
    _render_profile_section,
    _render_strategy_section,
    _render_swipes_section,
    build_analysis_markdown,
)


class TestBuildAnalysisMarkdown:
    """Tests for build_analysis_markdown function."""

    def test_empty_posts_and_comments(self):
        """Test with empty posts and comments."""
        result = build_analysis_markdown("testuser", [], [])
        assert "# Account Analysis" in result

    def test_posts_with_profile_metadata(self):
        """Test with posts containing _profile metadata."""
        posts = [{"_profile": {"_method": "instaloader"}, "caption": "Test"}]
        result = build_analysis_markdown("testuser", posts, [])
        assert "instaloader" in result

    def test_output_contains_expected_sections(self):
        """Test all expected sections are present in output."""
        result = build_analysis_markdown("testuser", [], [])
        for section in [
            "## 1. Account Profile",
            "## 2. Pattern Observations",
            "## 3. Swipe-Worthy Posts",
            "## 4. What Doesn't Work",
            "## 5. Strategy Implications",
            "## Access Log",
        ]:
            assert section in result

    def test_top_posts_sorted_by_engagement(self):
        """Test that top posts are sorted by likes + comments."""
        posts = [
            {"pk": "1", "caption": "Low", "likes_count": 10, "comments_count": 1},
            {"pk": "2", "caption": "High", "likes_count": 100, "comments_count": 50},
        ]
        result = build_analysis_markdown("testuser", posts, [])
        assert "High" in result

    def test_comment_summaries_generated(self):
        """Test that comment summaries are generated."""
        posts = [{"caption": "Test", "likes_count": 10, "comments_count": 5}]
        comments = [{"text": "Nice!", "post_url": "https://instagram.com/p/ABC123/"}]
        result = build_analysis_markdown("testuser", posts, comments)
        assert "comments captured" in result.lower()


class TestComputeAnalysisStats:
    """Tests for _compute_analysis_stats function."""

    def test_multiple_posts_and_comments(self):
        """Test with multiple posts and comments."""
        posts = [{"caption": "#python is great", "likes_count": 100, "comments_count": 10}]
        comments = [{"text": "Nice!", "post_url": "https://example.com/p/1"}]
        stats = _compute_analysis_stats(posts, comments)
        assert stats["post_count_observed"] == 1
        assert stats["total_comments"] == 1

    def test_counters_for_formats_hashtags_mentions(self):
        """Test that correct Counter types are returned."""
        posts = [
            {"caption": "#python @user1", "likes_count": 10, "comments_count": 1, "media_type": 1}
        ]
        stats = _compute_analysis_stats(posts, [])
        assert isinstance(stats["formats"], Counter)
        assert isinstance(stats["hashtags"], Counter)
        assert isinstance(stats["mentions"], Counter)
        assert stats["hashtags"]["#python"] == 1

    def test_top_posts_sorted_correctly(self):
        """Test that top_posts are sorted by engagement."""
        posts = [
            {"pk": "1", "caption": "Low", "likes_count": 10, "comments_count": 1},
            {"pk": "2", "caption": "High", "likes_count": 100, "comments_count": 50},
        ]
        stats = _compute_analysis_stats(posts, [])
        assert stats["top_posts"][0]["pk"] == "2"


class TestRenderProfileSection:
    """Tests for _render_profile_section function."""

    def test_profile_section_with_bio(self):
        """Test profile section with biography."""
        stats = {
            "profile": {"biography": "Test bio", "followers_count": 1000},
            "formats": Counter(),
            "common_words": [],
        }
        lines = _render_profile_section(stats, post_count=10)
        assert "Account Profile" in "\n".join(lines)
        assert "Test bio" in "\n".join(lines)


class TestRenderPatternsSection:
    """Tests for _render_patterns_section function."""

    def test_patterns_with_hooks_and_formats(self):
        """Test patterns section with hooks and formats."""
        stats = {
            "hooks": ["Hook 1"],
            "formats": Counter({"Story": 5}),
            "common_words": ["python"],
            "hashtags": Counter({"#python": 3}),
            "mentions": Counter(),
            "captions": ["Test"],
            "total_comments": 10,
            "comments_by_post": {},
            "comments": [],
        }
        lines = _render_patterns_section(stats)
        result = "\n".join(lines)
        assert "Pattern Observations" in result
        assert "Hook 1" in result


class TestRenderSwipesSection:
    """Tests for _render_swipes_section function."""

    def test_swipes_with_top_posts(self):
        """Test swipes section with top posts."""
        stats = {
            "top_posts": [
                {"short_code": "ABC123", "caption": "Test", "likes_count": 100, "media_type": 1}
            ],
            "comments_by_post": {},
        }
        lines = _render_swipes_section(stats)
        result = "\n".join(lines)
        assert "Swipe-Worthy" in result
        assert "Test" in result


class TestRenderStrategySection:
    """Tests for _render_strategy_section function."""

    def test_strategy_with_common_words(self):
        """Test strategy section with common words."""
        stats = {"common_words": ["python"], "formats": Counter(), "total_comments": 20}
        lines = _render_strategy_section(stats)
        result = "\n".join(lines)
        assert "What Doesn't Work" in result
        assert "Strategy Implications" in result


class TestRenderAccessLog:
    """Tests for _render_access_log function."""

    def test_access_log_with_method(self):
        """Test access log with method info."""
        stats = {
            "profile": {"_method": "instaloader"},
            "post_count_observed": 10,
            "total_comments": 5,
        }
        lines = _render_access_log(stats)
        result = "\n".join(lines)
        assert "Access Log" in result
        assert "instaloader" in result
