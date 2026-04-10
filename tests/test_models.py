"""Tests for models.py — typed dataclass models."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from ig_scraper.models import Comment, Post, PostResource, Profile
from ig_scraper.models.post import _safe_attr


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
            _method="instaloader",
        )
        data = profile.to_dict()
        assert "_method" not in data


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
            title="My Post Title",
            accessibility_caption="A photo of a sunset",
            product_type="feed",
        )
        data = post.to_dict()
        assert data["id"] == "post_123"
        assert data["short_code"] == "ABC123"
        assert data["caption"] == "Test caption"
        assert data["comment_count"] == 10
        assert data["like_count"] == 100
        assert len(data["resources"]) == 1
        assert data["title"] == "My Post Title"
        assert data["accessibility_caption"] == "A photo of a sunset"
        assert data["product_type"] == "feed"

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

    def test_post_new_fields_default_to_empty_string(self):
        """Test that title, accessibility_caption, product_type default to empty strings."""
        post = Post(
            id="1",
            pk="1",
            short_code="X",
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
        assert data["title"] == ""
        assert data["accessibility_caption"] == ""
        assert data["product_type"] == ""

    def test_post_from_instaloader_with_new_fields(self):
        """Test from_instaloader_post maps title, accessibility_caption, product_type."""
        mock_post = MagicMock()
        mock_post.mediaid = "12345"
        mock_post.shortcode = "NEW123"
        mock_post.typename = "GraphVideo"
        mock_post.caption = ""
        mock_post.date_utc = MagicMock()
        mock_post.likes = 10
        mock_post.comments = 5
        mock_post.url = "https://example.com"
        mock_post.is_video = True
        mock_post.resources = []
        mock_post.caption_hashtags = []
        mock_post.caption_mentions = []
        mock_post.tagged_users = []
        mock_post.sponsor_users = []
        mock_post.view_count = 100
        mock_post.video_play_count = 50
        mock_post.video_view_count = 75
        mock_post.is_sponsored = False
        mock_post.title = "Video Title"
        mock_post.accessibility_caption = "A video clip"
        mock_post.product_type = "clips"
        mock_post.video_url = "https://example.com/video.mp4"
        mock_post.location = None

        post = Post.from_instaloader_post(
            mock_post,
            username="testuser",
            user_full_name="Test User",
            user_id="999",
        )

        assert post.title == "Video Title"
        assert post.accessibility_caption == "A video clip"
        assert post.product_type == "clips"
        data = post.to_dict()
        assert data["title"] == "Video Title"
        assert data["accessibility_caption"] == "A video clip"
        assert data["product_type"] == "clips"

    def test_post_from_instaloader_new_fields_missing(self):
        """Test from_instaloader_post defaults to empty when new fields are missing."""
        mock_post = MagicMock()
        mock_post.mediaid = "67890"
        mock_post.shortcode = "MISS"
        mock_post.typename = "GraphImage"
        mock_post.caption = ""
        mock_post.date_utc = MagicMock()
        mock_post.likes = 0
        mock_post.comments = 0
        mock_post.url = ""
        mock_post.is_video = False
        mock_post.resources = []
        mock_post.caption_hashtags = []
        mock_post.caption_mentions = []
        mock_post.tagged_users = []
        mock_post.sponsor_users = []
        mock_post.view_count = 0
        mock_post.video_play_count = 0
        mock_post.video_view_count = 0
        mock_post.is_sponsored = False
        mock_post.video_url = ""
        mock_post.location = None
        # Simulate missing new fields via side_effect
        mock_post.title = None
        mock_post.accessibility_caption = None
        mock_post.product_type = None

        post = Post.from_instaloader_post(
            mock_post,
            username="testuser",
            user_full_name="Test User",
            user_id="999",
        )

        assert post.title == ""
        assert post.accessibility_caption == ""
        assert post.product_type == ""


class TestComment:
    """Tests for Comment model."""

    def test_comment_to_dict_includes_replies(self):
        """Test Comment.to_dict includes replies list."""
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
        assert "replies" in data
        assert data["replies"] == []

    def test_from_instaloader_comment_with_answers(self):
        """Test from_instaloader_comment extracts replies from comment.answers."""
        media_url = "https://instagram.com/p/ABC123"
        mock_answer = MagicMock()
        mock_answer.id = 12345
        mock_answer.text = "Reply text"
        mock_answer.created_at_utc = datetime(2024, 2, 10, 8, 0, 0)
        mock_owner = MagicMock()
        mock_owner.username = "replier"
        mock_answer.owner = mock_owner
        mock_answer.likes_count = 5

        mock_comment = MagicMock()
        mock_comment.id = 999
        mock_comment.text = "Original comment"
        mock_comment.created_at_utc = datetime(2024, 1, 15, 10, 30, 0)
        mock_comment.likes_count = 10
        mock_comment.answers_count = 1
        mock_comment.answers = [mock_answer]
        owner = MagicMock()
        owner.username = "commenter"
        owner.full_name = "Commenter Name"
        owner.profile_pic_url = "https://example.com/pic.jpg"
        mock_comment.owner = owner

        result = Comment.from_instaloader_comment(mock_comment, media_url)

        assert result.id == "999"
        assert result.text == "Original comment"
        assert result.replies_count == 1
        assert len(result.replies) == 1
        assert result.replies[0]["id"] == "12345"
        assert result.replies[0]["text"] == "Reply text"
        assert result.replies[0]["owner_username"] == "replier"
        assert result.replies[0]["likes_count"] == 5

        data = result.to_dict()
        assert data["replies"][0]["id"] == "12345"
        assert data["replies"][0]["owner_username"] == "replier"

    def test_from_instaloader_comment_without_answers(self):
        """Test from_instaloader_comment with no answers yields empty replies."""
        media_url = "https://instagram.com/p/XYZ789"
        mock_comment = MagicMock()
        mock_comment.id = 555
        mock_comment.text = "Solo comment"
        mock_comment.created_at_utc = datetime(2024, 3, 1, 14, 0, 0)
        mock_comment.likes_count = 0
        mock_comment.answers_count = 0
        mock_comment.answers = None
        owner = MagicMock()
        owner.username = "lone_user"
        owner.full_name = ""
        owner.profile_pic_url = ""
        mock_comment.owner = owner

        result = Comment.from_instaloader_comment(mock_comment, media_url)

        assert result.replies == []
        assert result.replies_count == 0
        data = result.to_dict()
        assert data["replies"] == []

    def test_from_instaloader_comment_answer_without_owner(self):
        """Test reply extraction when answer has no owner."""
        media_url = "https://instagram.com/p/NOOWNER"
        mock_answer = MagicMock()
        mock_answer.id = 777
        mock_answer.text = "No owner reply"
        mock_answer.created_at_utc = datetime(2024, 4, 1, 12, 0, 0)
        mock_answer.owner = None
        mock_answer.likes_count = 0

        mock_comment = MagicMock()
        mock_comment.id = 888
        mock_comment.text = "Parent comment"
        mock_comment.created_at_utc = datetime(2024, 4, 1, 11, 0, 0)
        mock_comment.likes_count = 1
        mock_comment.answers_count = 1
        mock_comment.answers = [mock_answer]
        mock_comment.owner = MagicMock(
            username="parent_user", full_name="Parent", profile_pic_url=""
        )

        result = Comment.from_instaloader_comment(mock_comment, media_url)

        assert len(result.replies) == 1
        assert result.replies[0]["owner_username"] == ""


class TestSafeAttr:
    """Tests for _safe_attr helper function."""

    def test_safe_attr_with_key_error_returns_default(self):
        """Test _safe_attr returns default when getattr raises KeyError."""

        class RaisesKeyError:
            def __getattribute__(self, name):
                raise KeyError(name)

        obj = RaisesKeyError()
        result = _safe_attr(obj, "missing", "default_val")

        assert result == "default_val"

    def test_safe_attr_with_type_error_returns_default(self):
        """Test _safe_attr returns default when getattr raises TypeError."""

        class RaisesTypeError:
            def __getattribute__(self, name):
                raise TypeError("type error")

        obj = RaisesTypeError()
        result = _safe_attr(obj, "field", "fallback")

        assert result == "fallback"

    def test_safe_attr_with_valid_attribute_returns_value(self):
        """Test _safe_attr returns actual value when attribute exists."""
        mock_obj = MagicMock()
        mock_obj.field = "actual_value"

        result = _safe_attr(mock_obj, "field", "default")

        assert result == "actual_value"

    def test_safe_attr_with_default_value_none(self):
        """Test _safe_attr returns None as default when specified."""
        mock_obj = MagicMock(spec=[])
        del mock_obj.missing

        result = _safe_attr(mock_obj, "missing", None)

        assert result is None


class TestPostLocation:
    """Tests for Post.from_instaloader_post location handling."""

    def test_post_from_instaloader_with_location_having_key_error(self):
        """Test location construction with KeyError on lat still creates location dict."""

        class LocationWithKeyError:
            """Mock location that raises KeyError on lat access."""

            def __getattr__(self, name):
                if name in ("lat", "lng", "name"):
                    raise KeyError(name)
                raise AttributeError(name)

        mock_post = MagicMock()
        mock_post.mediaid = "12345"
        mock_post.shortcode = "TEST123"
        mock_post.typename = "GraphImage"
        mock_post.caption = ""
        mock_post.date_utc = MagicMock()
        mock_post.likes = 10
        mock_post.comments = 5
        mock_post.url = "https://example.com"
        mock_post.is_video = False
        mock_post.resources = []
        mock_post.caption_hashtags = []
        mock_post.caption_mentions = []
        mock_post.tagged_users = []
        mock_post.sponsor_users = []
        mock_post.view_count = 0
        mock_post.video_play_count = 0
        mock_post.video_view_count = 0
        mock_post.is_sponsored = False
        mock_post.location = LocationWithKeyError()

        post = Post.from_instaloader_post(
            mock_post,
            username="testuser",
            user_full_name="Test User",
            user_id="999",
        )

        # Should not raise — KeyError in location.lat should be caught
        assert post.location == ""
        assert isinstance(post, Post)
