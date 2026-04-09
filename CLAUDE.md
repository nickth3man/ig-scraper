# CLAUDE.md

## Shell Requirement

This environment uses **bash** on Windows. Always use bash syntax, not PowerShell.
- Wrong: `$env:CI='true'; git status`
- Right: `CI='true' git ## Shell Requirement

This environment uses **bash** on Windows. Always use bash syntax, not PowerShell.
- Wrong: `$env:CI='true'; git status`
- Right: `CI='true' git status` or just `git status`
- Before running any command, verify every token is valid bash.

## Commands

```bash
# Install dependencies
uv sync --group dev

# Run ALL checks (stops on first failure) — do this after every edit
uv run python scripts/check_all.py

# Individual checks
uv run ruff check .                    # Lint
uv run ruff format .                   # Format (apply fixes)
uv run ruff format --check .           # Format (check only)
uv run mypy src/                       # Type check (mypy)
uv run ty check src/                   # Type check (ty)
uv run bandit -c pyproject.toml -r src/ -ll  # Security lint
uv run pytest                          # All tests
uv run pytest --cov                    # Tests with coverage (80% minimum)
uv run python scripts/check_file_length.py   # 200-line file limit

# Run a single test file or test
uv run pytest tests/test_scraper.py
uv run pytest tests/test_scraper.py -k test_name

# Run by marker
uv run pytest -m slow
uv run pytest -m "not integration"

# Invoke tasks (alternative interface)
uv run invoke check       # All checks (lint, typecheck, security, test, file length)
uv run invoke lint        # ruff check + format
uv run invoke typecheck   # ty + mypy
uv run invoke security    # bandit + pip-audit
uv run invoke test        # pytest with coverage
uv run invoke clean       # Remove build artifacts and caches

# CLI usage
uv run python -m ig_scraper --handles @username
uv run python -m ig_scraper --handles @user1,@user2 --max-posts-per-handle 50
uv run python -m ig_scraper --all
```

## Post-Edit Workflow

After any file change, **always** run `uv run python scripts/check_all.py`. This runs in order: ty, mypy, ruff check, ruff format, bandit, pytest, file length check. Fix and re-run until all pass.

**Never use `--no-verify`** to bypass pre-commit hooks.

## Architecture

### Data Flow

```
cli.main() → selected_handles() → for each handle:
  └─ process_handle()                          # run_scrape.py
       ├─ fetch_profile_posts_and_comments()   # scraper.py — main orchestrator
       │    ├─ get_instaloader_client()         # client.py — auth via instaloader
       │    ├─ Profile.from_username()          # fetch profile info
       │    ├─ profile.get_posts() → _take_n()  # fetch media list (iterator-limited)
       │    └─ for each media:
       │         _process_single_media()        # media_processing.py
       │           ├─ _download_media()         # media.py — photo/video/album dispatch
       │           ├─ _build_post_dict()        # Post dataclass → dict
       │           └─ _fetch_all_comments()     # comments.py — cursor-based pagination
       ├─ write_post_artifacts()                # per-post: metadata.json, comments.json, caption.txt
       ├─ write_json(raw-posts.json, raw-comments.json)
       ├─ build_analysis_markdown()             # analysis_render.py → analysis.py → analysis_io.py
       └─ update_readme_status()                # data/README.md status table
