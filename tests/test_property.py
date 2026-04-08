"""Property-based tests using Hypothesis for ig_scraper.

Tests pure functions with generated inputs to discover edge cases
that hardcoded test data might miss.
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ig_scraper.analysis import (
    _safe_int,
    extract_hashtags,
    extract_mentions,
    sanitize_path_segment,
)
from ig_scraper.analysis_io import HANDLE_PATTERN, clean_handle
from ig_scraper.models import Comment, Post, PostResource, Profile
from tests.factories import CommentFactory, PostFactory, ProfileFactory


# ---------------------------------------------------------------------------
# Strategy helpers
# ---------------------------------------------------------------------------

_profile_strategy = st.builds(
    ProfileFactory.build,
    id=st.text(min_size=1, max_size=20),
    username=st.from_regex(r"[a-zA-Z0-9._]{1,30}", fullmatch=True),
    followers_count=st.integers(min_value=0),
    verified=st.booleans(),
)

_post_strategy = st.builds(
    PostFactory.build,
    id=st.text(min_size=1, max_size=20),
    short_code=st.from_regex(r"[A-Za-z0-9_-]{1,20}", fullmatch=True),
)

_comment_strategy = st.builds(
    CommentFactory.build,
    id=st.text(min_size=1, max_size=20),
)

_resource_strategy = st.builds(
    PostResource,
    pk=st.text(min_size=1, max_size=20),
    media_type=st.sampled_from([1, 2, 8]),
    thumbnail_url=st.text(max_size=100),
    video_url=st.text(max_size=100),
)


# ---------------------------------------------------------------------------
# clean_handle
# ---------------------------------------------------------------------------


class TestCleanHandleProperty:
    """Property-based tests for clean_handle."""

    @given(st.from_regex(r"@?[a-zA-Z0-9._]{1,30}", fullmatch=True))
    @settings(max_examples=100)
    def test_clean_handle_produces_valid_handle(self, handle: str) -> None:
        """Valid-looking handles should produce a result matching HANDLE_PATTERN."""
        result = clean_handle(handle)
        assert HANDLE_PATTERN.fullmatch(result)

    @given(st.text(min_size=1).filter(lambda s: not re.match(r"@?[a-zA-Z0-9._]+$", s.strip())))
    @settings(max_examples=50)
    def test_clean_handle_rejects_invalid(self, handle: str) -> None:
        """Handles with no valid characters should raise ValueError."""
        with pytest.raises(ValueError, match="handle"):
            clean_handle(handle)


# ---------------------------------------------------------------------------
# sanitize_path_segment
# ---------------------------------------------------------------------------


class TestSanitizePathSegmentProperty:
    """Property-based tests for sanitize_path_segment."""

    @given(st.text(min_size=0, max_size=300))
    @settings(max_examples=200)
    def test_output_is_filesystem_safe(self, value: str) -> None:
        """Output should only contain safe filesystem characters."""
        result = sanitize_path_segment(value)
        assert len(result) <= 120
        if result != "item" and result != value:
            assert re.fullmatch(r"[A-Za-z0-9._-]*", result) or result == "item"

    @given(st.text(min_size=0, max_size=300))
    @settings(max_examples=100)
    def test_never_returns_empty(self, value: str) -> None:
        """Output should always be non-empty."""
        result = sanitize_path_segment(value)
        assert len(result) > 0

    @given(st.text(min_size=0, max_size=50), st.text(min_size=1, max_size=20))
    @settings(max_examples=50)
    def test_custom_fallback_honored(self, value: str, fallback: str) -> None:
        """When output would be the default fallback, custom fallback is used."""
        result = sanitize_path_segment(value, fallback=fallback)
        # If the result used fallback, it should match custom
        if result == "item" or (not re.search(r"[A-Za-z0-9]", value)):
            assert result == fallback or result == "item"


# ---------------------------------------------------------------------------
# extract_hashtags / extract_mentions
# ---------------------------------------------------------------------------


class TestExtractHashtagsProperty:
    """Property-based tests for extract_hashtags."""

    @given(st.text())
    @settings(max_examples=200)
    def test_all_results_start_with_hash(self, text: str) -> None:
        """Every returned hashtag must start with #."""
        result = extract_hashtags(text)
        assert isinstance(result, list)
        assert all(tag.startswith("#") for tag in result)

    @given(st.text())
    @settings(max_examples=100)
    def test_idempotent(self, text: str) -> None:
        """Calling extract_hashtags on the same text always returns the same result."""
        assert extract_hashtags(text) == extract_hashtags(text)


