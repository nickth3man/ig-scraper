"""Tests for exception classification behavior."""

from __future__ import annotations

from ig_scraper.exceptions import (
    AuthError,
    classify_exception,
    is_instaloader_authorization_failure,
)


def _named_exception(name: str) -> type[Exception]:
    """Create an exception type with an exact runtime name for classification tests."""
    return type(name, (Exception,), {})


CONNECTION_EXCEPTION = _named_exception("ConnectionException")
TOO_MANY_REQUESTS_EXCEPTION = _named_exception("TooManyRequestsException")
QUERY_RETURNED_FORBIDDEN_EXCEPTION = _named_exception("QueryReturnedForbiddenException")
QUERY_RETURNED_BAD_REQUEST_EXCEPTION = _named_exception("QueryReturnedBadRequestException")
PRIVATE_PROFILE_NOT_FOLLOWED_EXCEPTION = _named_exception("PrivateProfileNotFollowedException")
LOGIN_REQUIRED = _named_exception("LoginRequired")
CHALLENGE_REQUIRED = _named_exception("ChallengeRequired")
SOME_UNKNOWN_EXCEPTION = _named_exception("SomeUnknownException")


def test_classify_exception_retries_builtin_transient_errors() -> None:
    """Runtime/network/timeouts should be classified as retryable."""
    assert classify_exception(RuntimeError("boom")) is True
    assert classify_exception(ConnectionError("down")) is True
    assert classify_exception(TimeoutError("slow")) is True


def test_classify_exception_marks_igscraper_errors_fatal() -> None:
    """Internal scraper-domain errors should not be retried."""
    assert classify_exception(AuthError("bad auth")) is False


def test_classify_exception_matches_instaloader_retryable_names() -> None:
    """Known Instaloader transient exception names should retry."""
    assert classify_exception(CONNECTION_EXCEPTION("transient")) is True
    assert classify_exception(TOO_MANY_REQUESTS_EXCEPTION("429")) is True


def test_classify_exception_matches_instaloader_fatal_names() -> None:
    """Known Instaloader fatal exception names should not retry."""
    assert classify_exception(QUERY_RETURNED_FORBIDDEN_EXCEPTION("403")) is False
    assert (
        classify_exception(QUERY_RETURNED_BAD_REQUEST_EXCEPTION("not authorized to view user"))
        is False
    )
    assert classify_exception(ValueError("bad input")) is False


def test_classify_exception_marks_legacy_auth_names_fatal() -> None:
    """Legacy auth exception names should remain fatal."""
    assert classify_exception(LOGIN_REQUIRED("login")) is False
    assert classify_exception(CHALLENGE_REQUIRED("challenge")) is False


def test_classify_exception_defaults_unknown_names_to_fatal() -> None:
    """Unknown exception names should default to non-retryable."""
    assert classify_exception(SOME_UNKNOWN_EXCEPTION("unknown")) is False


def test_is_instaloader_authorization_failure_matches_authorized_messages() -> None:
    """Authorization helper should recognize access-denied Instaloader failures."""
    assert (
        is_instaloader_authorization_failure(
            QUERY_RETURNED_BAD_REQUEST_EXCEPTION("Not authorized to view user")
        )
        is True
    )
    assert (
        is_instaloader_authorization_failure(PRIVATE_PROFILE_NOT_FOLLOWED_EXCEPTION("private"))
        is True
    )


def test_is_instaloader_authorization_failure_ignores_other_bad_requests() -> None:
    """Generic 400s should not be treated as authorization failures."""
    assert (
        is_instaloader_authorization_failure(
            QUERY_RETURNED_BAD_REQUEST_EXCEPTION("feedback_required")
        )
        is False
    )
