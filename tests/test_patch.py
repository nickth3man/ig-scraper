"""Tests for src/ig_scraper/patch.py — runtime patches for instalader bugs."""

from __future__ import annotations

import warnings
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from instaloader import Profile

from ig_scraper.patch import (
    _V1CommentIterator,
    _build_post_comment,
    apply_instaloader_patches,
)


warnings.filterwarnings("ignore", category=DeprecationWarning)


@pytest.fixture(autouse=True)
def apply_patches():
    """Apply instaloader patches before each test."""
    apply_instaloader_patches()
    return


@pytest.fixture
def mock_context():
    """Create a mock instaloader Context."""
    context = MagicMock()
    context.is_logged_in = True
    return context


@pytest.fixture
def mock_post(mock_context):
    """Create a mock instaloader Post."""
    post = MagicMock()
    post._context = mock_context
    post.mediaid = 123456789012345
    return post


@pytest.fixture
def mock_profile(mock_context):
    """Create a mock instaloader Profile."""
    profile = MagicMock()
    profile._context = mock_context
    profile.userid = 9876543210
    return profile


class TestBuildPostComment:
    """Tests for _build_post_comment()."""

    @pytest.mark.filterwarnings("ignore::DeprecationWarning")
    def test_happy_path(self, mock_context, mock_post):
        """V1 node dict → PostComment with correct gql_node fields."""
        node = {
            "pk": 111111,
            "text": "Great photo!",
            "created_at": 1710000000,
            "user": {"pk": 100, "username": "commenter1"},
            "comment_like_count": 42,
            "child_comment_count": 3,
        }

        comment = _build_post_comment(mock_context, node, mock_post)

        assert comment.id == 111111
        assert comment.text == "Great photo!"
        # created_at_utc returns naive datetime (utcfromtimestamp), compare
        # as UTC struct to avoid local timezone offsets
        expected = datetime(2024, 3, 9, 16, 0)  # UTC equivalent of 1710000000
        assert comment.created_at_utc == expected
        assert isinstance(comment.owner, Profile)
        assert comment.likes_count == 42

    def test_with_child_comments(self, mock_context, mock_post):
        """Node with preview_child_comments → child PostCommentAnswer objects."""
        node = {
            "pk": 222222,
            "text": "Parent comment",
            "created_at": 1710000100,
            "user": {"pk": 200, "username": "parent_user"},
            "comment_like_count": 5,
            "child_comment_count": 1,
            "preview_child_comments": [
                {
                    "pk": 333333,
                    "text": "Reply comment",
                    "created_at": 1710000200,
                    "user": {"pk": 300, "username": "child_user"},
                    "comment_like_count": 2,
                },
            ],
        }

        comment = _build_post_comment(mock_context, node, mock_post)

        assert comment.id == 222222
        answers = list(comment.answers)
        assert len(answers) == 1
        assert answers[0].id == 333333
        assert answers[0].text == "Reply comment"

    def test_without_optional_fields(self, mock_context, mock_post):
        """Node missing comment_like_count, child_comment_count → defaults to 0."""
        node = {
            "pk": 444444,
            "text": "Minimal comment",
            "created_at": 1710000300,
            "user": {"pk": 400, "username": "minimal_user"},
        }

        comment = _build_post_comment(mock_context, node, mock_post)

        assert comment.id == 444444
        assert comment.likes_count == 0

    def test_empty_child_comments(self, mock_context, mock_post):
        """Node without preview_child_comments key → no child answers."""
        node = {
            "pk": 555555,
            "text": "No replies",
            "created_at": 1710000400,
            "user": {"pk": 500, "username": "lonely_user"},
            "comment_like_count": 0,
            "child_comment_count": 0,
        }

        comment = _build_post_comment(mock_context, node, mock_post)

        answers = list(comment.answers)
        assert len(answers) == 0


