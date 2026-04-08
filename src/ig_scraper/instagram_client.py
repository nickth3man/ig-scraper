"""Instagram authentication client for obtaining an authenticated instagrapi Client."""

from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.exceptions import (
    ChallengeRequired,
    ClientThrottledError,
    FeedbackRequired,
    LoginRequired,
    PleaseWaitFewMinutes,
)

from ig_scraper.errors import AuthError, IgScraperError
from ig_scraper.logging_utils import format_kv, get_logger


logger = get_logger("auth")


def _load_env() -> None:
    """Load environment variables from .env file in project root."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    logger.info("Loading environment file | %s", env_path)
    load_dotenv(env_path)


def get_instagram_client() -> Client:
    """Create and authenticate Instagram client."""
    _load_env()
    sessionid = os.getenv("INSTAGRAM_SESSIONID", "").strip()
    if not sessionid:
        raise IgScraperError("INSTAGRAM_SESSIONID is missing from .env")

    logger.info(
        "Preparing Instagram client | %s",
        format_kv(session_length=len(sessionid)),
    )
    request_timeout = int(os.getenv("IG_REQUEST_TIMEOUT_SECONDS", "30"))
    client = Client()
    client.request_timeout = request_timeout
    logger.info(
        "Client configured | %s",
        format_kv(request_timeout=request_timeout),
    )

    try:
        logger.info("Authenticating via session id")
        t0_login = time.perf_counter()
        client.login_by_sessionid(sessionid)
        elapsed_login = round(time.perf_counter() - t0_login, 3)
        logger.info("Session login accepted | %s", format_kv(elapsed_seconds=elapsed_login))
        logger.info("Validating account access")
        t0_account = time.perf_counter()
        account = client.account_info()
        elapsed_account = round(time.perf_counter() - t0_account, 3)
        logger.info("account_info() returned | %s", format_kv(elapsed_seconds=elapsed_account))
        logger.info(
            "Authenticated successfully | %s",
            format_kv(username=account.username, account_pk=account.pk),
        )
    except (
        LoginRequired,
        ChallengeRequired,
        ClientThrottledError,
        FeedbackRequired,
        PleaseWaitFewMinutes,
    ) as exc:
        logger.exception("Instagram authentication failed")
        raise AuthError(f"Instagram authentication failed: {exc}") from exc

    return client
