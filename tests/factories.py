"""Polyfactory factories for ig_scraper dataclass models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from polyfactory import Ignore
from polyfactory.factories import DataclassFactory

from ig_scraper.models import Comment, Post, PostResource, Profile


class ProfileFactory(DataclassFactory[Profile]):
    """Factory for Profile dataclass instances."""

    __model__ = Profile
    _method = Ignore()


class PostResourceFactory(DataclassFactory[PostResource]):
    """Factory for PostResource dataclass instances."""

    __model__ = PostResource


class PostFactory(DataclassFactory[Post]):
    """Factory for Post dataclass instances."""

    __model__ = Post
    _profile = Ignore()
    taken_at = datetime(2024, 6, 15, 12, 0, 0)
    resources = PostResourceFactory.batch(size=0)
    title = ""
    accessibility_caption = ""
    product_type = ""


class CommentFactory(DataclassFactory[Comment]):
    """Factory for Comment dataclass instances."""

    __model__ = Comment
    replies: list[dict[str, Any]] = []

    @staticmethod
    def build_replies(count: int = 2) -> list[dict[str, Any]]:
        """Generate a list of reply dicts matching the extracted replies schema."""
        return [
            {
                "id": str(12345 + i),
                "text": f"Reply text {i}",
                "created_at": str(datetime(2024, 1, 15, 10 + i, 30, 0)),
                "owner_username": f"replier_{i}",
                "likes_count": i * 2,
            }
            for i in range(count)
        ]
