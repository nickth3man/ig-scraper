"""BDD step definitions for ig_scraper feature tests."""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ig_scraper.analysis_io import clean_handle
from ig_scraper.analysis_render import build_analysis_markdown


# Load all scenarios from feature files
scenarios("features")


# ---------------------------------------------------------------------------
# Handle validation steps
# ---------------------------------------------------------------------------


class HandleContext:
    """Shared context for handle validation scenarios."""

    def __init__(self) -> None:  # noqa: D107
        self.result: str = ""
        self.exception: Exception | None = None


@pytest.fixture
def handle_ctx() -> HandleContext:
    """Provide handle test context."""
    return HandleContext()


@when(parsers.parse('cleaning handle "{handle_input}"'))
def cleaning_handle(handle_input: str, handle_ctx: HandleContext) -> None:
    """Clean the given handle, capturing any exception."""
    try:
        handle_ctx.result = clean_handle(handle_input)
    except Exception as exc:
        handle_ctx.exception = exc


@when('cleaning handle ""')
def cleaning_empty_handle(handle_ctx: HandleContext) -> None:
    """Attempt to clean an empty handle."""
    try:
        clean_handle("")
    except Exception as exc:
        handle_ctx.exception = exc


@then(parsers.parse('the result is "{expected}"'))
def result_is(expected: str, handle_ctx: HandleContext) -> None:
    """Verify the cleaned handle matches expected."""
    assert handle_ctx.exception is None, f"Unexpected exception: {handle_ctx.exception}"
    assert handle_ctx.result == expected


@then("a ValueError is raised")
def value_error_raised(handle_ctx: HandleContext) -> None:
    """Verify a ValueError was raised."""
    assert isinstance(handle_ctx.exception, ValueError)


# ---------------------------------------------------------------------------
# Analysis pipeline steps
# ---------------------------------------------------------------------------


class AnalysisContext:
    """Shared context for analysis pipeline scenarios."""

    def __init__(self) -> None:  # noqa: D107
        self.posts: list[dict[str, object]] = []
        self.comments: list[dict[str, object]] = []
        self.markdown: str = ""


@pytest.fixture
def analysis_ctx() -> AnalysisContext:
    """Provide analysis test context."""
    return AnalysisContext()


@given("zero posts and zero comments")
def zero_posts_and_comments(analysis_ctx: AnalysisContext) -> None:
    """Set up empty posts and comments."""
    analysis_ctx.posts = []
    analysis_ctx.comments = []


@given("3 posts with captions and 2 comments")
def three_posts_two_comments(analysis_ctx: AnalysisContext) -> None:
    """Set up 3 posts with captions and 2 comments."""
    analysis_ctx.posts = [
        {"caption": "First post #travel", "likes_count": 100, "comments_count": 5},
        {"caption": "Second post #food", "likes_count": 50, "comments_count": 3},
        {"caption": "Third post #fitness", "likes_count": 200, "comments_count": 10},
    ]
    analysis_ctx.comments = [
        {"text": "Great!", "post_url": "https://instagram.com/p/1/"},
        {"text": "Love it!", "post_url": "https://instagram.com/p/2/"},
    ]


@given('a post with caption "Love #python and @friend"')
def post_with_caption(analysis_ctx: AnalysisContext) -> None:
    """Set up a single post with specific caption."""
    analysis_ctx.posts = [
        {"caption": "Love #python and @friend", "likes_count": 10, "comments_count": 1}
    ]
    analysis_ctx.comments = []


@when(parsers.parse('analysis markdown is generated for "{handle}"'))
def generate_analysis(handle: str, analysis_ctx: AnalysisContext) -> None:
    """Generate analysis markdown from context posts and comments."""
    analysis_ctx.markdown = build_analysis_markdown(
        handle.strip("@"),
        analysis_ctx.posts,
        analysis_ctx.comments,
    )


@then(parsers.parse('the markdown contains "{text}"'))
def markdown_contains(text: str, analysis_ctx: AnalysisContext) -> None:
    """Verify markdown contains expected text."""
    assert text in analysis_ctx.markdown
