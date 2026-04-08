"""README management for account corpus status tracking."""

from __future__ import annotations

import re

from ig_scraper.logging_utils import format_kv, get_logger
from ig_scraper.paths import ACCOUNT_DIR, README_FILE


logger = get_logger("runner")


def initialize_readme(handles: list[str]) -> None:
    """Create or update the data/README.md status table with the given handles."""
    logger.info(
        "Initializing account README | %s",
        format_kv(handle_count=len(handles), readme_path=README_FILE),
    )
    ACCOUNT_DIR.mkdir(parents=True, exist_ok=True)
    if not README_FILE.exists():
        rows = [
            "# Account Corpus",
            "",
            "This directory holds per-account Instagram research used to improve `instagram-strategy.md`.",
            "",
            "## Method",
            "",
            "- Source list: `resources/instagram_handles.md`",
            "- Account folder naming: exact handle, lowercase, including `@`",
            "- One `analysis.md` per account",
            "- One `posts/<index>_<shortcode>/` folder per scraped post",
            "- Each post folder stores `metadata.json`, `comments.json`, `caption.txt`, and `media/` assets",
            "- Cross-account patterns belong in `SYNTHESIS.md`",
            "",
            "## Status",
            "",
            "| Handle | Analysis | Access | Notes |",
            "|---|---|---|---|",
        ]
        rows.extend(f"| {handle} | pending | queued | awaiting scrape |" for handle in handles)
        rows.extend(
            [
                "",
                "## Notes",
                "",
                "- Comments are fetched to exhaustion via authenticated pagination whenever Instagram returns cursors.",
                "- Per-post media downloads are stored under each post folder's `media/` directory.",
            ]
        )
        README_FILE.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return

    text = README_FILE.read_text(encoding="utf-8")
    insert_after = "|---|---|---|---|"
    for handle in handles:
        if re.search(rf"^\| {re.escape(handle)} \| .*?$", text, flags=re.MULTILINE):
            continue
        text = text.replace(
            insert_after,
            insert_after + f"\n| {handle} | pending | queued | awaiting scrape |",
            1,
        )
    README_FILE.write_text(text, encoding="utf-8")


def update_readme_status(handle: str, analysis: str, access: str, notes: str = "") -> None:
    """Update the README status row for *handle* with the latest analysis/access result."""
    text = README_FILE.read_text(encoding="utf-8")
    pattern = rf"^\| {re.escape(handle)} \| .*?\| .*?\| .*?\|$"
    replacement = f"| {handle} | {analysis} | {access} | {notes} |"
    README_FILE.write_text(re.sub(pattern, replacement, text, flags=re.MULTILINE), encoding="utf-8")
