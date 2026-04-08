"""Exception classification and retry-specific exceptions."""

from __future__ import annotations


class RetryExhaustedError(Exception):
    """Raised internally when all retry attempts are spent and caller should handle exhaustion."""


# Exception Classification
def classify_exception(exc: Exception) -> bool:
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
    retryable_types = (RuntimeError, ConnectionError, TimeoutError)
    fatal_types = (
        "LoginRequired",
        "ChallengeRequired",
        "AuthError",
        "IgScraperError",
    )

    # Check if exception type matches retryable types
    if isinstance(exc, retryable_types):
        return True

    # Check exception class name for specific fatal exceptions
    exc_type_name = type(exc).__name__
    return exc_type_name not in fatal_types
