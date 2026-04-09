"""Instagram scraper package for collecting account data, posts, and comments."""

from ig_scraper.analysis import clean_handle
from ig_scraper.client import get_instagram_client
from ig_scraper.models import Comment, Post, PostResource, Profile
from ig_scraper.scraper import fetch_profile_posts_and_comments


__all__ = [
    "Comment",
    "Post",
    "PostResource",
    "Profile",
    "clean_handle",
    "fetch_profile_posts_and_comments",
    "get_instagram_client",
]