class TestV1CommentIterator:
    """Tests for _V1CommentIterator."""

    def test_single_page(self, mock_context, mock_post):
        """Single page of comments → all yielded, then StopIteration."""
        mock_context.get_iphone_json.return_value = {
            "comments": [
                {
                    "pk": 101,
                    "text": "Comment A",
                    "created_at": 1710000001,
                    "user": {"pk": 1, "username": "user_a"},
                    "comment_like_count": 1,
                },
                {
                    "pk": 102,
                    "text": "Comment B",
                    "created_at": 1710000002,
                    "user": {"pk": 2, "username": "user_b"},
                    "comment_like_count": 2,
                },
            ],
            "has_more_comments": False,
            "next_min_id": None,
        }

        with patch("ig_scraper.config._sleep"):
            iterator = _V1CommentIterator(mock_context, mock_post, 123)
            comments = list(iterator)

        assert len(comments) == 2
        assert comments[0].id == 101
        assert comments[1].id == 102

    def test_multi_page(self, mock_context, mock_post):
        """Multi-page pagination → all comments yielded across pages."""
        mock_context.get_iphone_json.side_effect = [
            {
                "comments": [
                    {
                        "pk": 201,
                        "text": "Page 1 comment",
                        "created_at": 1710000010,
                        "user": {"pk": 10, "username": "page1_user"},
                        "comment_like_count": 1,
                    },
                ],
                "has_more_comments": True,
                "next_min_id": "min_id_1",
            },
            {
                "comments": [
                    {
                        "pk": 202,
                        "text": "Page 2 comment",
                        "created_at": 1710000020,
                        "user": {"pk": 20, "username": "page2_user"},
                        "comment_like_count": 2,
                    },
                ],
                "has_more_comments": True,
                "next_min_id": "min_id_2",
            },
            {
                "comments": [
                    {
                        "pk": 203,
                        "text": "Page 3 comment",
                        "created_at": 1710000030,
                        "user": {"pk": 30, "username": "page3_user"},
                        "comment_like_count": 3,
                    },
                ],
                "has_more_comments": False,
                "next_min_id": None,
            },
        ]

        with patch("ig_scraper.config._sleep"):
            iterator = _V1CommentIterator(mock_context, mock_post, 123)
            comments = list(iterator)

        assert len(comments) == 3
        assert comments[0].id == 201
        assert comments[1].id == 202
        assert comments[2].id == 203
        assert mock_context.get_iphone_json.call_count == 3

    def test_empty_first_page(self, mock_context, mock_post):
        """Empty comments list → immediately exhausted."""
        mock_context.get_iphone_json.return_value = {
            "comments": [],
            "has_more_comments": False,
            "next_min_id": None,
        }

        with patch("ig_scraper.config._sleep"):
            iterator = _V1CommentIterator(mock_context, mock_post, 123)
            comments = list(iterator)

        assert len(comments) == 0

    def test_no_more_comments_flag(self, mock_context, mock_post):
        """has_more_comments=False → exhausted after first page."""
        mock_context.get_iphone_json.return_value = {
            "comments": [
                {
                    "pk": 301,
                    "text": "Only page",
                    "created_at": 1710000100,
                    "user": {"pk": 50, "username": "solo_user"},
                    "comment_like_count": 0,
                },
            ],
            "has_more_comments": False,
            "next_min_id": None,
        }

        with patch("ig_scraper.config._sleep"):
            iterator = _V1CommentIterator(mock_context, mock_post, 123)
            comments = list(iterator)

        assert len(comments) == 1
        mock_context.get_iphone_json.assert_called_once()


