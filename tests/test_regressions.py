"""Regression tests using pytest-regressions for ig_scraper.

Guards composed outputs against unintended drift.
Golden files are auto-created on first run.
"""

from __future__ import annotations

from typing import Any

from ig_scraper.analysis import (
    group_comments_by_post,
    top_words,
)
from ig_scraper.analysis_render import build_analysis_markdown
from tests.factories import ProfileFactory


class TestProfileRegression:
    """Regression tests for Profile serialization."""

    def test_profile_dict_regression(self, data_regression: Any) -> None:
        """Profile.to_dict() output should match golden baseline."""
        profile = ProfileFactory.build(
            id="regression_001",
            username="regtest_user",
            full_name="Regression Test",
            biography="Testing regression",
            followers_count=5000,
            follows_count=200,
            posts_count=100,
            verified=True,
            is_business_account=False,
            profile_pic_url="https://example.com/pic.jpg",
            external_url="https://example.com",
        )
        data_regression.check(profile.to_dict())


class TestPostRegression:
    """Regression tests for Post serialization."""

    def test_post_dict_regression(self, data_regression: Any) -> None:
        """Post.to_dict() output should match golden baseline."""
        from datetime import datetime

        from ig_scraper.models import Post

        post = Post(
            id="reg_post_001",
            pk="reg_post_001",
            short_code="REG001",
            url="https://www.instagram.com/p/REG001/",
            type="image",
            caption="Regression test caption #test",
            comment_count=5,
            like_count=50,
            taken_at=datetime(2024, 6, 15, 12, 0, 0),
            owner_username="reguser",
            owner_full_name="Reg User",
            owner_id="123",
            video_url="",
            thumbnail_url="https://example.com/thumb.jpg",
            is_video=False,
            mentions=["@friend"],
            hashtags=["#test"],
            resources=[],
            media_files=[],
            post_folder="posts/001_REG001",
            from_url="https://www.instagram.com/reguser/",
        )
        data_regression.check(post.to_dict())


class TestAnalysisRegression:
    """Regression tests for analysis pipeline output."""

    def test_analysis_markdown_regression(self, file_regression: Any) -> None:
        """Full analysis markdown should match golden baseline."""
        posts = [
            {
                "caption": "Check out this #python project @mentor",
                "likes_count": 100,
                "comments_count": 10,
                "_profile": {
                    "biography": "Python developer",
                    "followers_count": 1000,
                    "follows_count": 200,
                },
                "short_code": "REG01",
                "url": "https://www.instagram.com/p/REG01/",
            },
            {
                "caption": "Another #coding tip for you",
                "likes_count": 50,
                "comments_count": 5,
                "short_code": "REG02",
                "url": "https://www.instagram.com/p/REG02/",
            },
        ]
        comments = [
            {
                "text": "Great tip!",
                "post_url": "https://www.instagram.com/p/REG01/",
            },
            {
                "text": "Thanks for sharing",
                "post_url": "https://www.instagram.com/p/REG02/",
            },
        ]
        md = build_analysis_markdown("regression_user", posts, comments)
        file_regression.check(md, extension=".md")

    def test_comment_grouping_regression(self, data_regression: Any) -> None:
        """group_comments_by_post output should match golden baseline."""
        comments = [
            {"text": "Nice!", "post_url": "https://instagram.com/p/A/"},
            {"text": "Cool!", "post_url": "https://instagram.com/p/A/"},
            {"text": "Wow!", "post_url": "https://instagram.com/p/B/"},
        ]
        grouped = group_comments_by_post(comments)
        # Convert defaultdict keys to sorted list for stable regression
        result = {k: grouped[k] for k in sorted(grouped)}
        data_regression.check(result)


class TestTopWordsRegression:
    """Regression tests for top_words output."""

    def test_top_words_regression(self, data_regression: Any) -> None:
        """top_words output should match golden baseline for fixed input."""
        texts = [
            "Python is great for data science",
            "Data science requires Python skills",
            "Great Python libraries for science projects",
        ]
        result = top_words(texts, limit=5)
        data_regression.check({"top_words": result})