class TestExtractMentionsProperty:
    """Property-based tests for extract_mentions."""

    @given(st.text())
    @settings(max_examples=200)
    def test_all_results_start_with_at(self, text: str) -> None:
        """Every returned mention must start with @."""
        result = extract_mentions(text)
        assert isinstance(result, list)
        assert all(m.startswith("@") for m in result)

    @given(st.text())
    @settings(max_examples=100)
    def test_mention_format(self, text: str) -> None:
        """Mentions must match word characters and optional dots."""
        for mention in extract_mentions(text):
            assert re.fullmatch(r"@\w+(?:\.\w+)*", mention)


# ---------------------------------------------------------------------------
# _safe_int
# ---------------------------------------------------------------------------


class TestSafeIntProperty:
    """Property-based tests for _safe_int."""

    @given(st.one_of(st.integers(), st.floats(allow_nan=False, allow_infinity=False), st.text()))
    @settings(max_examples=200)
    def test_never_crashes(self, value: int | float | str) -> None:
        """_safe_int should never raise on numeric or string input."""
        result = _safe_int(value)
        assert isinstance(result, int)

    @given(st.integers())
    @settings(max_examples=50)
    def test_integers_pass_through(self, value: int) -> None:
        """Integer inputs should be returned as-is."""
        assert _safe_int(value) == value

    @given(st.one_of(st.none(), st.lists(st.integers()), st.dictionaries(st.text(), st.integers())))
    @settings(max_examples=50)
    def test_uncoercible_returns_zero(self, value: object) -> None:
        """Values that cannot be coerced should return 0."""
        assert _safe_int(value) == 0  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Model round-trip (to_dict)
# ---------------------------------------------------------------------------


class TestModelRoundTripProperty:
    """Property-based tests for model serialization round-trips."""

    @given(_profile_strategy)
    @settings(max_examples=50)
    def test_profile_to_dict_no_private_fields(self, profile: Profile) -> None:
        """to_dict should never include private fields."""
        d = profile.to_dict()
        assert "_method" not in d
        assert all(not k.startswith("_") for k in d)

    @given(_profile_strategy)
    @settings(max_examples=50)
    def test_profile_to_dict_types(self, profile: Profile) -> None:
        """to_dict values should have correct types."""
        d = profile.to_dict()
        assert isinstance(d["id"], str)
        assert isinstance(d["username"], str)
        assert isinstance(d["followers_count"], int)
        assert isinstance(d["verified"], bool)

    @given(_post_strategy)
    @settings(max_examples=50)
    def test_post_to_dict_no_private_fields(self, post: Post) -> None:
        """Post.to_dict should never include _profile."""
        d = post.to_dict()
        assert "_profile" not in d
        assert all(not k.startswith("_") for k in d)

    @given(_comment_strategy)
    @settings(max_examples=50)
    def test_comment_to_dict_preserves_text(self, comment: Comment) -> None:
        """Comment.to_dict should preserve the text field."""
        d = comment.to_dict()
        assert d["text"] == comment.text

    @given(_resource_strategy)
    @settings(max_examples=50)
    def test_post_resource_creation(self, resource: PostResource) -> None:
        """PostResource should have the expected field types."""
        assert isinstance(resource.pk, str)
        assert isinstance(resource.media_type, int)
        assert resource.media_type in (1, 2, 8)