class TestSafeObtainMetadata:
    """Tests for _safe_obtain_metadata (Patch 0)."""

    def test_already_cached(self):
        """_full_metadata_dict already set → early return, no processing."""
        from instaloader import Post

        post = MagicMock(spec=Post)
        post._full_metadata_dict = {"already": "cached"}
        post._node = {}

        Post._obtain_metadata(post)

        assert post._full_metadata_dict == {"already": "cached"}

    def test_no_iphone_struct(self):
        """_node.get('iphone_struct', {}) returns empty → _full_metadata_dict = {}."""
        from instaloader import Post

        post = MagicMock(spec=Post)
        post._full_metadata_dict = {}
        post._node = {}

        Post._obtain_metadata(post)

        assert post._full_metadata_dict == {}

    def test_full_iphone_struct_with_all_keys(self):
        """Full iphone_struct → correct GraphQL mapping for each field."""
        from instaloader import Post

        post = MagicMock(spec=Post)
        post._full_metadata_dict = {}
        post._node = {
            "iphone_struct": {
                "comment_count": 100,
                "like_count": 500,
                "media_type": 1,
                "view_count": 1000,
                "play_count": 2000,
                "product_type": "feed",
                "caption": {"text": "Test caption"},
                "title": "Test Title",
                "accessibility_caption": "Image description",
                "location": {"pk": 1, "name": "Test Location"},
            },
        }

        Post._obtain_metadata(post)

        gql = post._full_metadata_dict
        assert gql["edge_media_to_comment"] == {"count": 100}
        assert gql["edge_media_preview_like"] == {"count": 500}
        assert gql["__typename"] == "GraphImage"
        assert gql["video_view_count"] == 1000
        assert gql["video_play_count"] == 2000
        assert gql["product_type"] == "feed"
        assert gql["edge_media_to_caption"] == {"edges": [{"node": {"text": "Test caption"}}]}
        assert gql["title"] == "Test Title"
        assert gql["accessibility_caption"] == "Image description"
        assert gql["location"] == {"pk": 1, "name": "Test Location"}

    def test_media_type_graphvideo(self):
        """media_type=2 → GraphVideo."""
        from instaloader import Post

        post = MagicMock(spec=Post)
        post._full_metadata_dict = {}
        post._node = {"iphone_struct": {"media_type": 2}}

        Post._obtain_metadata(post)

        assert post._full_metadata_dict["__typename"] == "GraphVideo"

    def test_media_type_graphsidecar(self):
        """media_type=8 → GraphSidecar."""
        from instaloader import Post

        post = MagicMock(spec=Post)
        post._full_metadata_dict = {}
        post._node = {"iphone_struct": {"media_type": 8}}

        Post._obtain_metadata(post)

        assert post._full_metadata_dict["__typename"] == "GraphSidecar"

    def test_media_type_unknown(self):
        """Unknown media_type → empty string."""
        from instaloader import Post

        post = MagicMock(spec=Post)
        post._full_metadata_dict = {}
        post._node = {"iphone_struct": {"media_type": 99}}

        Post._obtain_metadata(post)

        assert post._full_metadata_dict["__typename"] == ""

    def test_caption_as_dict_with_text(self):
        """Caption as dict with text key → edge_media_to_caption mapped."""
        from instaloader import Post

        post = MagicMock(spec=Post)
        post._full_metadata_dict = {}
        post._node = {"iphone_struct": {"caption": {"text": "hello"}}}

        Post._obtain_metadata(post)

        assert post._full_metadata_dict["edge_media_to_caption"] == {
            "edges": [{"node": {"text": "hello"}}]
        }

    def test_caption_as_string(self):
        """Caption as string → edge_media_to_caption mapped."""
        from instaloader import Post

        post = MagicMock(spec=Post)
        post._full_metadata_dict = {}
        post._node = {"iphone_struct": {"caption": "hello"}}

        Post._obtain_metadata(post)

        assert post._full_metadata_dict["edge_media_to_caption"] == {
            "edges": [{"node": {"text": "hello"}}]
        }

    def test_caption_as_none(self):
        """Caption as None → no edge_media_to_caption key."""
        from instaloader import Post

        post = MagicMock(spec=Post)
        post._full_metadata_dict = {}
        post._node = {"iphone_struct": {"caption": None}}

        Post._obtain_metadata(post)

        assert "edge_media_to_caption" not in post._full_metadata_dict


