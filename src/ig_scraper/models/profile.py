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
    _method: str = field(default="instagrapi", repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {k: v for k, v in asdict(self).items() if not k.startswith("_")}

    @classmethod
    def from_instagrapi_user(cls, user: Any, method: str = "instagrapi") -> Profile:
        """Create Profile from instagrapi User object."""
        logger.debug(
            "Built profile | %s",
            format_kv(
                raw_pk=getattr(user, "pk", "MISSING"),
                raw_username=getattr(user, "username", "MISSING"),
                raw_follower_count_type=type(getattr(user, "follower_count", 0)).__name__,
                raw_is_verified=getattr(user, "is_verified", "MISSING"),
                raw_is_business=getattr(user, "is_business", "MISSING"),
            ),
        )
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
            _method=method,
        )
