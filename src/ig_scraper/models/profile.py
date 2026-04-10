"""Profile data model for Instagram user data."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ig_scraper.logging_utils import format_kv, get_logger


logger = get_logger("models")


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
    is_private: bool = False
    igtv_count: int = 0
    biography_hashtags: list[str] = field(default_factory=list)
    biography_mentions: list[str] = field(default_factory=list)
    business_category_name: str = ""
    _method: str = field(default="instaloader", repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {k: v for k, v in asdict(self).items() if not k.startswith("_")}

    @classmethod
    def from_instaloader_profile(cls, profile: Any, method: str = "instaloader") -> Profile:
        """Create Profile from instaloader Profile object."""
        logger.debug(
            "Built profile | %s",
            format_kv(
                raw_userid=getattr(profile, "userid", "MISSING"),
                raw_username=getattr(profile, "username", "MISSING"),
                raw_follower_count_type=type(getattr(profile, "followers", 0)).__name__,
                raw_is_verified=getattr(profile, "is_verified", "MISSING"),
            ),
        )
        return cls(
            id=str(getattr(profile, "userid", "")),
            username=getattr(profile, "username", ""),
            full_name=getattr(profile, "full_name", ""),
            biography=getattr(profile, "biography", ""),
            followers_count=getattr(profile, "followers", 0),
            follows_count=getattr(profile, "followees", 0),
            posts_count=getattr(profile, "mediacount", 0),
            verified=getattr(profile, "is_verified", False),
            is_business_account=getattr(profile, "is_business_account", False),
            profile_pic_url=str(getattr(profile, "profile_pic_url", "") or ""),
            external_url=str(getattr(profile, "external_url", "") or ""),
            is_private=getattr(profile, "is_private", False),
            igtv_count=getattr(profile, "igtvcount", 0) or 0,
            biography_hashtags=[str(h) for h in getattr(profile, "biography_hashtags", [])],
            biography_mentions=[str(m) for m in getattr(profile, "biography_mentions", [])],
            business_category_name=str(getattr(profile, "business_category_name", "") or ""),
            _method=method,
        )