class TestPatchedGetPosts:
    """Tests for _patched_get_posts (Patch 1)."""

    def test_single_page_with_items(self, mock_profile):
        """Single page of items → yields Posts."""
        from instaloader import Post

        mock_post1 = MagicMock(spec=Post)
        mock_post2 = MagicMock(spec=Post)
        with patch.object(Post, "from_iphone_struct", side_effect=[mock_post1, mock_post2]):
            mock_profile._context.get_iphone_json.return_value = {
                "items": [
                    {
                        "pk": 111,
                        "id": "111_222",
                        "code": "TESTCODE1",
                        "media_type": 1,
                        "caption": {"text": "Post 1"},
                        "like_count": 10,
                        "comment_count": 5,
                    },
                    {
                        "pk": 222,
                        "id": "222_333",
                        "code": "TESTCODE2",
                        "media_type": 2,
                        "caption": {"text": "Post 2"},
                        "like_count": 20,
                        "comment_count": 10,
                    },
                ],
                "next_max_id": None,
            }

            with patch("ig_scraper.config._sleep"):
                posts = list(Profile.get_posts(mock_profile))

        assert len(posts) == 2
        mock_profile._context.get_iphone_json.assert_called_once()

    def test_multi_page(self, mock_profile):
        """Multi-page pagination → yields from all pages, stops when no next_max_id."""
        from instaloader import Post

        mock_posts = [MagicMock(spec=Post) for _ in range(3)]
        with patch.object(Post, "from_iphone_struct", side_effect=mock_posts):
            mock_profile._context.get_iphone_json.side_effect = [
                {
                    "items": [
                        {"pk": 301, "id": "301_401", "code": "CODE1", "media_type": 1},
                    ],
                    "next_max_id": "max_id_1",
                },
                {
                    "items": [
                        {"pk": 302, "id": "302_402", "code": "CODE2", "media_type": 1},
                    ],
                    "next_max_id": "max_id_2",
                },
                {
                    "items": [
                        {"pk": 303, "id": "303_403", "code": "CODE3", "media_type": 1},
                    ],
                    "next_max_id": None,
                },
            ]

            with patch("ig_scraper.config._sleep"):
                posts = list(Profile.get_posts(mock_profile))

        assert len(posts) == 3
        assert mock_profile._context.get_iphone_json.call_count == 3

    def test_empty_items(self, mock_profile):
        """Empty items list → stops immediately, yields nothing."""
        mock_profile._context.get_iphone_json.return_value = {
            "items": [],
            "next_max_id": None,
        }

        with patch("ig_scraper.config._sleep"):
            posts = list(Profile.get_posts(mock_profile))

        assert len(posts) == 0


class TestPatchedGetComments:
    """Tests for _patched_get_comments (Patch 2)."""

    def test_not_logged_in(self):
        """context.is_logged_in=False → raises LoginRequiredException."""
        from instaloader import Post
        from instaloader.exceptions import LoginRequiredException

        mock_context = MagicMock()
        mock_context.is_logged_in = False

        mock_post = MagicMock()
        mock_post._context = mock_context
        mock_post.mediaid = 123

        with pytest.raises(LoginRequiredException):
            for _ in Post.get_comments(mock_post):
                pass

    def test_zero_comment_count(self, mock_context):
        """comments=0 in node → returns immediately, yields nothing."""
        mock_post = MagicMock()
        mock_post._context = mock_context
        mock_post._context.is_logged_in = True
        mock_post.mediaid = 123
        mock_post._node = {"comments": 0}

        from instaloader import Post

        comments = list(Post.get_comments(mock_post))
        assert len(comments) == 0

    def test_has_comments(self, mock_context, mock_post):
        """comments=5 in node → yields from _V1CommentIterator."""
        mock_post._context.is_logged_in = True
        mock_post._node = {"comments": 5}
        mock_post._context.get_iphone_json.return_value = {
            "comments": [
                {
                    "pk": 901,
                    "text": "Nice post!",
                    "created_at": 1710001000,
                    "user": {"pk": 90, "username": "fan1"},
                    "comment_like_count": 3,
                },
            ],
            "has_more_comments": False,
            "next_min_id": None,
        }

        from instaloader import Post

        with patch("ig_scraper.config._sleep"):
            comments = list(Post.get_comments(mock_post))

        assert len(comments) == 1
        assert comments[0].id == 901
