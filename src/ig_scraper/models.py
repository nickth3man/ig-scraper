"""Typed dataclass models for Instagram scraping data (Profile, Post, Comment)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Profile:
    """Instagram user profile information."""

    id: str
    username: str
    full_name: str
    biography: str
    followers_count: int
    follows_count: int
    posts_count: int
    verified: bool
    is_business_account: bool
    profile_pic_url: str
    external_url: str
    _method: str = field(default="instagrapi", repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {k: v for k, v in asdict(self).items() if not k.startswith("_")}

    @classmethod
    def from_instagrapi_user(cls, user: Any, method: str = "instagrapi") -> Profile:
        """Create Profile from instagrapi User object."""
        return cls(
            id=str(getattr(user, "pk", "")),
            username=getattr(user, "username", ""),
            full_name=getattr(user, "full_name", ""),
            biography=getattr(user, "biography", ""),
            followers_count=getattr(user, "follower_count", 0),
            follows_count=getattr(user, "following_count", 0),
            posts_count=getattr(user, "media_count", 0),
            verified=getattr(user, "is_verified", False),
            is_business_account=getattr(user, "is_business", False),
            profile_pic_url=str(getattr(user, "profile_pic_url", "") or ""),
            external_url=str(getattr(user, "external_url", "") or ""),
            _method=method,
        )


@dataclass
class PostResource:
    """Media resource (image/video) within a post."""

    pk: str
    media_type: int
    thumbnail_url: str
    video_url: str


@dataclass
class Post:
    """Instagram post/media item."""

    id: str
    pk: str
    short_code: str
    url: str
    type: str
    caption: str
    comment_count: int
    like_count: int
    taken_at: datetime | str | None
    owner_username: str
    owner_full_name: str
    owner_id: str
    video_url: str
    thumbnail_url: str
    is_video: bool
    mentions: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    resources: list[PostResource] = field(default_factory=list)
    media_files: list[str] = field(default_factory=list)
    post_folder: str = ""
    from_url: str = ""
    _profile: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_instagrapi_media(
        cls, media: Any, username: str, user_full_name: str, user_pk: str
    ) -> Post:
        """Create Post from instagrapi Media object."""
        kind = "reel" if getattr(media, "product_type", "") == "clips" else "p"
        code = getattr(media, "code", "")
        url = f"https://www.instagram.com/{kind}/{code}/"
        resources = [
            PostResource(
                pk=str(getattr(r, "pk", "")),
                media_type=int(getattr(r, "media_type", 0)),
                thumbnail_url=str(getattr(r, "thumbnail_url", "")),
                video_url=str(getattr(r, "video_url", "")),
            )
            for r in getattr(media, "resources", [])
        ]
        return cls(
            id=str(getattr(media, "pk", "")),
            pk=str(getattr(media, "pk", "")),
            short_code=code,
            url=url,
            type=str(getattr(media, "product_type", "") or getattr(media, "media_type", "")),
            caption=getattr(media, "caption_text", "") or "",
            comment_count=getattr(media, "comment_count", 0) or 0,
            like_count=getattr(media, "like_count", 0) or 0,
            taken_at=getattr(media, "taken_at", None),
            owner_username=username,
            owner_full_name=user_full_name,
            owner_id=str(user_pk),
            video_url=str(getattr(media, "video_url", "")),
            thumbnail_url=str(getattr(media, "thumbnail_url", "")),
            is_video=getattr(media, "media_type", 0) == 2,
            resources=resources,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        # Filter private fields
        d = {k: v for k, v in d.items() if not k.startswith("_")}
        # Convert datetime
        d["taken_at"] = (
            self.taken_at.isoformat()
            if isinstance(self.taken_at, datetime)
            else str(self.taken_at)
            if self.taken_at
            else ""
        )
        return d


@dataclass
class Comment:
    """Instagram comment on a post."""

    post_url: str
    comment_url: str
    id: str
    text: str
    owner_username: str
    owner_full_name: str
    owner_profile_pic_url: str
    timestamp: str
    likes_count: int
    replies_count: int

    @classmethod
    def from_instagrapi_comment(cls, comment: Any, media_url: str) -> Comment:
        """Create Comment from instagrapi Comment object."""
        user = getattr(comment, "user", None)
        return cls(
            post_url=media_url,
            comment_url=f"{media_url}#comment-{getattr(comment, 'pk', '')}",
            id=str(getattr(comment, "pk", "")),
            text=getattr(comment, "text", "") or "",
            owner_username=getattr(user, "username", "") if user else "",
            owner_full_name=getattr(user, "full_name", "") if user else "",
            owner_profile_pic_url=str(getattr(user, "profile_pic_url", "")) if user else "",
            timestamp=str(getattr(comment, "created_at_utc", "")),
            likes_count=int(getattr(comment, "like_count", 0) or 0),
            replies_count=int(getattr(comment, "child_comment_count", 0) or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
