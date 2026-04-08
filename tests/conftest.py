"""Test fixtures for ig-scraper."""

from __future__ import annotations

import sys
from pathlib import Path


# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


import pytest  # noqa: E402

from tests.factories import (  # noqa: E402
    CommentFactory,
    PostFactory,
    PostResourceFactory,
    ProfileFactory,
)


@pytest.fixture
def sample_captions():
    """Sample captions for testing text extraction."""
    return [
        "Check out this amazing photo! #photography #art",
        "Love this place @friendname @another.friend",
        "How to improve your skills in 30 days",
        "Watch this transformation! #beforeandafter",
        "Why you should start today @mentor",
    ]


@pytest.fixture
def sample_texts():
    """Sample texts for word frequency testing."""
    return [
        "Python is great for data science",
        "Data science requires Python skills",
        "Great Python libraries for science",
    ]


# --- Polyfactory fixtures ---


@pytest.fixture
def profile_factory():
    """Provide the ProfileFactory class for building test profiles."""
    return ProfileFactory


@pytest.fixture
def post_factory():
    """Provide the PostFactory class for building test posts."""
    return PostFactory


@pytest.fixture
def comment_factory():
    """Provide the CommentFactory class for building test comments."""
    return CommentFactory


@pytest.fixture
def resource_factory():
    """Provide the PostResourceFactory class for building test resources."""
    return PostResourceFactory
