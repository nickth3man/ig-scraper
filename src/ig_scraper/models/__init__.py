"""Typed dataclass models for Instagram scraping data (Profile, Post, Comment)."""

from ig_scraper.models.comment import Comment
from ig_scraper.models.post import Post, PostResource
from ig_scraper.models.profile import Profile


__all__ = [
    "Comment",
    "Post",
    "PostResource",
    "Profile",
]
