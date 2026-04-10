"""Custom exception hierarchy and classification for ig_scraper."""

from __future__ import annotations


INSTALOADER_RETRYABLE = {
    "ConnectionException",
    "TooManyRequestsException",
    "AmbiguousRedirectException",
    "PostChangedException",
}

INSTALOADER_FATAL = {
    "LoginRequiredException",
    "BadCredentialsException",
    "TwoFactorAuthRequiredException",
    "PrivateProfileNotFollowedException",
    "ProfileNotExistsException",
    "QueryReturnedNotFoundException",
    "QueryReturnedForbiddenException",
    "QueryReturnedBadRequestException",
    "InvalidArgumentException",
    "BadResponseException",
}

INSTALOADER_AUTHORIZATION_FAILURES = {
    "PrivateProfileNotFollowedException",
    "QueryReturnedForbiddenException",
}

INSTALOADER_AUTHORIZATION_MESSAGES = (
    "not authorized to view user",
    "private profile",
)


class IgScraperError(Exception):
    """Base exception for all ig_scraper errors."""


class AuthError(IgScraperError):
    """Raised when Instagram authentication fails."""


class MediaDownloadError(IgScraperError):
    """Raised when media download fails."""


class RetryExhaustedError(IgScraperError):
    """Raised internally when all retry attempts are spent and caller should handle exhaustion."""


# Exception Classification
def classify_exception(exc: BaseException) -> bool:
    """Classify if an exception is retryable.

    Args:
        exc: The exception to classify.

    Returns:
        True if the exception is retryable (transient), False if fatal.

    Retryable exceptions (transient failures):
    - RuntimeError: General API errors, rate limiting
    - ConnectionError: Network issues
    - TimeoutError: Request timeouts

    Fatal exceptions (should not retry):
    - LoginRequired: Authentication failure
    - AuthError: Authentication failure
    - ValueError: Invalid input (won't change on retry)
    """
    # Retryable exceptions (transient failures)
    if isinstance(exc, (OSError, RuntimeError, ConnectionError, TimeoutError)):
        return True

    # Fatal: IgScraperError base class and all subclasses (includes AuthError)
    if isinstance(exc, IgScraperError):
        return False

    exc_name = type(exc).__name__
    if exc_name in INSTALOADER_RETRYABLE:
        return True
    if exc_name in INSTALOADER_FATAL:
        return False

    # Fatal: legacy authentication errors that may only be available by name.
    if exc_name in ("LoginRequired", "ChallengeRequired"):
        return False

    # Default to fatal for unknown exception types.
    return False


def is_instaloader_authorization_failure(exc: BaseException) -> bool:
    """Return whether *exc* represents an authorization/visibility failure.

    This is used to distinguish private or otherwise inaccessible profiles from
    transient transport issues so callers can skip the affected handle.
    """
    exc_name = type(exc).__name__
    if exc_name in INSTALOADER_AUTHORIZATION_FAILURES:
        return True
    if exc_name != "QueryReturnedBadRequestException":
        return False
    return any(message in str(exc).lower() for message in INSTALOADER_AUTHORIZATION_MESSAGES)