```

### Key Modules

- **`client.py`** — Auth via instaloader. Loads credentials from `.env` (session file → username/password fallback). Validates with `Profile.from_username()`.
- **`scraper.py`** — Top-level orchestrator. Fetches profile + media list, delegates each media to `_process_single_media()`.
- **`media_processing.py`** — Per-post pipeline: download → build post dict → fetch comments. Graceful degradation: download/comment failures log warnings and continue.
- **`retry.py`** — `@retry_on(*exc_types)` decorator (preferred) and `_retry_with_backoff()` (legacy). Exponential backoff: `wait = base * 2^attempt`.
- **`exceptions.py`** — Hierarchy rooted at `IgScraperError` (`AuthError`, `MediaDownloadError`, `RetryExhaustedError`). `classify_exception()` uses name-based matching for instaloader exceptions that can't be imported directly. Returns True=retryable, False=fatal.
- **`config.py`** — Env var overrides (`IG_COMMENTS_PAGE_SIZE`, `IG_REQUEST_PAUSE_SECONDS`, etc.) resolved at import time. `_sleep()` is the centralized rate-limiting pause between API calls.
- **`paths.py`** — Centralized `Path` constants: `ROOT`, `DATA_DIR`, `LOGS_DIR`, `ACCOUNT_DIR`, `HANDLES_FILE`.

### Analysis Pipeline (3-module split)

The analysis system is split across three modules to stay under the 200-line limit:
- **`analysis_io.py`** — Constants (`CTA_TOKENS`, `HOOK_WORDS`, truncation limits), path helpers (`handle_dir`, `sanitize_path_segment`), I/O (`write_json`, `write_text`, `clean_handle`).
- **`analysis.py`** — Text extraction utilities (`extract_hashtags`, `extract_mentions`, `extract_hook`, `top_words`, `group_comments_by_post`). Uses a `_first_non_empty(item, keys)` pattern to support multiple field-name variants from different data sources.
- **`analysis_render.py`** — `build_analysis_markdown()` computes stats via `_compute_analysis_stats()`, then renders sections (`_render_profile_section`, `_render_patterns_section`, etc.) into a markdown report.

### Models (dual-constructor pattern)

Each dataclass in `models/` has **two** `@classmethod` constructors:
- `from_instaloader_*()` — used by the active code path
- `from_instagrapi_*()` — legacy, retained for backwards compatibility

All use defensive `getattr(obj, "field", default)` because the Instagram library objects aren't typed. Fields prefixed with `_` (like `_profile`, `_method`) are excluded from `to_dict()` serialization.

### Authentication

The backend is **instaloader** (not instagrapi — despite legacy naming). Auth priority:
1. Session file (if `INSTAGRAM_SESSIONID` + `INSTAGRAM_USERNAME` set and session file exists)
2. Username/password login (saves session for future use)

### Graceful Degradation

Media download and comment pagination failures are caught independently in `_process_single_media()`. A failed download or comment fetch logs a warning and continues — the scrape never aborts for partial data.

## Key Conventions

- **200-line file limit** — enforced by `scripts/check_file_length.py`, scans only `src/ig_scraper/*.py` (not subdirectories or tests). Split large modules.
- **Structured logging** — use `format_kv(key=value, ...)` from `logging_utils.py` for all log messages. Produces pipe-delimited `key=value` pairs. Dual output: console at INFO, file at DEBUG under `logs/`.
- **Google docstring convention** — enforced by ruff D rules (`convention = "google"`).
- **Type annotations required** — mypy with `disallow_untyped_defs = true`. Use `from __future__ import annotations` at the top of every module.
- **ruff line length** — 100 characters.
- **Imports** — ruff isort with `case-sensitive = true`, `lines-after-imports = 2` (two blank lines after imports).
- **Coverage** — 80% minimum (`fail_under = 80`). Branch coverage enabled. `__main__.py` and test files are excluded.

## Testing Patterns

- **Factories** — polyfactory `DataclassFactory` subclasses in `tests/factories.py` (`ProfileFactory`, `PostFactory`, `CommentFactory`, `PostResourceFactory`). Fixtures in `conftest.py` expose them.
- **Mocking** — Instagram API objects are mocked with `MagicMock()`. Tests patch `time.sleep` and `REQUEST_PAUSE_SECONDS` to avoid real delays. Auth tests patch `_load_env` to isolate env loading.
- **BDD** — `pytest-bdd` feature files in `tests/features/` (handle validation, analysis pipeline). Step definitions implement the Gherkin scenarios.
- **Regression tests** — `pytest-regressions` golden files in `tests/test_regressions/` (YAML data snapshots, markdown output).
- **Inline snapshots** — `inline-snapshot` configured with shortcuts: `--inline-snapshot=fix` to create/fix, `--inline-snapshot=review` to review.
- **Markers** — `@pytest.mark.slow`, `@pytest.mark.integration`. Tests use `--strict-markers`.

## CI Pipeline

GitHub Actions runs on push to `main` and all PRs:
1. **quick-check** (gate) — ty, ruff check, ruff format check
2. **typecheck** — mypy (after quick-check passes)
3. **test** — pytest with coverage on Python 3.12 + 3.13 matrix (after quick-check)
4. **security** — pip-audit + bandit (after quick-check)
5. **analysis** — prospector (non-blocking, after test + typecheck)

## External Search Workflows

When searching externally, use these MCP tool patterns. Always run Phase 1 tools in parallel.

| Scenario | Phase 1 (parallel) | Phase 2 (if needed) |
|---|---|---|
| Quick fact check | `perplexity_ask`, `brave_web_search`, `web_search_prime` | `webfetch` / `webReader` for specific URLs |
| Tech docs deep dive | `context7_resolve-library-id`, `tavily-search` (advanced), `brave_web_search` | `context7_query-docs`, `tavily-extract`, `webReader` |
| GitHub code examples | `searchGitHub`, `zread_search_doc`, `deepwiki_read_wiki_contents` | `zread_read_file`, `deepwiki_read_wiki_structure` |
| Deep research | `perplexity_research`, `tavily-search` (advanced, max=20), `websearch_exa` | `tavily-extract`, `brave_web_search` (count=20) |
| Package reference | `context7_resolve-library-id`, `tavily-search` (advanced), `searchGitHub` | `context7_query-docs`, `zread_search_doc`, `webReader` |

**Key principles**: Context7 first for libraries. Tavily with advanced depth for technical topics. DeepWiki for GitHub repo docs (`read_wiki_contents` before, `read_wiki_structure` after). Extract only after identifying valuable URLs.
status` or just `git status`
- Before running any command, verify every token is valid bash.

## Commands

```bash
# Install dependencies
uv sync --group dev

# Run ALL checks (stops on first failure) — do this after every edit
uv run python scripts/check_all.py

# Individual checks
uv run ruff check .                    # Lint
uv run ruff format .                   # Format (apply fixes)
uv run ruff format --check .           # Format (check only)
uv run mypy src/                       # Type check (mypy)
uv run ty check src/                   # Type check (ty)
uv run bandit -c pyproject.toml -r src/ -ll  # Security lint
uv run pytest                          # All tests
uv run pytest --cov                    # Tests with coverage (80% minimum)
uv run python scripts/check_file_length.py   # 200-line file limit

# Run a single test file or test
uv run pytest tests/test_scraper.py
uv run pytest tests/test_scraper.py -k test_name

# Run by marker
uv run pytest -m slow
uv run pytest -m "not integration"

# Invoke tasks (alternative interface)
uv run invoke check       # All checks (lint, typecheck, security, test, file length)
uv run invoke lint        # ruff check + format
uv run invoke typecheck   # ty + mypy
uv run invoke security    # bandit + pip-audit
uv run invoke test        # pytest with coverage
uv run invoke clean       # Remove build artifacts and caches

# CLI usage
uv run python -m ig_scraper --handles @username
uv run python -m ig_scraper --handles @user1,@user2 --max-posts-per-handle 50
uv run python -m ig_scraper --all
```

## Post-Edit Workflow

After any file change, **always** run `uv run python scripts/check_all.py`. This runs in order: ty, mypy, ruff check, ruff format, bandit, pytest, file length check. Fix and re-run until all pass.

**Never use `--no-verify`** to bypass pre-commit hooks.

## Architecture

### Data Flow

```
cli.main() → selected_handles() → for each handle:
  └─ process_handle()                          # run_scrape.py
       ├─ fetch_profile_posts_and_comments()   # scraper.py — main orchestrator
       │    ├─ get_instaloader_client()         # client.py — auth via instaloader
       │    ├─ Profile.from_username()          # fetch profile info
       │    ├─ profile.get_posts() → _take_n()  # fetch media list (iterator-limited)
       │    └─ for each media:
       │         _process_single_media()        # media_processing.py
       │           ├─ _download_media()         # media.py — photo/video/album dispatch
       │           ├─ _build_post_dict()        # Post dataclass → dict
       │           └─ _fetch_all_comments()     # comments.py — cursor-based pagination
       ├─ write_post_artifacts()                # per-post: metadata.json, comments.json, caption.txt
       ├─ write_json(raw-posts.json, raw-comments.json)
       ├─ build_analysis_markdown()             # analysis_render.py → analysis.py → analysis_io.py
       └─ update_readme_status()                # data/README.md status table
```

### Key Modules

- **`client.py`** — Auth via instaloader. Loads credentials from `.env` (session file → username/password fallback). Validates with `Profile.from_username()`.
- **`scraper.py`** — Top-level orchestrator. Fetches profile + media list, delegates each media to `_process_single_media()`.
- **`media_processing.py`** — Per-post pipeline: download → build post dict → fetch comments. Graceful degradation: download/comment failures log warnings and continue.
- **`retry.py`** — `@retry_on(*exc_types)` decorator (preferred) and `_retry_with_backoff()` (legacy). Exponential backoff: `wait = base * 2^attempt`.
- **`exceptions.py`** — Hierarchy rooted at `IgScraperError` (`AuthError`, `MediaDownloadError`, `RetryExhaustedError`). `classify_exception()` uses name-based matching for instaloader exceptions that can't be imported directly. Returns True=retryable, False=fatal.
- **`config.py`** — Env var overrides (`IG_COMMENTS_PAGE_SIZE`, `IG_REQUEST_PAUSE_SECONDS`, etc.) resolved at import time. `_sleep()` is the centralized rate-limiting pause between API calls.
- **`paths.py`** — Centralized `Path` constants: `ROOT`, `DATA_DIR`, `LOGS_DIR`, `ACCOUNT_DIR`, `HANDLES_FILE`.

### Analysis Pipeline (3-module split)

The analysis system is split across three modules to stay under the 200-line limit:
- **`analysis_io.py`** — Constants (`CTA_TOKENS`, `HOOK_WORDS`, truncation limits), path helpers (`handle_dir`, `sanitize_path_segment`), I/O (`write_json`, `write_text`, `clean_handle`).
- **`analysis.py`** — Text extraction utilities (`extract_hashtags`, `extract_mentions`, `extract_hook`, `top_words`, `group_comments_by_post`). Uses a `_first_non_empty(item, keys)` pattern to support multiple field-name variants from different data sources.
- **`analysis_render.py`** — `build_analysis_markdown()` computes stats via `_compute_analysis_stats()`, then renders sections (`_render_profile_section`, `_render_patterns_section`, etc.) into a markdown report.

### Models (dual-constructor pattern)

Each dataclass in `models/` has **two** `@classmethod` constructors:
- `from_instaloader_*()` — used by the active code path
- `from_instagrapi_*()` — legacy, retained for backwards compatibility

All use defensive `getattr(obj, "field", default)` because the Instagram library objects aren't typed. Fields prefixed with `_` (like `_profile`, `_method`) are excluded from `to_dict()` serialization.

### Authentication

The backend is **instaloader** (not instagrapi — despite legacy naming). Auth priority:
1. Session file (if `INSTAGRAM_SESSIONID` + `INSTAGRAM_USERNAME` set and session file exists)
2. Username/password login (saves session for future use)

### Graceful Degradation

Media download and comment pagination failures are caught independently in `_process_single_media()`. A failed download or comment fetch logs a warning and continues — the scrape never aborts for partial data.

## Key Conventions

- **200-line file limit** — enforced by `scripts/check_file_length.py`, scans only `src/ig_scraper/*.py` (not subdirectories or tests). Split large modules.
- **Structured logging** — use `format_kv(key=value, ...)` from `logging_utils.py` for all log messages. Produces pipe-delimited `key=value` pairs. Dual output: console at INFO, file at DEBUG under `logs/`.
- **Google docstring convention** — enforced by ruff D rules (`convention = "google"`).
- **Type annotations required** — mypy with `disallow_untyped_defs = true`. Use `from __future__ import annotations` at the top of every module.
- **ruff line length** — 100 characters.
- **Imports** — ruff isort with `case-sensitive = true`, `lines-after-imports = 2` (two blank lines after imports).
- **Coverage** — 80% minimum (`fail_under = 80`). Branch coverage enabled. `__main__.py` and test files are excluded.

## Testing Patterns

- **Factories** — polyfactory `DataclassFactory` subclasses in `tests/factories.py` (`ProfileFactory`, `PostFactory`, `CommentFactory`, `PostResourceFactory`). Fixtures in `conftest.py` expose them.
- **Mocking** — Instagram API objects are mocked with `MagicMock()`. Tests patch `time.sleep` and `REQUEST_PAUSE_SECONDS` to avoid real delays. Auth tests patch `_load_env` to isolate env loading.
- **BDD** — `pytest-bdd` feature files in `tests/features/` (handle validation, analysis pipeline). Step definitions implement the Gherkin scenarios.
- **Regression tests** — `pytest-regressions` golden files in `tests/test_regressions/` (YAML data snapshots, markdown output).
- **Inline snapshots** — `inline-snapshot` configured with shortcuts: `--inline-snapshot=fix` to create/fix, `--inline-snapshot=review` to review.
- **Markers** — `@pytest.mark.slow`, `@pytest.mark.integration`. Tests use `--strict-markers`.

## CI Pipeline

GitHub Actions runs on push to `main` and all PRs:
1. **quick-check** (gate) — ty, ruff check, ruff format check
2. **typecheck** — mypy (after quick-check passes)
3. **test** — pytest with coverage on Python 3.12 + 3.13 matrix (after quick-check)
4. **security** — pip-audit + bandit (after quick-check)
5. **analysis** — prospector (non-blocking, after test + typecheck)

## External Search Workflows

When searching externally, use these MCP tool patterns. Always run Phase 1 tools in parallel.

| Scenario | Phase 1 (parallel) | Phase 2 (if needed) |
|---|---|---|
| Quick fact check | `perplexity_ask`, `brave_web_search`, `web_search_prime` | `webfetch` / `webReader` for specific URLs |
| Tech docs deep dive | `context7_resolve-library-id`, `tavily-search` (advanced), `brave_web_search` | `context7_query-docs`, `tavily-extract`, `webReader` |
| GitHub code examples | `searchGitHub`, `zread_search_doc`, `deepwiki_read_wiki_contents` | `zread_read_file`, `deepwiki_read_wiki_structure` |
| Deep research | `perplexity_research`, `tavily-search` (advanced, max=20), `websearch_exa` | `tavily-extract`, `brave_web_search` (count=20) |
| Package reference | `context7_resolve-library-id`, `tavily-search` (advanced), `searchGitHub` | `context7_query-docs`, `zread_search_doc`, `webReader` |

**Key principles**: Context7 first for libraries. Tavily with advanced depth for technical topics. DeepWiki for GitHub repo docs (`read_wiki_contents` before, `read_wiki_structure` after). Extract only after identifying valuable URLs.
