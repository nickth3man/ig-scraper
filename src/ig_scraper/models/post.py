"""Post and PostResource data models for Instagram media."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from ig_scraper.logging_utils import format_kv, get_logger


logger = get_logger("models")


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
    _profile: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_instagrapi_media(
        cls, media: Any, username: str, user_full_name: str, user_pk: str
    ) -> Post:
        """Create Post from instagrapi Media object."""
        logger.debug(
            "Built post | %s",
            format_kv(
                raw_pk=getattr(media, "pk", "MISSING"),
                raw_code=getattr(media, "code", "MISSING"),
                raw_media_type=type(getattr(media, "media_type", 0)).__name__,
                raw_product_type=getattr(media, "product_type", "MISSING"),
                raw_caption_text_len=len(getattr(media, "caption_text", "") or ""),
                raw_taken_at_type=type(getattr(media, "taken_at", None)).__name__,
                resources_count=len(getattr(media, "resources", [])),
                constructed_url=f"https://www.instagram.com/{getattr(media, 'code', '')}/",
            ),
        )
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
            type=str(getattr(media, "product_type", "") or getattr(media, "media_type", "")) or "",
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

    @classmethod
    def from_instaloader_post(
        cls, post: Any, username: str, user_full_name: str, user_id: str
    ) -> Post:
        """Create Post from instaloader Post object."""
        logger.debug(
            "Built post | %s",
            format_kv(
                raw_pk=getattr(post, "pk", "MISSING"),
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
                pk=str(getattr(r, "pk", "")),
                media_type=int(getattr(r, "media_type", 0)),
                thumbnail_url=str(getattr(r, "thumbnail_url", "")),
                video_url=str(getattr(r, "video_url", "")),
            )
            for r in getattr(post, "resources", [])
        ]
        hashtags = [str(h) for h in getattr(post, "caption_hashtags", [])]
        mentions = [str(m) for m in getattr(post, "caption_mentions", [])]
        return cls(
            id=str(getattr(post, "pk", "")),
            pk=str(getattr(post, "pk", "")),
            short_code=post.shortcode,
            url=url,
            type=str(getattr(post, "typename", "") or getattr(post, "media_type", "")) or "",
            caption=getattr(post, "caption", "") or "",
            comment_count=getattr(post, "comments", 0) or 0,
            like_count=getattr(post, "likes", 0) or 0,
            taken_at=getattr(post, "date_utc", None),
            owner_username=username,
            owner_full_name=user_full_name,
            owner_id=str(user_id),
            video_url=str(getattr(post, "video_url", "")),
            thumbnail_url=str(getattr(post, "url", "")),
            is_video=getattr(post, "is_video", False),
            resources=resources,
            hashtags=hashtags,
            mentions=mentions,
            view_count=getattr(post, "view_count", 0) or 0,
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
