"""Pure conversion functions for building dictionaries from instagrapi objects."""

from pathlib import Path
from typing import Any

from ig_scraper.ig_config import COMMENT_PAGE_RETRIES
from ig_scraper.logging_utils import format_kv, get_logger
from ig_scraper.models import Post, Profile


logger = get_logger("instagrapi")


def _build_profile_dict(user: Any) -> dict[str, Any]:
    """Convert an instagrapi User object to a profile dictionary.

    Args:
        user: An instagrapi User object with pk, username, full_name, etc.

    Returns:
        A dictionary with snake_case keys matching the model output.
    """
    return Profile.from_instagrapi_user(user).to_dict()


def _build_post_dict(
    media: Any,
    username: str,
    user_full_name: str,
    user_pk: str,
    media_url: str,
    media_files: list[str],
    post_folder: Path | None,
    account_dir: Path | None,
) -> dict[str, Any]:
    """Convert an instagrapi Media object to a post dictionary.

    Args:
        media: An instagrapi Media object.
        username: The Instagram username of the account owner.
        user_full_name: The full name of the account owner.
        user_pk: The primary key of the account owner.
        media_url: The permalink URL for this media.
        media_files: List of downloaded media file paths.
        post_folder: Path to the post folder, if any.
        account_dir: Path to the account directory, if any.

    Returns:
        A dictionary with snake_case keys matching the model output.
    """
    post = Post.from_instagrapi_media(media, username, user_full_name, user_pk)
    d = post.to_dict()
    # Overlay runtime-only fields not in the model's to_dict()
    d["media_files"] = media_files
    d["post_folder"] = (
        str(post_folder.relative_to(account_dir)) if post_folder and account_dir else ""
    )
    d["from_url"] = f"https://www.instagram.com/{username}/"
    return d


def _log_profile_fetch_attempt(
    username: str, attempt: int, exc: Exception, wait_seconds: float
) -> None:
    """Log a failed profile fetch attempt."""
    logger.warning(
        "Profile fetch failed | %s",
        format_kv(
            username=username,
            attempt=f"{attempt}/{COMMENT_PAGE_RETRIES}",
            error=exc,
            retry_wait_seconds=wait_seconds,
        ),
    )


def _log_medias_fetch_attempt(
    username: str, attempt: int, exc: Exception, wait_seconds: float
) -> None:
    """Log a failed medias fetch attempt."""
    logger.warning(
        "Medias fetch failed | %s",
        format_kv(
            username=username,
            attempt=f"{attempt}/{COMMENT_PAGE_RETRIES}",
            error=exc,
            retry_wait_seconds=wait_seconds,
        ),
    )
