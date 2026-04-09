"""Comment data model for Instagram post comments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ig_scraper.logging_utils import format_kv, get_logger


logger = get_logger("models")


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
        logger.debug(
            "Built comment | %s",
            format_kv(
                raw_pk=getattr(comment, "pk", "MISSING"),
                has_user=bool(user),
                raw_text_len=len(getattr(comment, "text", "") or ""),
                raw_created_at=str(getattr(comment, "created_at_utc", "MISSING")),
                raw_like_count=getattr(comment, "like_count", "MISSING"),
                raw_child_count=getattr(comment, "child_comment_count", "MISSING"),
            ),
        )
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

    @classmethod
    def from_instaloader_comment(cls, comment: Any, media_url: str) -> Comment:
        """Create Comment from instaloader Comment object."""
        user = getattr(comment, "owner", None)
        logger.debug(
            "Built comment | %s",
            format_kv(
                raw_pk=getattr(comment, "id", "MISSING"),
                has_owner=bool(user),
                raw_text_len=len(getattr(comment, "text", "") or ""),
                raw_created_at_utc=str(getattr(comment, "created_at_utc", "MISSING")),
                raw_likes_count=getattr(comment, "likes_count", "MISSING"),
            ),
        )
        return cls(
            post_url=media_url,
            comment_url=f"{media_url}#comment-{getattr(comment, 'id', '')}",
            id=str(getattr(comment, "id", "")),
            text=getattr(comment, "text", "") or "",
            owner_username=getattr(user, "username", "") if user else "",
            owner_full_name=getattr(user, "full_name", "") if user else "",
            owner_profile_pic_url=str(getattr(user, "profile_pic_url", "")) if user else "",
            timestamp=str(getattr(comment, "created_at_utc", "")),
            likes_count=int(getattr(comment, "likes_count", 0) or 0),
            replies_count=int(getattr(comment, "answers_count", 0) or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
