"""Test fixtures for ig-scraper."""

from __future__ import annotations

import sys
from pathlib import Path


# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


import pytest  # noqa: E402


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
