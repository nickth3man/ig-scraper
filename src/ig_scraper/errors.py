"""Custom exception hierarchy for ig_scraper."""


class IgScraperError(Exception):
    """Base exception for all ig_scraper errors."""


class AuthError(IgScraperError):
    """Raised when Instagram authentication fails."""


class MediaDownloadError(IgScraperError):
    """Raised when media download fails."""
