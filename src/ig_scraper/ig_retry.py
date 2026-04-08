"""Retry logic with exponential backoff for Instagram API calls.

This module provides two APIs for retrying operations:
1. Function-based: _retry_with_backoff() - backward compatible, uses functools.partial
2. Decorator-based: @retry_on() - modern pattern, cleaner for new code

Exception Classification:
- RETRYABLE: Transient failures that might succeed on retry
- FATAL: Permanent failures that won't succeed on retry
"""

from __future__ import annotations

import functools
import time
from typing import TYPE_CHECKING, Any, TypeVar

from ig_scraper.ig_config import REQUEST_PAUSE_SECONDS
from ig_scraper.logging_utils import get_logger


if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger("instagrapi")

T = TypeVar("T")


class _RetryExhaustedError(Exception):
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


def _retry_with_backoff[T](
    fn: Callable[[], T],
    *,
    retries: int,
    exceptions: tuple[type[Exception], ...],
    log_attempt: Callable[[int, Exception, float], None],
) -> T:
    """Execute a callable with exponential backoff retries on specified exceptions.

    Retries the function up to *retries* times, sleeping for exponentially increasing
    intervals between attempts. Logs each failure via the log_attempt callback.

    DEPRECATED: Use @retry_on() decorator for new code.

    Args:
        fn: Callable to execute and retry.
        retries: Maximum number of attempts (including the first).
        exceptions: Tuple of exception types that trigger a retry.
        log_attempt: Callback(current_attempt, exception, wait_seconds) for logging.

    Returns:
        The return value of *fn* on successful execution.

    Raises:
        _RetryExhaustedError: When all retry attempts are exhausted with the last exception.
    """
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except exceptions as exc:
            last_exc = exc
            wait_seconds = round(REQUEST_PAUSE_SECONDS * (2**attempt), 2)
            log_attempt(attempt, exc, wait_seconds)
            if attempt < retries:
                time.sleep(wait_seconds)
    if last_exc is None:
        raise RuntimeError("Unexpected: last_exc is None after retries exhausted")
    raise _RetryExhaustedError(str(last_exc)) from last_exc


def retry_on(
    *exception_types: type[Exception],
    max_attempts: int = 3,
    wait_base_seconds: float | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to retry a function on specified exception types.

    Uses exponential backoff: wait_seconds = REQUEST_PAUSE_SECONDS * (2 ** attempt)

    Args:
        *exception_types: Exception types to catch and retry on.
        max_attempts: Maximum number of attempts (default: 3).
        wait_base_seconds: Override base wait time (default: REQUEST_PAUSE_SECONDS).

    Returns:
        Decorator function.

    Example:
        @retry_on(RuntimeError, ConnectionError, max_attempts=3)
        def fetch_profile(username: str) -> dict:
            # This will be retried up to 3 times on RuntimeError or ConnectionError
            ...
    """
    if not exception_types:
        raise ValueError("Must specify at least one exception type to retry on")

    base_wait = wait_base_seconds if wait_base_seconds is not None else REQUEST_PAUSE_SECONDS

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        fn_name = getattr(fn, "__name__", repr(fn))

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exc: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exception_types as exc:
                    last_exc = exc
                    wait_seconds = round(base_wait * (2**attempt), 2)
                    logger.warning(
                        "Function %s failed (attempt %d/%d) | error=%s | retry_wait_seconds=%s",
                        fn_name,
                        attempt,
                        max_attempts,
                        exc,
                        wait_seconds,
                    )
                    if attempt < max_attempts:
                        time.sleep(wait_seconds)
            if last_exc is None:
                raise RuntimeError(f"Unexpected: {fn_name} exhausted retries but no exception")
            raise _RetryExhaustedError(
                f"{fn_name} failed after {max_attempts} attempts: {last_exc}"
            ) from last_exc

        return wrapper

    return decorator
