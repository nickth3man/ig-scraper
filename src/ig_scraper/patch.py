"""Runtime patches for upstream instaloader bugs.

Instagram 403'd all ``POST graphql/query`` calls (April 2026).  These patches
bypass ``graphql/query`` entirely, using the iPhone v1 API instead.

TODO: Remove when instaloader > 4.15.1 is released with fixes.
Upstream: https://github.com/instaloader/instaloader/issues/2635
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from instaloader import Post, Profile
from instaloader.exceptions import LoginRequiredException
from instaloader.structures import PostComment, PostCommentAnswer

from ig_scraper.logging_utils import format_kv, get_logger


if TYPE_CHECKING:
    from collections.abc import Iterator


logger = get_logger("patch")


def _build_post_comment(context: Any, node: dict[str, Any], post: Post) -> PostComment:
    """Convert a v1 API comment dict to ``PostComment`` with embedded replies."""
    child_answers = [
        PostCommentAnswer(
            id=int(child["pk"]),
            created_at_utc=datetime.fromtimestamp(child["created_at"], tz=UTC),
            text=child["text"],
            owner=Profile(context, child["user"]),
            likes_count=child.get("comment_like_count", 0),
        )
        for child in node.get("preview_child_comments", [])
    ]
    # PostComment.__init__ expects a GraphQL-style node dict.
    gql_node: dict[str, Any] = {
        "id": node["pk"],
        "text": node["text"],
        "created_at": node["created_at"],
        "owner": node["user"],
        "edge_liked_by": {"count": node.get("comment_like_count", 0)},
        "edge_threaded_comments": {
            "count": node.get("child_comment_count", 0),
            "edges": [{"node": {"id": a.id, "text": a.text}} for a in child_answers],
        },
    }
    return PostComment(context=context, node=gql_node, answers=iter(child_answers), post=post)


class _V1CommentIterator:
    """Cursor-based iterator over ``api/v1/media/{pk}/comments/``."""

    def __init__(self, context: Any, post: Post, media_pk: int) -> None:
        self._context = context
        self._post = post
        self._media_pk = media_pk
        self._next_min_id: str | None = None
        self._buffer: list[PostComment] = []
        self._exhausted = False

    def __iter__(self) -> Iterator[PostComment]:
        return self

    def __next__(self) -> PostComment:
        while not self._buffer and not self._exhausted:
            self._fetch_page()
        if not self._buffer:
            raise StopIteration
        return self._buffer.pop(0)

    def _fetch_page(self) -> None:
        from ig_scraper.config import _sleep

        _sleep("comment page fetch")
        params: dict[str, Any] = {"can_support_threading": "true", "permalink_enabled": "false"}
        if self._next_min_id:
            params["min_id"] = self._next_min_id
        data = self._context.get_iphone_json(
            path=f"api/v1/media/{self._media_pk}/comments/",
            params=params,
        )
        comments = data.get("comments", [])
        if not comments:
            self._exhausted = True
            return
        for node in comments:
            self._buffer.append(_build_post_comment(self._context, node, self._post))
        has_more = data.get("has_more_comments")
        self._next_min_id = data.get("next_min_id")
        if not has_more or not self._next_min_id:
            self._exhausted = True


def apply_instaloader_patches() -> None:
    """Replace graphql/query calls with v1 iPhone API equivalents."""
    logger.info(
        "Applying instaloader API patches | %s",
        format_kv(
            metadata_patch=True,
            profile_posts_patch=True,
            post_comments_patch=True,
        ),
    )

    # Patch 0: Post._obtain_metadata — normalize v1 API keys to GraphQL-style
    # so _field() lookups work.  from_iphone_struct populates _node with some
    # GraphQL keys already (edge_media_preview_like, __typename, etc.), but
    # anything accessed via _field() that falls through to _full_metadata_dict
    # encounters raw v1 keys and raises KeyError.
    def _safe_obtain_metadata(self) -> None:  # type: ignore[no-untyped-def]
        if self._full_metadata_dict:
            return
        iphone = self._node.get("iphone_struct", {})
        if not iphone:
            self._full_metadata_dict = {}
            return
        # Build a GraphQL-compatible dict from v1 API keys.
        gql: dict[str, Any] = {}
        if "comment_count" in iphone:
            gql["edge_media_to_comment"] = {"count": iphone["comment_count"]}
        if "like_count" in iphone:
            gql["edge_media_preview_like"] = {"count": iphone["like_count"]}
        if "media_type" in iphone:
            _type_map = {1: "GraphImage", 2: "GraphVideo", 8: "GraphSidecar"}
            gql["__typename"] = _type_map.get(iphone["media_type"], "")
        if "view_count" in iphone:
            gql["video_view_count"] = iphone["view_count"]
            gql["video_play_count"] = iphone["view_count"]
        if "play_count" in iphone:
            gql["video_play_count"] = iphone["play_count"]
        if "product_type" in iphone:
            gql["product_type"] = iphone["product_type"]
        caption = iphone.get("caption")
        if isinstance(caption, dict) and "text" in caption:
            gql["edge_media_to_caption"] = {"edges": [{"node": {"text": caption["text"]}}]}
        elif isinstance(caption, str):
            gql["edge_media_to_caption"] = {"edges": [{"node": {"text": caption}}]}
        if "title" in iphone:
            gql["title"] = iphone["title"]
        if "accessibility_caption" in iphone:
            gql["accessibility_caption"] = iphone["accessibility_caption"]
        if "location" in iphone:
            gql["location"] = iphone["location"]
        self._full_metadata_dict = gql

    Post._obtain_metadata = _safe_obtain_metadata  # type: ignore[method-assign]  # ty: ignore[invalid-assignment]

    # Patch 1: Profile.get_posts — v1 feed API with next_max_id pagination
    def _patched_get_posts(self) -> Iterator[Post]:  # type: ignore[no-untyped-def]
        next_max_id: str | None = None
        while True:
            params: dict[str, Any] = {"count": 12}
            if next_max_id:
                params["max_id"] = next_max_id
            data = self._context.get_iphone_json(
                path=f"api/v1/feed/user/{self.userid}/",
                params=params,
            )
            items = data.get("items", [])
            for item in items:
                yield Post.from_iphone_struct(self._context, item)
            next_max_id = data.get("next_max_id")
            if not next_max_id or not items:
                break

    Profile.get_posts = _patched_get_posts  # type: ignore[method-assign,assignment]  # ty: ignore[invalid-assignment]

    # Patch 2: Post.get_comments — v1 comments API with next_min_id pagination
    def _patched_get_comments(self) -> Iterator[PostComment]:  # type: ignore[no-untyped-def]
        if not self._context.is_logged_in:
            raise LoginRequiredException("Login required to access comments of a post.")
        # _node["comments"] is the plain int from iphone_struct.
        # self.comments property must NOT be used — it triggers _obtain_metadata().
        comment_count = self._node.get("comments")
        if not comment_count:
            return
        yield from _V1CommentIterator(self._context, self, self.mediaid)

    Post.get_comments = _patched_get_comments  # type: ignore[method-assign]  # ty: ignore[invalid-assignment]
    logger.info("Instaloader API patches applied")
