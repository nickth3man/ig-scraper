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

from ig_scraper.exceptions import AuthError, IgScraperError
from ig_scraper.logging_utils import format_kv, get_logger


logger = get_logger("auth")


def _load_env() -> None:
    """Load environment variables from .env file in project root."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    logger.debug("Loading environment file | %s", env_path)
    load_dotenv(env_path)


def get_instagram_client() -> Client:
    """Create and authenticate Instagram client."""
    _load_env()
    env_path = Path(__file__).resolve().parents[2] / ".env"
    sessionid = os.getenv("INSTAGRAM_SESSIONID", "").strip()
    logger.debug(
        "Environment loaded | %s",
        format_kv(
            env_path=str(env_path),
            env_exists=env_path.exists(),
            sessionid_present=bool(sessionid),
            sessionid_length=len(sessionid),
        ),
    )
    if not sessionid:
        raise IgScraperError("INSTAGRAM_SESSIONID is missing from .env")

    logger.info(
        "Preparing Instagram client | %s",
        format_kv(session_length=len(sessionid)),
    )
    request_timeout = int(os.getenv("IG_REQUEST_TIMEOUT_SECONDS", "30"))
    client = Client()
    client.request_timeout = request_timeout
    logger.debug(
        "Client configured | %s",
        format_kv(request_timeout=request_timeout),
    )

    try:
        logger.debug("Authenticating via session id")
        t0_login = time.perf_counter()
        client.login_by_sessionid(sessionid)
        elapsed_login = round(time.perf_counter() - t0_login, 3)
        logger.debug("Session login accepted | %s", format_kv(elapsed_seconds=elapsed_login))
        logger.debug("Validating account access")
        t0_account = time.perf_counter()
        account = client.account_info()
        elapsed_account = round(time.perf_counter() - t0_account, 3)
        logger.debug(
            "account_info() returned | %s",
            format_kv(
                elapsed_seconds=elapsed_account,
                pk=account.pk,
                username=account.username,
                is_private=getattr(account, "is_private", False),
                is_verified=getattr(account, "is_verified", False),
                is_business=getattr(account, "is_business", False),
                account_type=getattr(account, "account_type", 0),
            ),
        )
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
        exc_type = type(exc).__name__
        exc_args_str = str(exc.args)
        exc_args_truncated = exc_args_str[:200] if len(exc_args_str) > 200 else exc_args_str
        sessionid_prefix = sessionid[:8] + "..." if len(sessionid) > 8 else sessionid
        logger.debug(
            "Auth failed | %s",
            format_kv(
                exc_type=exc_type,
                exc_args=exc_args_truncated,
                sessionid_prefix=sessionid_prefix,
            ),
        )
        logger.exception("Instagram authentication failed")
        raise AuthError(f"Instagram authentication failed: {exc}") from exc

    return client
