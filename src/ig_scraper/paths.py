"""Centralized path constants for the ig-scraper project."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
LOGS_DIR = ROOT / "logs"
ACCOUNT_DIR = DATA_DIR / "accounts"
README_FILE = DATA_DIR / "README.md"
HANDLES_FILE = ROOT / "resources" / "instagram_handles.md"
