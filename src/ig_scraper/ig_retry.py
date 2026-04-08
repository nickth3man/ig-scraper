"""Retry logic with exponential backoff for Instagram API calls."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ig_scraper.ig_config import REQUEST_PAUSE_SECONDS
from ig_scraper.logging_utils import get_logger


if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger("instagrapi")


class _RetryExhaustedError(Exception):
    """Raised internally when all retry attempts are spent and caller should handle exhaustion."""


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
