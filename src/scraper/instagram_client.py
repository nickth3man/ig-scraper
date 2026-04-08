from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from instagrapi import Client

from scraper.logging_utils import format_kv, get_logger


logger = get_logger("auth")


def _load_env() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    logger.info("Loading environment file | %s", env_path)
    load_dotenv(env_path)


@lru_cache(maxsize=1)
def get_instagram_client() -> Client:
    _load_env()
    sessionid = os.getenv("INSTAGRAM_SESSIONID", "").strip()
    if not sessionid:
        raise RuntimeError("INSTAGRAM_SESSIONID is missing from .env")

    logger.info(
        "Preparing Instagram client | %s",
        format_kv(session_length=len(sessionid)),
    )
    client = Client()

    try:
        logger.info("Authenticating via session id")
        client.login_by_sessionid(sessionid)
        logger.info("Session login accepted; validating account access")
        account = client.account_info()
        logger.info(
            "Authenticated successfully | %s",
            format_kv(username=account.username, account_pk=account.pk),
        )
    except Exception as exc:
        logger.exception("Instagram authentication failed")
        raise RuntimeError(f"Instagram authentication failed: {exc}") from exc

    return client
