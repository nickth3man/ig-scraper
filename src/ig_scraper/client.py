"""Instagram authentication helpers for authenticated Instaloader access."""

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
from ig_scraper.patch import apply_instaloader_patches
from ig_scraper.session import load_cookies_from_file


apply_instaloader_patches()
logger = get_logger("auth")

_SESSION_FILE_DIR = Path.home() / ".config" / "instaloader"


def _session_file_for(username: str) -> Path:
    """Return the explicit session file path for a username."""
    return _SESSION_FILE_DIR / f"session-{username}"


def _load_env() -> None:
    """Load environment variables from .env file in project root."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    logger.debug("Loading environment file | %s", env_path)
    load_dotenv(env_path)


def get_instaloader_client() -> Instaloader:
    """Create an authenticated Instaloader client.

    Current auth order is cookie-backed session via ``cookies.txt`` when
    ``INSTAGRAM_SESSIONID`` is set, then username/password login with session-file persistence.
    """
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

    loader = Instaloader(
        sleep=True,
        max_connection_attempts=3,
        quiet=True,
    )
    logger.debug("Instaloader configured with built-in rate limiting")

    try:
        auth_method = None
        elapsed_login = 0.0
        session_username = None

        if sessionid:
            try:
                logger.info("Attempting cookie-backed session authentication")
                t0_login = time.perf_counter()

                cookies_file = Path(__file__).resolve().parents[2] / "cookies.txt"
                cookies = load_cookies_from_file(cookies_file) if cookies_file.exists() else {}
                if not cookies:
                    raise AuthError("No cookies found in cookies.txt")
                logger.info("Loaded %d cookies from cookies.txt", len(cookies))

                loader.context.update_cookies(cookies)

                actual_username = loader.test_login()
                if not actual_username:
                    raise AuthError("Cookie-backed session is invalid or expired")

                # update_cookies() doesn't set context.username, so is_logged_in stays
                # False.  Set it explicitly (matches instaloader's __main__.py pattern).
                loader.context.username = actual_username  # type: ignore[assignment]

                session_username = actual_username
                elapsed_login = round(time.perf_counter() - t0_login, 3)
                logger.info(
                    "Cookie-backed session authenticated | %s",
                    format_kv(elapsed_seconds=elapsed_login, username=session_username),
                )
                auth_method = "sessionid"
            except AuthError:
                raise
            except Exception as e:
                logger.info(
                    "Cookie-backed session authentication failed | %s",
                    format_kv(error=str(e)),
                )
                if not (username and password):
                    raise AuthError(
                        f"Cookie-backed session authentication failed and no fallback credentials: {e}"
                    ) from e
        if auth_method is None and username and password:
            logger.info("Authenticating via username/password")
            t0_login = time.perf_counter()
            try:
                loader.login(username, password)
                elapsed_login = round(time.perf_counter() - t0_login, 3)
                logger.info(
                    "Username/password login accepted | %s",
                    format_kv(elapsed_seconds=elapsed_login),
                )
                auth_method = "username/password"
                loader.save_session_to_file(str(_session_file_for(username)))
                logger.info("Session saved for future use")
            except TwoFactorAuthRequiredException as e:
                logger.error(
                    "Two-factor authentication required | %s", format_kv(username=username)
                )
                raise AuthError(
                    "Two-factor authentication is not supported. "
                    "Please disable 2FA on your Instagram account or use a session file."
                ) from e
            except BadCredentialsException as e:
                logger.error("Invalid credentials | %s", format_kv(username=username))
                raise AuthError(
                    "Invalid Instagram credentials. Check username and password."
                ) from e
            except ConnectionException as e:
                logger.error("Connection error during login | %s", format_kv(error=str(e)))
                raise AuthError(f"Connection error during Instagram login: {e}") from e

        if auth_method is None:
            raise IgScraperError("No authentication method succeeded")

        profile_username = session_username or username
        logger.info("Validating account access")
        t0_account = time.perf_counter()
        account = Profile.from_username(loader.context, profile_username)
        elapsed_account = round(time.perf_counter() - t0_account, 3)
        logger.info(
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
        logger.debug(
            "Auth failed | %s", format_kv(exc_type=type(exc).__name__, exc_args=str(exc.args)[:200])
        )
        logger.exception("Instagram connection error during authentication")
        raise AuthError(f"Instagram connection error: {exc}") from exc
    except (AuthError, IgScraperError):
        raise
    except Exception as exc:
        exc_args = str(exc.args)
        logger.debug(
            "Auth failed | %s",
            format_kv(exc_type=type(exc).__name__, exc_args=exc_args[:200]),
        )
        logger.exception("Instagram authentication failed")
        raise AuthError(f"Instagram authentication failed: {exc}") from exc

    return loader
