"""Snapshot tests using inline-snapshot for ig_scraper.

Locks down structural contracts for to_dict() output shapes
and analysis markdown rendering.
"""

from __future__ import annotations

from datetime import datetime

from inline_snapshot import snapshot

from ig_scraper.analysis_render import build_analysis_markdown
from ig_scraper.models import Comment, Post, Profile


class TestProfileSnapshot:
    """Snapshot tests for Profile.to_dict()."""

    def test_profile_to_dict_shape(self) -> None:
        """Profile.to_dict() output shape should not change unexpectedly."""
        profile = Profile(
            id="12345",
            username="testuser",
            full_name="Test User",
            biography="Hello world",
            followers_count=1000,
            follows_count=500,
            posts_count=50,
            verified=True,
            is_business_account=False,
            profile_pic_url="https://example.com/pic.jpg",
            external_url="https://example.com",
            is_private=False,
            igtv_count=0,
        )
        assert profile.to_dict() == snapshot(
            {
                "id": "12345",
                "username": "testuser",
                "full_name": "Test User",
                "biography": "Hello world",
                "followers_count": 1000,
                "follows_count": 500,
                "posts_count": 50,
                "verified": True,
                "is_business_account": False,
                "profile_pic_url": "https://example.com/pic.jpg",
                "external_url": "https://example.com",
                "is_private": False,
                "igtv_count": 0,
                "biography_hashtags": [],
                "biography_mentions": [],
                "business_category_name": "",
            }
        )


class TestPostSnapshot:
    """Snapshot tests for Post.to_dict()."""

    def test_post_to_dict_shape(self) -> None:
        """Post.to_dict() output shape should not change unexpectedly."""
        post = Post(
            id="post_123",
            pk="post_123",
            short_code="ABC123",
            url="https://www.instagram.com/p/ABC123/",
            type="image",
            caption="Test caption",
            comment_count=10,
            like_count=100,
            taken_at=datetime(2024, 1, 15, 12, 0, 0),
            owner_username="poster",
            owner_full_name="Poster Name",
            owner_id="999",
            video_url="",
            thumbnail_url="https://example.com/thumb.jpg",
            is_video=False,
            mentions=["@friend"],
            hashtags=["#photo"],
            resources=[],
            media_files=[],
            post_folder="",
            from_url="",
            view_count=0,
        )
        assert post.to_dict() == snapshot(
            {
                "id": "post_123",
                "pk": "post_123",
                "short_code": "ABC123",
                "url": "https://www.instagram.com/p/ABC123/",
                "type": "image",
                "caption": "Test caption",
                "comment_count": 10,
                "like_count": 100,
                "taken_at": "2024-01-15T12:00:00",
                "owner_username": "poster",
                "owner_full_name": "Poster Name",
                "owner_id": "999",
                "video_url": "",
                "thumbnail_url": "https://example.com/thumb.jpg",
                "is_video": False,
                "mentions": ["@friend"],
                "hashtags": ["#photo"],
                "resources": [],
                "media_files": [],
                "post_folder": "",
                "from_url": "",
                "view_count": 0,
                "location": "",
                "tagged_users": [],
                "sponsor_users": [],
                "video_play_count": 0,
                "video_view_count": 0,
                "is_sponsored": False,
                "title": "",
                "accessibility_caption": "",
                "product_type": "",
            }
        )


class TestCommentSnapshot:
    """Snapshot tests for Comment.to_dict()."""

    def test_comment_to_dict_shape(self) -> None:
        """Comment.to_dict() output shape should not change unexpectedly."""
        comment = Comment(
            post_url="https://instagram.com/p/ABC123",
            comment_url="https://instagram.com/p/ABC123#comment-999",
            id="999",
            text="Great post!",
            owner_username="commenter",
            owner_full_name="Commenter Name",
            owner_profile_pic_url="https://example.com/pic.jpg",
            timestamp="2024-01-15T10:30:00",
            likes_count=5,
            replies_count=2,
        )
        assert comment.to_dict() == snapshot(
            {
                "post_url": "https://instagram.com/p/ABC123",
                "comment_url": "https://instagram.com/p/ABC123#comment-999",
                "id": "999",
                "text": "Great post!",
                "owner_username": "commenter",
                "owner_full_name": "Commenter Name",
                "owner_profile_pic_url": "https://example.com/pic.jpg",
                "timestamp": "2024-01-15T10:30:00",
                "likes_count": 5,
                "replies_count": 2,
                "replies": [],
            }
        )


class TestAnalysisMarkdownSnapshot:
    """Snapshot tests for build_analysis_markdown output."""

    def test_empty_analysis_structure(self) -> None:
        """Analysis markdown with no posts should have expected structure."""
        result = build_analysis_markdown("testuser", [], [])
        lines = result.split("\n")[:5]
        assert lines == snapshot(
            [
                "# Account Analysis",
                "",
                "- Status: analyzed",
                "- Access: instaloader",
                "",
            ]
        )

    def test_analysis_with_posts_structure(self) -> None:
        """Analysis markdown with posts should contain key sections."""
        posts = [
            {
                "caption": "#python is great @mentor",
                "likes_count": 100,
                "comments_count": 10,
                "_profile": {"biography": "Coder", "followers_count": 500},
            }
        ]
        result = build_analysis_markdown("devuser", posts, [])
        section_headers = [line for line in result.split("\n") if line.startswith("## ")]
        assert section_headers == snapshot(
            [
                "## 1. Account Profile",
                "## 2. Pattern Observations",
                "## 3. Swipe-Worthy Posts",
                "## 4. What Doesn't Work",
                "## 5. Strategy Implications",
                "## Access Log",
            ]
        )
