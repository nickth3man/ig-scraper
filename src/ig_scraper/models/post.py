"""Post and PostResource data models for Instagram media."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from ig_scraper.logging_utils import format_kv, get_logger


logger = get_logger("models")


def _safe_attr(obj: Any, name: str, default: Any = None) -> Any:
    """Get attribute from instaloader object, catching KeyError from _field().

    Many instaloader Post properties (location, tagged_users, video_url, etc.)
    use _field() internally which raises KeyError when metadata is unavailable.
    Standard getattr() only catches AttributeError, not KeyError.
    """
    try:
        return getattr(obj, name, default)
    except (KeyError, TypeError):
        return default


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
    view_count: int = 0
    location: str = ""
    tagged_users: list[str] = field(default_factory=list)
    sponsor_users: list[str] = field(default_factory=list)
    video_play_count: int = 0
    video_view_count: int = 0
    is_sponsored: bool = False
    _profile: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_instaloader_post(
        cls, post: Any, username: str, user_full_name: str, user_id: str
    ) -> Post:
        """Create Post from instaloader Post object."""
        logger.debug(
            "Built post | %s",
            format_kv(
                raw_pk=getattr(post, "mediaid", "MISSING"),
                raw_shortcode=getattr(post, "shortcode", "MISSING"),
                raw_media_type=type(getattr(post, "media_type", 0)).__name__,
                rawtypename=getattr(post, "typename", "MISSING"),
                raw_caption_len=len(getattr(post, "caption", "") or ""),
                raw_date_utc=str(getattr(post, "date_utc", "MISSING")),
            ),
        )
        url = f"https://www.instagram.com/p/{post.shortcode}/"
        resources = [
            PostResource(
                pk=str(_safe_attr(r, "pk", "")),
                media_type=int(_safe_attr(r, "media_type", 0)),
                thumbnail_url=str(_safe_attr(r, "thumbnail_url", "")),
                video_url=str(_safe_attr(r, "video_url", "")),
            )
            for r in _safe_attr(post, "resources", [])
        ]
        hashtags = [str(h) for h in _safe_attr(post, "caption_hashtags", [])]
        mentions = [str(m) for m in _safe_attr(post, "caption_mentions", [])]
        tagged_users = [str(u) for u in _safe_attr(post, "tagged_users", [])]
        sponsor_users = [str(u) for u in _safe_attr(post, "sponsor_users", [])]
        try:
            location = _safe_attr(post, "location")
            location_str = f"{location.lat},{location.lng},{location.name}" if location else ""
        except (KeyError, TypeError):
            location_str = ""
        return cls(
            id=str(getattr(post, "mediaid", "")),
            pk=str(getattr(post, "mediaid", "")),
            short_code=post.shortcode,
            url=url,
            type=str(getattr(post, "typename", "") or getattr(post, "media_type", "")) or "",
            caption=getattr(post, "caption", "") or "",
            comment_count=_safe_attr(post, "comments", 0) or 0,
            like_count=_safe_attr(post, "likes", 0) or 0,
            taken_at=getattr(post, "date_utc", None),
            owner_username=username,
            owner_full_name=user_full_name,
            owner_id=str(user_id),
            video_url=str(_safe_attr(post, "video_url", "")),
            thumbnail_url=str(getattr(post, "url", "")),
            is_video=getattr(post, "is_video", False),
            resources=resources,
            hashtags=hashtags,
            mentions=mentions,
            view_count=_safe_attr(post, "view_count", 0) or 0,
            location=location_str,
            tagged_users=tagged_users,
            sponsor_users=sponsor_users,
            video_play_count=_safe_attr(post, "video_play_count", 0) or 0,
            video_view_count=_safe_attr(post, "video_view_count", 0) or 0,
            is_sponsored=_safe_attr(post, "is_sponsored", False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d = {k: v for k, v in d.items() if not k.startswith("_")}
        d["taken_at"] = (
            self.taken_at.isoformat()
            if isinstance(self.taken_at, datetime)
            else str(self.taken_at)
            if self.taken_at
            else ""
        )
        return d
