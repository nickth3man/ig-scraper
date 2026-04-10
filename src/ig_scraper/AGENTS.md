# AGENTS.md — src/ig_scraper

## OVERVIEW

22 Python files. Main application boundary. Orchestration chain:
cli → run_scrape → scraper → media_processing

## WHERE TO LOOK

| Purpose | File(s) |
|---------|---------|
| Entry point | `cli.py` — argparse, handle loop, status tracking |
| Per-handle orchestration | `run_scrape.py` — scrape → write artifacts → update README |
| Core scraper | `scraper.py` — `fetch_profile_posts_and_comments()` |
| Per-post pipeline | `media_processing.py` — download → build post dict → fetch comments |
| Auth | `client.py` — `get_instaloader_client()` via session file or username/password |
| Media download | `media.py` — photo/video/album dispatch |
| Comments pagination | `comments.py` — cursor-based chunk fetching |
| Models | `models/profile.py`, `models/post.py`, `models/comment.py` |

## SOURCE RULES

- **200-line limit** — enforced on `src/ig_scraper/*.py` only (not subdirs/tests)
- **Absolute imports** — use `from ig_scraper.module import ...`, never relative
- **Paths** — import from `paths.py` (`ROOT`, `DATA_DIR`, `LOGS_DIR`), never hardcode
- **Future annotations** — every module starts with `from __future__ import annotations`
- **Type annotations** — required; mypy enforces `disallow_untyped_defs = true`
- **Line length** — 100 characters (ruff)
- **Google docstrings** — enforced by ruff D rules
- **Imports** — ruff isort with `case-sensitive = true`, `lines-after-imports = 2`

## SHARED UTILITY SPINE

These six modules form the foundation; import them freely:

- `logging_utils.py` — `get_logger("name")`, `format_kv(k=v, ...)` for structured logs
- `paths.py` — centralized `Path` constants (`ROOT`, `DATA_DIR`, `LOGS_DIR`, `ACCOUNT_DIR`, `HANDLES_FILE`)
- `config.py` — env overrides (`IG_COMMENTS_PAGE_SIZE`, `IG_REQUEST_PAUSE_SECONDS`), `_sleep(reason)` for rate limiting
- `exceptions.py` — hierarchy: `IgScraperError` → `AuthError`, `MediaDownloadError`, `RetryExhaustedError`; `classify_exception()` returns True=retryable
- `retry.py` — `@retry_on(*exc_types, max_attempts, wait_base_seconds)` decorator; exponential backoff `wait = base * 2^attempt`

## FAILURE/RETRY CONTRACT

- **Graceful degradation** — media download and comment failures log warnings via `format_kv()` and continue; scrape never aborts for partial data
- **Fatal errors** — `AuthError` and `IgScraperError` subclasses propagate immediately (not retried)
- **Retryable errors** — `RuntimeError`, `ConnectionError`, `TimeoutError` + instaloader name-matched exceptions get exponential backoff
- **Structured logging pattern**: `logger.warning("msg | %s", format_kv(key=value))`

## SPLIT PATTERN

Large modules are split to stay under 200 lines:

- **Analysis** — three-module split:
  - `analysis_io.py` — constants (`CTA_TOKENS`, `HOOK_WORDS`), I/O helpers, path sanitization
  - `analysis.py` — text extraction (`extract_hashtags`, `extract_mentions`, `extract_hook`, `top_words`)
  - `analysis_render.py` — `build_analysis_markdown()` computes stats and renders markdown report

- **Models** — single-constructor pattern per dataclass:
  - `from_instaloader_*()` — active code path
  - All use defensive `getattr(obj, "field", default)`; underscore-prefixed fields excluded from `to_dict()`
