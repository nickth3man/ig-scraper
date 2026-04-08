"""Instagram scraper package for collecting account data, posts, and comments."""

from ig_scraper.analysis import clean_handle
from ig_scraper.instagram_client import get_instagram_client
from ig_scraper.instagrapi_fallback import fetch_profile_posts_and_comments
from ig_scraper.models import Comment, Post, PostResource, Profile


__all__ = [
    "Comment",
    "Post",
    "PostResource",
    "Profile",
    "clean_handle",
    "fetch_profile_posts_and_comments",
    "get_instagram_client",
]
