# ig-scraper

Instagram scraping tool for collecting account data, posts, and comments for analysis using the [instagrapi](https://github.com/adw0rd/instagrapi) library.

## Features

- **Profile scraping**: Fetch user profiles with follower counts, bio, verification status
- **Post collection**: Download media, captions, and metadata for posts
- **Comment extraction**: Full cursor-based pagination for comment threads
- **Media downloads**: Photos, videos, albums (carousels), and reels via instagrapi
- **Analysis generation**: Automated markdown analysis of account patterns (hooks, formats, CTAs, top posts)
- **Type-safe models**: Dataclass-based data models for Profile, Post, PostResource, and Comment
- **Retry logic**: Exponential backoff for transient API failures
- **Structured logging**: Dual-output (console INFO + file DEBUG) with timestamped log files

## Requirements

- Python 3.12+
- Instagram account with a valid `sessionid` cookie

## Installation

```bash
# Clone the repository
git clone https://github.com/<your-repo>/ig-scraper
cd ig-scraper

# Install dependencies (requires uv)
uv sync

# Install dev dependencies
uv sync --group dev
```

## Configuration

Create a `.env` file in the project root:

```env
INSTAGRAM_SESSIONID=your_session_id_here
```

### Obtaining a Session ID

1. Log into Instagram in your browser
2. Open Developer Tools (F12) → Application → Cookies → instagram.com
3. Find the `sessionid` cookie and copy its value

### Optional Tuning Variables

| Variable | Default | Description |
|---|---|---|
| `IG_REQUEST_TIMEOUT_SECONDS` | `30` | Timeout for Instagram API requests |
| `IG_COMMENTS_PAGE_SIZE` | `250` | Number of comments fetched per pagination page |
| `IG_REQUEST_PAUSE_SECONDS` | `0.25` | Delay between requests to avoid rate limiting |
| `IG_COMMENT_PAGE_RETRIES` | `3` | Retry attempts for comment pagination failures |
| `IG_MEDIA_DOWNLOAD_RETRIES` | `3` | Retry attempts for media download failures |

## Usage

### CLI

```bash
# Scrape a single handle
uv run python -m ig_scraper --handles @username

# Scrape multiple handles
uv run python -m ig_scraper --handles @user1,@user2,@user3

# Scrape all handles from resources/instagram_handles.md
uv run python -m ig_scraper --all

# Limit posts per handle (default: 100)
uv run python -m ig_scraper --handles @username --max-posts-per-handle 50
```

> **Note**: Either `--handles` or `--all` is required. The tool authenticates once per run and reuses the client.

### Programmatic

```python
from ig_scraper import get_instagram_client, fetch_profile_posts_and_comments

client = get_instagram_client()
profile, posts, comments = fetch_profile_posts_and_comments("username", posts_per_profile=50)
```

## Output Structure

All output goes under `data/accounts/@<handle>/`:

```
data/accounts/@username/
├── analysis.md          # Generated account analysis report
├── raw-posts.json       # All posts as JSON array
├── raw-comments.json    # All comments as JSON array
├── posts/
│   └── 001_AbCdEfGh/    # One folder per post (index_shortcode)
│       ├── metadata.json
│       ├── comments.json
│       ├── caption.txt
│       └── media/       # Downloaded media files
└── swipes/
    └── post-01.md       # Swipe-worthy post summaries
```

### Analysis Report (`analysis.md`)

Generated markdown covering:
1. **Account Profile** — bio, follower/following counts, format mix
2. **Pattern Observations** — hook patterns, caption themes, hashtag/mention frequency, CTA patterns, comment analysis
3. **Swipe-Worthy Posts** — top 5 posts by engagement with hook + caption summary
4. **What Doesn't Work** — access gaps and data limitations
5. **Strategy Implications** — dominant themes and format mix
6. **Access Log** — scraping method and constraint notes

### Post JSON Schema

```json
{
  "id": "string",
  "pk": "string",
  "short_code": "string",
  "url": "https://www.instagram.com/p/AbCdEfGh/",
  "type": "reel/video | carousel | ... ",
  "caption": "string",
  "comment_count": 0,
  "like_count": 0,
  "taken_at": "ISO8601",
  "owner_username": "string",
  "owner_full_name": "string",
  "owner_id": "string",
  "video_url": "string",
  "thumbnail_url": "string",
  "is_video": false,
  "mentions": ["@user"],
  "hashtags": ["#tag"],
  "resources": [{ "pk", "media_type", "thumbnail_url", "video_url" }],
  "media_files": ["file.jpg"],
  "post_folder": "001_AbCdEfGh",
  "from_url": "https://www.instagram.com/username/",
  "_profile": { ... }
}
```

### Comment JSON Schema

```json
{
  "post_url": "https://www.instagram.com/p/AbCdEfGh/",
  "comment_url": "https://www.instagram.com/p/AbCdEfGh/#comment-123",
  "id": "123456789",
  "text": "Great post!",
  "owner_username": "commenter",
  "owner_full_name": "Commenter Name",
  "owner_profile_pic_url": "https://...",
  "timestamp": "ISO8601",
  "likes_count": 0,
  "replies_count": 0
}
```

## Project Structure

```
ig-scraper/
├── src/ig_scraper/
│   ├── __init__.py              # Public API: exports models + core functions
│   ├── __main__.py              # python -m ig_scraper entry point
│   ├── analysis.py              # Caption/post analysis helpers (hooks, hashtags, top_words)
│   ├── analysis_io.py           # I/O utilities + analysis constants (CTA_TOKENS, HOOK_WORDS)
│   ├── analysis_render.py       # Markdown report builder (build_analysis_markdown)
│   ├── cli.py                   # argparse CLI, handle loop, status tracking
│   ├── client.py                # Session auth via instagrapi + account verification
│   ├── comments.py              # Cursor-based comment pagination (media_comments_chunk)
│   ├── config.py                # Environment variable overrides + rate-limit constants
│   ├── exceptions.py            # Exception hierarchy + classify_exception()
│   ├── logging_utils.py         # Dual-handler logging (console INFO, file DEBUG)
│   ├── media.py                 # Media download dispatch (album/photo/clip/video)
│   ├── media_processing.py      # Per-post pipeline: download → post dict → comments
│   ├── models/
│   │   ├── __init__.py
│   │   ├── comment.py           # Comment dataclass
│   │   ├── post.py              # Post + PostResource dataclasses
│   │   └── profile.py           # Profile dataclass
│   ├── paths.py                 # Centralized Path constants (ROOT, DATA_DIR, etc.)
│   ├── retry.py                 # Exponential backoff (retry_on decorator + _retry_with_backoff)
│   ├── run_scrape.py            # Per-handle orchestration: scrape → write artifacts → update README
│   └── scraper.py               # Profile + media fetch loop (fetch_profile_posts_and_comments)
├── tests/
│   ├── conftest.py              # Pytest fixtures
│   ├── factories.py             # Polyfactory data factories
│   ├── features/                # BDD .feature files
│   ├── test_*.py                # Unit/integration tests
│   └── test_regressions/        # Golden/regression test data
├── scripts/
│   ├── check_all.py             # Runs: ruff check, ruff format --check, mypy, pytest
│   └── check_file_length.py     # Enforces 200-line file limit
├── resources/
│   └── instagram_handles.md     # Handles list for --all (one @handle per line)
├── data/
│   ├── accounts/                # Scraped data (gitignored)
│   └── README.md                # Data corpus documentation
├── pyproject.toml               # Project metadata + tool configuration
├── uv.lock                      # Locked dependencies
└── README.md                    # This file
```

## Development

### Running Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov

# Specific file
uv run pytest tests/test_scraper.py

# Slow tests only
uv run pytest -m slow

# Skip integration tests
uv run pytest -m "not integration"
```

### Code Quality

```bash
# Lint
uv run ruff check .

# Format check
uv run ruff format --check .

# Format + apply fixes
uv run ruff format .

# Type check (mypy)
uv run mypy src/

# All checks (ruff lint, ruff format check, mypy, pytest, file length)
uv run python scripts/check_all.py

# Pre-commit hooks (runs check_all.py on every commit)
uv run pre-commit run --all-files
```

### Exception Handling Strategy

| Exception | Classification | Behavior |
|---|---|---|
| `RuntimeError` | Retryable | Exponential backoff retry |
| `ConnectionError` | Retryable | Exponential backoff retry |
| `TimeoutError` | Retryable | Exponential backoff retry |
| `LoginRequired`, `AuthError` | Fatal | Auth error raised immediately |
| `IgScraperError` subclasses | Fatal | Logged and re-raised |

Graceful degradation: media download failures don't stop the scrape; comment pagination failures don't prevent post metadata from being saved.

## Architecture

### Data Flow

```
cli.main()
  └─> load_handles()          # Read @handles from resources/instagram_handles.md
  └─> initialize_readme()     # Create/update data/README.md status table
  └─> for each handle:
        process_handle()
          ├─> clean_handle()              # Normalize @username → username
          ├─> fetch_profile_posts_and_comments()
          │     ├─> get_instagram_client()         # Auth once per run
          │     ├─> _fetch_user_info()             # instagrapi.user_info_by_username_v1
          │     ├─> _fetch_user_medias()           # instagrapi.user_medias_v1
          │     └─> for each media:
          │           _process_single_media()
          │             ├─> _download_media()      # instagrapi.album/photo/clip/video_download
          │             ├─> _build_post_dict()    # Post dataclass → dict
          │             └─> _fetch_all_comments()   # Paginated via media_comments_chunk
          ├─> write_post_artifacts()     # metadata.json, comments.json, caption.txt, media/
          ├─> write_json(raw-posts.json, raw-comments.json)
          ├─> build_analysis_markdown()  # analysis.md report
          └─> update_readme_status()    # Mark handle as "analyzed" in data/README.md
```

### Authentication

`client.py` loads `INSTAGRAM_SESSIONID` from `.env` and calls `instagrapi.Client.login_by_sessionid()`. It then validates the session by calling `account_info()`. All auth errors (`LoginRequired`, `ChallengeRequired`, `ClientThrottledError`, `FeedbackRequired`, `PleaseWaitFewMinutes`) are caught and re-raised as `AuthError`.

### Retry Mechanism

`retry.py` provides two APIs:
- `@retry_on(*exc_types, max_attempts, wait_base_seconds)` — decorator for clean retry wrapping
- `_retry_with_backoff()` — legacy function-based API

Wait formula: `wait_seconds = REQUEST_PAUSE_SECONDS * (2 ** attempt)`

### Logging

`logging_utils.py` configures dual output on first logger access:
- **Console**: INFO level, human-readable `%(asctime)s | %(levelname)-7s | %(name)s | %(message)s`
- **File**: DEBUG level, timestamped at `logs/YYYY-MM-DD_HH-MM-SS.log`

All log lines use `format_kv()` to produce pipe-delimited `key=value` pairs for grep-friendly traceability.

## Dependencies

### Runtime

| Package | Version | Purpose |
|---|---|---|
| [instagrapi](https://github.com/adw0rd/instagrapi) | ~2.1.5 | Instagram API client |
| python-dotenv | >=1.2.0 | `.env` file loading |
| Pillow | >=8.1.1 | Image processing (instagrapi dep) |
| requests | >=2.33.0 | HTTP library (instagrapi dep) |

### Development

| Package | Purpose |
|---|---|
| pytest + pytest-cov + pytest-mock + pytest-regressions + pytest-bdd | Testing |
| responses | HTTP mocking |
| mypy | Static type checking |
| ruff | Linting and formatting |
| ty | Fast type checker (Astral) |
| bandit | Security linting |
| invoke | Task automation |
| prospector | Comprehensive code analysis |
| hypothesis + polyfactory | Property-based testing + data factories |
| inline-snapshot | Snapshot testing |
| pip-audit | Dependency vulnerability scanning |

## Troubleshooting

### Authentication Failed

```
AuthError: Instagram authentication failed: ...
```

1. Verify your `INSTAGRAM_SESSIONID` is current — Instagram sessions expire
2. Ensure the account isn't temporarily suspended or rate-limited
3. Check that the sessionid cookie is valid and not expired

### Rate Limiting

Instagram aggressively throttles scraping. The tool handles this with:
- Request pauses (0.25s default between operations)
- Exponential backoff on `RuntimeError` / `ConnectionError`
- Full cursor-based comment pagination

If you hit hard limits:
- Wait 15–30 minutes before retrying
- Lower `--max-posts-per-handle`
- Use a different Instagram account's session

### Partial Data

If some posts lack comments or media:
- The tool logs a warning and continues — it never aborts a scrape for partial data
- Brand/private/restricted posts may return sparse captions or no comments
- Check `data/accounts/@username/posts/<shortcode>/` for per-post `metadata.json` with `_profile` access metadata

## Contributing

1. Fork and create a feature branch
2. Make changes with type annotations
3. Run `uv run python scripts/check_all.py` — all checks must pass
4. Commit with a clear message
5. Open a Pull Request

## License

[Your License Here]
