"""Retry logic with exponential backoff for Instagram API calls.

This module provides two APIs for retrying operations:
1. Function-based: _retry_with_backoff() - backward compatible, uses functools.partial
2. Decorator-based: @retry_on() - modern pattern, cleaner for new code

Exception classification is delegated to ig_scraper.exceptions.classify_exception.
"""

from __future__ import annotations

import functools
import time
from typing import TYPE_CHECKING, Any, TypeVar

from ig_scraper.config import REQUEST_PAUSE_SECONDS
from ig_scraper.exceptions import RetryExhaustedError as _RetryExhaustedError
from ig_scraper.exceptions import classify_exception
from ig_scraper.logging_utils import format_kv, get_logger


if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger("instagrapi")

T = TypeVar("T")


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
    fn_name = getattr(fn, "__name__", repr(fn))
    for attempt in range(1, retries + 1):
        logger.debug("Retry attempt starting | %s", format_kv(attempt=attempt, fn_name=fn_name))
        try:
            return fn()
        except exceptions as exc:
            last_exc = exc
            wait_seconds = round(REQUEST_PAUSE_SECONDS * (2**attempt), 2)
            is_retryable = classify_exception(exc)
            will_retry = attempt < retries
            exc_msg = str(exc)[:200]
            logger.debug(
                "Retry except caught | %s",
                format_kv(
                    exc_type=type(exc).__name__,
                    exc_msg=exc_msg,
                    is_retryable=is_retryable,
                    wait_seconds=wait_seconds,
                    will_retry=will_retry,
                ),
            )
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
            logger.debug(
                "Retry wrapper entered | %s",
                format_kv(
                    fn_name=fn_name,
                    max_attempts=max_attempts,
                    base_wait=base_wait,
                    exception_types=exception_types,
                ),
            )
            last_exc: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    result = fn(*args, **kwargs)
                    logger.debug(
                        "Retry wrapper succeeded | %s", format_kv(fn_name=fn_name, attempt=attempt)
                    )
                    return result
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
