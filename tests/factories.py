"""Polyfactory factories for ig_scraper dataclass models."""

from __future__ import annotations

from datetime import datetime

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


class CommentFactory(DataclassFactory[Comment]):
    """Factory for Comment dataclass instances."""

    __model__ = Comment
