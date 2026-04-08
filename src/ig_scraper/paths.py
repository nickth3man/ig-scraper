"""Centralized path constants for the ig-scraper project."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ACCOUNT_DIR = DATA_DIR / "accounts"
README_FILE = DATA_DIR / "README.md"
VERBOSE_LOG_FILE = ROOT / "verbose-run.log"
HANDLES_FILE = ROOT / "resources" / "instagram_handles.md"
