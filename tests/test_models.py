"""Tests for models.py — typed dataclass models."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from ig_scraper.models import Comment, Post, PostResource, Profile


class TestProfile:
    """Tests for Profile model."""

    def test_profile_to_dict(self):
        """Test Profile.to_dict serializes all fields."""
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
        )
        result = profile.to_dict()
        assert result["id"] == "12345"
        assert result["username"] == "testuser"
        assert result["full_name"] == "Test User"
        assert result["followers_count"] == 1000
        assert result["verified"] is True
        assert "_method" not in result  # excluded from repr

    def test_profile_to_dict_excludes_method_field(self):
        """Test that _method field is not serialized."""
        profile = Profile(
            id="123",
            username="user",
            full_name="",
            biography="",
            followers_count=0,
            follows_count=0,
            posts_count=0,
            verified=False,
            is_business_account=False,
            profile_pic_url="",
            external_url="",
            _method="instagrapi",
        )
        data = profile.to_dict()
        assert "_method" not in data

    def test_profile_from_instagrapi_user(self):
        """Test Profile.from_instagrapi_user maps instagrapi fields correctly."""
        mock_user = MagicMock()
        mock_user.pk = 99999
        mock_user.username = "insta_user"
        mock_user.full_name = "Instagram User"
        mock_user.biography = "My bio"
        mock_user.follower_count = 1500
        mock_user.following_count = 300
        mock_user.media_count = 75
        mock_user.is_verified = True
        mock_user.is_business = True
        mock_user.profile_pic_url = "https://example.com/profile.jpg"
        mock_user.external_url = "https://example.com"

        profile = Profile.from_instagrapi_user(mock_user)

        assert profile.id == "99999"
        assert profile.username == "insta_user"
        assert profile.full_name == "Instagram User"
        assert profile.biography == "My bio"
        assert profile.followers_count == 1500
        assert profile.follows_count == 300
        assert profile.posts_count == 75
        assert profile.verified is True
        assert profile.is_business_account is True

    def test_profile_from_instagrapi_user_with_defaults(self):
        """Test Profile.from_instagrapi_user handles missing attributes gracefully."""
        mock_user = MagicMock(spec=[])
        # All getattr calls will return None via default
        profile = Profile.from_instagrapi_user(mock_user)

        assert profile.id == ""
        assert profile.username == ""
        assert profile.followers_count == 0


class TestPostResource:
    """Tests for PostResource model."""

    def test_post_resource_creation(self):
        """Test PostResource can be created with all fields."""
        resource = PostResource(
            pk="resource_123",
            media_type=1,
            thumbnail_url="https://example.com/thumb.jpg",
            video_url="",
        )
        assert resource.pk == "resource_123"
        assert resource.media_type == 1

    def test_post_resource_default_empty_urls(self):
        """Test PostResource defaults video_url and thumbnail_url to empty strings."""
        resource = PostResource(pk="abc", media_type=1, thumbnail_url="", video_url="")
        assert resource.thumbnail_url == ""
        assert resource.video_url == ""


class TestPost:
    """Tests for Post model."""

    def test_post_to_dict_serializes_all_fields(self):
        """Test Post.to_dict includes all fields including resources."""
        post = Post(
            id="post_123",
            pk="post_123",
            short_code="ABC123",
            url="https://instagram.com/p/ABC123",
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
            resources=[PostResource(pk="res1", media_type=1, thumbnail_url="", video_url="")],
            media_files=["image1.jpg"],
            post_folder="posts/001_ABC123",
            from_url="https://instagram.com/poster/",
        )
        data = post.to_dict()
        assert data["id"] == "post_123"
        assert data["short_code"] == "ABC123"
        assert data["caption"] == "Test caption"
        assert data["comment_count"] == 10
        assert data["like_count"] == 100
        assert len(data["resources"]) == 1

    def test_post_to_dict_datetime_converted_to_isoformat(self):
        """Test that datetime taken_at is serialized as ISO string."""
        post = Post(
            id="123",
            pk="123",
            short_code="XYZ",
            url="",
            type="",
            caption="",
            comment_count=0,
            like_count=0,
            taken_at=datetime(2024, 6, 1, 10, 30, 45),
            owner_username="",
            owner_full_name="",
            owner_id="",
            video_url="",
            thumbnail_url="",
            is_video=False,
        )
        data = post.to_dict()
        assert "2024-06-01T10:30:45" in data["taken_at"]

    def test_post_to_dict_non_datetime_taken_at(self):
        """Test that non-datetime taken_at is converted to string."""
        post = Post(
            id="123",
            pk="123",
            short_code="XYZ",
            url="",
            type="",
            caption="",
            comment_count=0,
            like_count=0,
            taken_at="2024-07-01",
            owner_username="",
            owner_full_name="",
            owner_id="",
            video_url="",
            thumbnail_url="",
            is_video=False,
        )
        data = post.to_dict()
        assert data["taken_at"] == "2024-07-01"

    def test_post_to_dict_none_taken_at(self):
        """Test that None taken_at becomes empty string."""
        post = Post(
            id="123",
            pk="123",
            short_code="XYZ",
            url="",
            type="",
            caption="",
            comment_count=0,
            like_count=0,
            taken_at=None,
            owner_username="",
            owner_full_name="",
            owner_id="",
            video_url="",
            thumbnail_url="",
            is_video=False,
        )
        data = post.to_dict()
        assert data["taken_at"] == ""

    def test_post_from_instagrapi_media(self):
        """Test Post.from_instagrapi_media correctly maps media fields."""
        mock_media = MagicMock()
        mock_media.pk = 77777
        mock_media.code = "DEF456"
        mock_media.product_type = "clips"
        mock_media.caption_text = "My video caption"
        mock_media.comment_count = 5
        mock_media.like_count = 200
        mock_media.taken_at = datetime(2024, 3, 20, 8, 0, 0)
        mock_media.media_type = 2  # video
        mock_media.video_url = "https://example.com/video.mp4"
        mock_media.thumbnail_url = "https://example.com/thumb.jpg"
        mock_media.resources = []

        post = Post.from_instagrapi_media(mock_media, "poster_name", "Poster Full Name", "88888")

        assert post.id == "77777"
        assert post.pk == "77777"
        assert post.short_code == "DEF456"
        assert "reel" in post.url  # clips -> reel
        assert post.type == "clips"
        assert post.caption == "My video caption"
        assert post.comment_count == 5
        assert post.like_count == 200
        assert post.is_video is True
        assert post.owner_username == "poster_name"

    def test_post_from_instagrapi_media_carousel(self):
        """Test Post.from_instagrapi_media handles albums/carousels."""
        mock_resource = MagicMock()
        mock_resource.pk = "res_001"
        mock_resource.media_type = 8
        mock_resource.thumbnail_url = "https://example.com/res_thumb.jpg"
        mock_resource.video_url = ""

        mock_media = MagicMock()
        mock_media.pk = 55555
        mock_media.code = "CAROUSEL1"
        mock_media.product_type = ""
        mock_media.media_type = 8  # album
        mock_media.caption_text = "Album post"
        mock_media.comment_count = 0
        mock_media.like_count = 50
        mock_media.taken_at = None
        mock_media.video_url = ""
        mock_media.thumbnail_url = ""
        mock_media.resources = [mock_resource]

        post = Post.from_instagrapi_media(mock_media, "cuser", "Carousel User", "33333")

        assert len(post.resources) == 1
        assert post.resources[0].pk == "res_001"
        assert post.resources[0].media_type == 8


class TestComment:
    """Tests for Comment model (no 'replies' field in current contract)."""

    def test_comment_to_dict_serializes_replies_count_not_replies_list(self):
        """Test Comment.to_dict includes replies_count but NOT a replies list."""
        comment = Comment(
            post_url="https://instagram.com/p/ABC123",
            comment_url="https://instagram.com/p/ABC123#comment-999",
            id="999",
            text="Great post!",
            owner_username="commenter",
            owner_full_name="Commenter Name",
            owner_profile_pic_url="https://example.com/commenter.jpg",
            timestamp="2024-01-15T10:30:00",
            likes_count=5,
            replies_count=2,
        )
        data = comment.to_dict()
        assert data["id"] == "999"
        assert data["text"] == "Great post!"
        assert data["replies_count"] == 2
        # Comment model does NOT have a 'replies' field
        assert "replies" not in data

    def test_comment_from_instagrapi_comment(self):
        """Test Comment.from_instagrapi_comment correctly maps fields."""
        mock_user = MagicMock()
        mock_user.username = "commenter"
        mock_user.full_name = "Commenter Name"
        mock_user.profile_pic_url = "https://example.com/pic.jpg"

        mock_comment = MagicMock()
        mock_comment.pk = 12345
        mock_comment.text = "Nice photo"
        mock_comment.user = mock_user
        mock_comment.created_at_utc = datetime(2024, 2, 1, 14, 30, 0)
        mock_comment.like_count = 10
        mock_comment.child_comment_count = 3

        comment = Comment.from_instagrapi_comment(mock_comment, "https://instagram.com/p/XYZ")

        assert comment.id == "12345"
        assert comment.text == "Nice photo"
        assert comment.owner_username == "commenter"
        assert comment.likes_count == 10
        assert comment.replies_count == 3

    def test_comment_from_instagrapi_comment_no_user(self):
        """Test Comment.from_instagrapi_comment handles missing user gracefully."""
        mock_comment = MagicMock(spec=[])
        mock_comment.pk = 111
        mock_comment.text = "Hello"
        mock_comment.user = None
        mock_comment.created_at_utc = None
        mock_comment.like_count = None
        mock_comment.child_comment_count = None

        comment = Comment.from_instagrapi_comment(mock_comment, "https://instagram.com/p/XYZ")

        assert comment.owner_username == ""
        assert comment.owner_full_name == ""
        assert comment.likes_count == 0
        assert comment.replies_count == 0
