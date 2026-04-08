"""Tests for analysis.py pure functions."""

from __future__ import annotations

import pytest

from ig_scraper.analysis import (
    clean_handle,
    extract_hashtags,
    extract_hook,
    extract_mentions,
    get_caption,
    get_comment_count,
    get_like_count,
    get_post_url,
    get_shortcode,
    sanitize_path_segment,
    top_words,
)


class TestCleanHandle:
    """Tests for clean_handle function."""

    def test_basic_handle(self):
        """Test basic handle cleaning."""
        assert clean_handle("@testuser") == "testuser"

    def test_handle_with_whitespace(self):
        """Test handle with leading/trailing whitespace."""
        assert clean_handle("  @testuser  ") == "testuser"

    def test_handle_without_at(self):
        """Test handle without @ symbol."""
        assert clean_handle("testuser") == "testuser"

    def test_handle_multiple_ats(self):
        """Test handle with multiple @ symbols."""
        assert clean_handle("@@testuser") == "testuser"

    def test_empty_handle_raises_validation_error(self):
        """Test empty handle raises ValueError per validation contract."""
        with pytest.raises(ValueError, match="Instagram handles must be"):
            clean_handle("")


class TestExtractHashtags:
    """Tests for extract_hashtags function."""

    def test_single_hashtag(self):
        """Test extracting single hashtag."""
        assert extract_hashtags("Love #photography") == ["#photography"]

    def test_multiple_hashtags(self):
        """Test extracting multiple hashtags."""
        text = "#art #photography #travel"
        result = extract_hashtags(text)
        assert result == ["#art", "#photography", "#travel"]

    def test_hashtag_with_numbers(self):
        """Test hashtag with numbers."""
        assert extract_hashtags("#python3 #ai2024") == ["#python3", "#ai2024"]

    def test_no_hashtags(self):
        """Test text with no hashtags."""
        assert extract_hashtags("Just plain text") == []

    def test_hashtag_at_start(self):
        """Test hashtag at start of text."""
        assert extract_hashtags("#start of text") == ["#start"]


class TestExtractMentions:
    """Tests for extract_mentions function."""

    def test_single_mention(self):
        """Test extracting single mention."""
        assert extract_mentions("Hey @user") == ["@user"]

    def test_multiple_mentions(self):
        """Test extracting multiple mentions."""
        text = "Thanks @alice and @bob.smith"
        result = extract_mentions(text)
        assert "@alice" in result
        assert "@bob.smith" in result

    def test_no_mentions(self):
        """Test text with no mentions."""
        assert extract_mentions("Just plain text") == []

    def test_mention_with_dot(self):
        """Test mention with dot in username."""
        assert extract_mentions("@user.name") == ["@user.name"]


class TestExtractHook:
    """Tests for extract_hook function."""

    def test_short_hook(self):
        """Test hook under 140 chars."""
        text = "Short hook here"
        assert extract_hook(text) == "Short hook here"

    def test_long_hook_truncated(self):
        """Test hook over 140 chars truncated."""
        text = "A" * 200
        result = extract_hook(text)
        assert len(result) <= 140

    def test_hook_first_sentence(self):
        """Test extracting first sentence as hook."""
        text = "First sentence. Second sentence here."
        assert extract_hook(text) == "First sentence."

    def test_empty_hook(self):
        """Test empty text returns empty hook."""
        assert extract_hook("") == ""

    def test_hook_with_newlines(self):
        """Test hook with newlines takes first line."""
        text = "First line\nSecond line"
        assert extract_hook(text) == "First line"


class TestTopWords:
    """Tests for top_words function."""

    def test_basic_word_frequency(self, sample_texts):
        """Test basic word frequency counting."""
        result = top_words(sample_texts, limit=3)
        assert "python" in result
        assert "data" in result or "science" in result

    def test_excludes_common_words(self):
        """Test that common hook words are excluded."""
        texts = ["how to do this", "why you want that"]
        result = top_words(texts, limit=10)
        # HOOK_WORDS includes "how", "why", "you", etc.
        assert "how" not in result
        assert "why" not in result

    def test_excludes_short_words(self):
        """Test that words under 3 chars are excluded."""
        texts = ["a b c hello"]
        result = top_words(texts, limit=10)
        assert "a" not in result
        assert "b" not in result
        assert "hello" in result

    def test_respects_limit(self, sample_texts):
        """Test that limit parameter is respected."""
        result = top_words(sample_texts, limit=2)
        assert len(result) <= 2


