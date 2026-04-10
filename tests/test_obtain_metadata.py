"""Smoke test for patched post metadata access."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from instaloader import Profile

from ig_scraper.client import get_instaloader_client


@pytest.mark.integration
def test_obtain_metadata() -> None:
    """Ensure patched metadata access works for a post fetched via the v1 profile flow."""
    cookies_path = Path("cookies.txt")
    sessionid = os.getenv("INSTAGRAM_SESSIONID")
    target_username = os.getenv("INSTAGRAM_TEST_POSTS_USERNAME", "another_account")

    if not (cookies_path.exists() and sessionid):
        pytest.skip("cookies.txt and INSTAGRAM_SESSIONID are required for integration auth")

    try:
        loader = get_instaloader_client()
    except Exception as exc:  # pragma: no cover - best-effort environment bootstrap
        pytest.skip(f"Authenticated client setup failed: {exc}")

    try:
        profile = Profile.from_username(loader.context, target_username)
        post: Any = next(profile.get_posts())
    except StopIteration:  # pragma: no cover - external platform data availability
        pytest.skip(f"No posts available for integration account: {target_username}")
    except Exception as exc:  # pragma: no cover - external platform behavior
        pytest.skip(f"Failed to fetch test post from {target_username}: {exc}")

    assert post.owner_username == target_username
    assert post.shortcode
    assert isinstance(post.comments, int)
    assert isinstance(post._full_metadata, dict)
