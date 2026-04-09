"""Custom exception hierarchy and classification for ig_scraper."""

from __future__ import annotations


INSTALOADER_RETRYABLE = {
    "ConnectionException",
    "TooManyRequestsException",
    "QueryReturnedNotFoundException",
    "AmbiguousRedirectException",
}

INSTALOADER_FATAL = {
    "LoginRequiredException",
    "BadCredentialsException",
    "TwoFactorAuthRequiredException",
    "PrivateProfileNotFollowedException",
    "ProfileNotExistsException",
}


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
    if isinstance(exc, (RuntimeError, ConnectionError, TimeoutError)):
        return True

    # Fatal: IgScraperError base class and all subclasses (includes AuthError)
    if isinstance(exc, IgScraperError):
        return False

    exc_name = type(exc).__name__
    if exc_name in INSTALOADER_RETRYABLE:
        return True
    if exc_name in INSTALOADER_FATAL:
        return False

    # Fatal: instagrapi authentication errors (not importable, check by name)
    return exc_name not in ("LoginRequired", "ChallengeRequired")