class TestSanitizePathSegment:
    """Tests for sanitize_path_segment function."""

    def test_basic_sanitization(self):
        """Test basic path sanitization."""
        assert sanitize_path_segment("test name") == "test-name"

    def test_removes_special_chars(self):
        """Test removal of special characters."""
        assert sanitize_path_segment("test@name#here") == "test-name-here"

    def test_truncates_long_names(self):
        """Test truncation of long names."""
        long_name = "a" * 150
        result = sanitize_path_segment(long_name)
        assert len(result) <= 120

    def test_uses_fallback(self):
        """Test fallback for empty result."""
        assert sanitize_path_segment("@#$%") == "item"

    def test_custom_fallback(self):
        """Test custom fallback value."""
        assert sanitize_path_segment("@#$%", fallback="custom") == "custom"


class TestGetCaption:
    """Tests for get_caption function."""

    def test_get_caption_from_caption_key(self):
        """Test getting caption from 'caption' key."""
        post = {"caption": "Test caption"}
        assert get_caption(post) == "Test caption"

    def test_get_caption_from_text_key(self):
        """Test getting caption from 'text' key."""
        post = {"text": "Test text"}
        assert get_caption(post) == "Test text"

    def test_get_caption_empty(self):
        """Test empty caption handling."""
        post = {}
        assert get_caption(post) == ""

    def test_get_caption_list(self):
        """Test caption as list joined with newlines."""
        post = {"caption": ["Line 1", "Line 2"]}
        assert get_caption(post) == "Line 1\nLine 2"


class TestGetPostUrl:
    """Tests for get_post_url function."""

    def test_get_url_from_url_key(self):
        """Test getting URL from 'url' key."""
        post = {"url": "https://instagram.com/p/ABC123"}
        assert get_post_url(post) == "https://instagram.com/p/ABC123"

    def test_get_url_from_post_url_key(self):
        """Test getting URL from 'postUrl' key."""
        post = {"post_url": "https://instagram.com/p/DEF456"}
        assert get_post_url(post) == "https://instagram.com/p/DEF456"

    def test_get_url_empty(self):
        """Test empty URL handling."""
        post = {}
        assert get_post_url(post) == ""


class TestGetShortcode:
    """Tests for get_shortcode function."""

    def test_get_shortcode_from_short_code_key(self):
        """Test getting shortcode from 'shortCode' key."""
        post = {"short_code": "ABC123"}
        assert get_shortcode(post) == "ABC123"

    def test_get_shortcode_from_code_key(self):
        """Test getting shortcode from 'code' key."""
        post = {"code": "DEF456"}
        assert get_shortcode(post) == "DEF456"

    def test_get_shortcode_empty(self):
        """Test empty shortcode handling."""
        post = {}
        assert get_shortcode(post) == ""


class TestGetCommentCount:
    """Tests for get_comment_count function."""

    def test_get_count_from_comments_count_key(self):
        """Test getting count from 'commentsCount' key."""
        post = {"comments_count": 42}
        assert get_comment_count(post) == 42

    def test_get_count_from_comments_count(self):
        """Test getting count from 'comments_count' key."""
        post = {"comments_count": 100}
        assert get_comment_count(post) == 100

    def test_get_count_invalid_value(self):
        """Test handling of invalid comment count."""
        post = {"comment_count": "invalid"}
        assert get_comment_count(post) == 0

    def test_get_count_missing(self):
        """Test missing comment count returns 0."""
        post = {}
        assert get_comment_count(post) == 0


class TestGetLikeCount:
    """Tests for get_like_count function."""

    def test_get_count_from_likes_count_key(self):
        """Test getting count from 'likesCount' key."""
        post = {"likes_count": 42}
        assert get_like_count(post) == 42

    def test_get_count_from_likes_count(self):
        """Test getting count from 'likes_count' key."""
        post = {"likes_count": 100}
        assert get_like_count(post) == 100

    def test_get_count_invalid_value(self):
        """Test handling of invalid like count."""
        post = {"like_count": "invalid"}
        assert get_like_count(post) == 0

    def test_get_count_missing(self):
        """Test missing like count returns 0."""
        post = {}
        assert get_like_count(post) == 0
