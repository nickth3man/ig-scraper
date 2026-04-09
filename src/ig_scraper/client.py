"""Instagram authentication client for obtaining an authenticated instaloader Instaloader."""

from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from instaloader import Instaloader, Profile
from instaloader.exceptions import (
    BadCredentialsException,
    ConnectionException,
    TwoFactorAuthRequiredException,
)

from ig_scraper.exceptions import AuthError, IgScraperError
from ig_scraper.logging_utils import format_kv, get_logger


logger = get_logger("auth")


def _load_env() -> None:
    """Load environment variables from .env file in project root."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    logger.debug("Loading environment file | %s", env_path)
    load_dotenv(env_path)


def get_instaloader_client() -> Instaloader:
    """Create and authenticate Instaloader client with fallback auth methods."""
    _load_env()
    env_path = Path(__file__).resolve().parents[2] / ".env"
    sessionid = os.getenv("INSTAGRAM_SESSIONID", "").strip()
    username = os.getenv("INSTAGRAM_USERNAME", "").strip()
    password = os.getenv("INSTAGRAM_PASSWORD", "").strip()
    logger.debug(
        "Environment loaded | %s",
        format_kv(
            env_path=str(env_path),
            env_exists=env_path.exists(),
            sessionid_present=bool(sessionid),
            username_present=bool(username),
            password_present=bool(password),
        ),
    )

    if not sessionid and not (username and password):
        raise IgScraperError(
            "Either INSTAGRAM_SESSIONID or INSTAGRAM_USERNAME/INSTAGRAM_PASSWORD must be set in .env"
        )

    logger.info(
        "Preparing Instaloader client | %s",
        format_kv(
            auth_method="sessionid" if sessionid else "username/password",
            session_length=len(sessionid) if sessionid else 0,
        ),
    )

    # Instaloader automatically handles rate limiting with sleep=True
    loader = Instaloader(
        sleep=True,
        max_connection_attempts=3,
        quiet=False,
    )
    logger.debug("Instaloader configured with built-in rate limiting")

    try:
        auth_method = None
        elapsed_login = 0.0

        # Try session from file if sessionid provided (instaloader uses session files internally)
        if sessionid and username:
            session_file = Path.home() / ".config" / "instaloader" / f"session-{username}"
            if session_file.exists():
                try:
                    logger.debug(
                        "Loading session from file | %s", format_kv(session_file=session_file)
                    )
                    t0_login = time.perf_counter()
                    loader.load_session_from_file(username)
                    # Verify session is valid
                    if not loader.test_login():
                        raise AuthError("Loaded session is invalid")
                    elapsed_login = round(time.perf_counter() - t0_login, 3)
                    logger.debug(
                        "Session file loaded and verified | %s",
                        format_kv(elapsed_seconds=elapsed_login),
                    )
                    auth_method = "session_file"
                except Exception as e:
                    logger.info(
                        "Session file invalid or expired | %s",
                        format_kv(error=str(e), session_file=session_file),
                    )
                    # Fall through to username/password login

        # Username/password authentication
        if auth_method is None and username and password:
            logger.debug("Authenticating via username/password")
            t0_login = time.perf_counter()
            try:
                loader.login(username, password)
                elapsed_login = round(time.perf_counter() - t0_login, 3)
                logger.debug(
                    "Username/password login accepted | %s",
                    format_kv(elapsed_seconds=elapsed_login),
                )
                auth_method = "username/password"
                # Save session for future use
                loader.save_session_to_file(username)
                logger.info("Session saved for future use")
            except TwoFactorAuthRequiredException as e:
                logger.error("Two-factor authentication required but not implemented")
                raise AuthError(
                    "Two-factor authentication is not supported. "
                    "Please disable 2FA on your Instagram account or use a session file."
                ) from e
            except BadCredentialsException as e:
                logger.error("Invalid credentials")
                raise AuthError(
                    "Invalid Instagram credentials. Check username and password."
                ) from e
            except ConnectionException as e:
                logger.error("Connection error during login | %s", format_kv(error=str(e)))
                raise AuthError(f"Connection error during Instagram login: {e}") from e

        if auth_method is None:
            raise IgScraperError("No authentication method succeeded")

        logger.debug("Validating account access")
        t0_account = time.perf_counter()
        # Verify login by loading profile
        account = Profile.from_username(loader.context, username)
        elapsed_account = round(time.perf_counter() - t0_account, 3)
        logger.debug(
            "Profile.from_username returned | %s",
            format_kv(
                elapsed_seconds=elapsed_account,
                username=account.username,
                user_id=account.userid,
                is_private=account.is_private,
                is_verified=account.is_verified,
            ),
        )
        logger.info(
            "Authenticated successfully | %s",
            format_kv(username=account.username, account_id=account.userid),
        )
    except ConnectionException as exc:
        exc_type = type(exc).__name__
        logger.debug(
            "Auth failed | %s",
            format_kv(
                exc_type=exc_type,
                exc_args=str(exc.args)[:200],
            ),
        )
        logger.exception("Instagram connection error during authentication")
        raise AuthError(f"Instagram connection error: {exc}") from exc
    except (AuthError, IgScraperError):
        raise
    except Exception as exc:
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

    return loader
