# ig-scraper

Instagram scraping tool for collecting account data, posts, and comments for analysis.

## Features

- **Profile scraping**: Fetch user profiles with follower counts, bio, etc.
- **Post collection**: Download media, captions, and metadata for posts
- **Comment extraction**: Full pagination support for comment threads
- **Analysis generation**: Automated markdown analysis of account patterns
- **Type-safe models**: Dataclass-based data models for consistent data handling
- **Retry logic**: Exponential backoff for failed API calls
- **Structured logging**: Detailed logging with configurable verbosity

## Installation

Requires Python 3.12+

```bash
# Clone the repository
git clone <repository-url>
cd ig-scraper

# Install dependencies using uv
uv sync

# Or install with pip
pip install -e ".[dev]"
```

## Configuration

Create a `.env` file in the project root:

```env
INSTAGRAM_SESSIONID=your_session_id_here
```

To obtain a session ID:
1. Log into Instagram in your browser
2. Open Developer Tools (F12) → Application/Storage → Cookies
3. Find the `sessionid` cookie value

## Usage

### Basic Usage

```bash
# Scrape a single handle
uv run python -m ig_scraper --handles @username

# Scrape multiple handles
uv run python -m ig_scraper --handles @user1,@user2,@user3

# Scrape all handles from resources/instagram_handles.md
uv run python -m ig_scraper --all

# Limit posts per handle
uv run python -m ig_scraper --handles @username --max-posts-per-handle 50
```

### Output Structure

Data is organized under `data/accounts/`:

```
data/accounts/
└── @username/
    ├── analysis.md          # Generated analysis
    ├── raw-posts.json       # All posts data
    ├── raw-comments.json    # All comments data
    ├── posts/
    │   ├── 001_shortcode/
    │   │   ├── metadata.json
    │   │   ├── comments.json
    │   │   ├── caption.txt
    │   │   └── media/       # Downloaded media files
    │   └── ...
    └── swipes/
        └── post-01.md
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov

# Run specific test file
uv run pytest tests/test_analysis.py

# Run slow tests only
uv run pytest -m slow

# Skip integration tests
uv run pytest -m "not integration"
```

### Code Quality

```bash
# Run linter
uv run ruff check .

# Run formatter
uv run ruff format .

# Run type checker
uv run mypy src/

# Run all checks
uv run python scripts/check_all.py
```

### Project Structure

```
ig-scraper/
├── src/ig_scraper/
│   ├── __init__.py
│   ├── __main__.py          # Package entry point
│   ├── analysis.py          # Text analysis utilities
│   ├── instagram_client.py  # Authentication client
│   ├── instagrapi_fallback.py  # API interaction with retry logic
│   ├── logging_utils.py     # Structured logging
│   ├── models.py            # Typed data models (Profile, Post, Comment)
│   └── run_scrape.py        # CLI entry point
├── tests/
│   ├── conftest.py          # Test fixtures
│   └── test_analysis.py     # Unit tests for analysis functions
├── resources/
│   └── instagram_handles.md # Handles template for --all
├── data/
│   ├── accounts/            # Scraped data (gitignored)
│   └── README.md            # Data documentation
├── pyproject.toml           # Project configuration
├── uv.lock                  # Locked dependencies
└── README.md                # This file
```

## Architecture

### Data Models

The project uses typed dataclasses for Instagram data:

- **Profile**: User profile information (followers, bio, etc.)
- **Post**: Media post with metadata, resources, and media files
- **Comment**: Comment with owner info and engagement metrics
- **PostResource**: Individual image/video within an album/carousel

These models provide:
- Type safety and IDE autocomplete
- JSON serialization via `to_dict()` methods
- Factory methods for instagrapi objects: `from_instagrapi_*()`

### Error Handling

- **Retry logic**: Exponential backoff for transient failures
- **Specific exceptions**: Catches `RuntimeError`, `ConnectionError`, `OSError` instead of broad `Exception`
- **Graceful degradation**: Continues scraping other posts if one fails
- **Structured logging**: All errors logged with context via `format_kv()`

### Testing Strategy

Three-tier testing approach:

1. **Unit tests** (current): Pure functions in `analysis.py`
2. **Mocked integration tests**: Mock `instagrapi.Client` methods
3. **Integration tests**: Real API calls with `@pytest.mark.integration`

## Dependencies

### Runtime
- **instagrapi**: Instagram API client
- **python-dotenv**: Environment variable management
- **requests**: HTTP library (instagrapi dependency)

### Development
- **pytest**: Testing framework
- **pytest-cov**: Coverage reporting
- **pytest-mock**: Enhanced mocking
- **responses**: HTTP mocking for tests
- **mypy**: Static type checking
- **ruff**: Linting and formatting

## License

[Your License Here]

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run all checks (`uv run python scripts/check_all.py`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Troubleshooting

### Authentication Issues

If you get "Instagram authentication failed":
1. Verify your `INSTAGRAM_SESSIONID` is current (they expire)
2. Check that your account isn't rate-limited
3. Ensure you're using the correct session ID format

### Rate Limiting

Instagram aggressively rate-limits scraping. The tool includes:
- Automatic delays between requests (0.25s default)
- Exponential backoff on failures
- Request batching for comments

If you hit rate limits:
- Wait 15-30 minutes before retrying
- Reduce `max-posts-per-handle`
- Use a different session ID

### Data Not Saving

Check that:
1. `data/` directory exists and is writable
2. You have sufficient disk space
3. File paths don't contain special characters (sanitized automatically)
