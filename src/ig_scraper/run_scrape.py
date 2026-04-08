"""Scraping orchestration: per-handle processing, artifact writing, and README management."""

from __future__ import annotations

import re
import time
from pathlib import Path

from ig_scraper.analysis import (
    build_analysis_markdown,
    clean_handle,
    ensure_swipes_dir,
    get_post_url,
    handle_dir,
    post_dir,
    write_json,
    write_text,
)
from ig_scraper.instagrapi_fallback import fetch_profile_posts_and_comments
from ig_scraper.logging_utils import format_kv, get_logger


logger = get_logger("runner")

ROOT = Path(__file__).resolve().parents[2]
ACCOUNT_DIR = ROOT / "data" / "accounts"
DATA_DIR = ROOT / "data"
README_FILE = DATA_DIR / "README.md"


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

def cleanup_removed_handle_dirs(handles: list[str]) -> None:
    """Log a notice that destructive cleanup is intentionally skipped."""
    logger.info(
        "Skipping destructive cleanup of non-target handles | %s",
        format_kv(target_handle_count=len(handles)),
    )


def write_post_artifacts(handle: str, posts: list[dict], comments: list[dict]) -> None:
    """Write per-post artifact files (metadata, comments, caption) under the accounts directory."""
    logger.info(
        "Writing per-post artifacts | %s",
        format_kv(handle=handle, posts=len(posts), comments=len(comments)),
    )
    comments_by_post_url: dict[str, list[dict]] = {}
    for comment in comments:
        comments_by_post_url.setdefault(str(comment.get("postUrl") or ""), []).append(comment)

    for index, post in enumerate(posts, start=1):
        folder = post_dir(ACCOUNT_DIR, handle, index, post)
        folder.mkdir(parents=True, exist_ok=True)
        post_comments = comments_by_post_url.get(get_post_url(post), [])
        logger.info(
            "Persisting post artifact bundle | %s",
            format_kv(
                handle=handle,
                progress=f"{index}/{len(posts)}",
                shortcode=post.get("shortCode") or post.get("id"),
                folder=folder,
                comment_count=len(post_comments),
                media_files=len(post.get("media_files") or []),
            ),
        )

        write_json(folder / "metadata.json", post)
        write_json(folder / "comments.json", post_comments)
        write_text(folder / "caption.txt", str(post.get("caption") or ""))


def process_handle(handle: str, max_posts: int) -> str:
    """Scrape a single handle end-to-end and return the access method used."""
    username = clean_handle(handle)
    method = "instagrapi"
    base = handle_dir(ACCOUNT_DIR, handle)
    handle_started_at = time.perf_counter()
    logger.info(
        "Starting handle sync | %s",
        format_kv(handle=handle, username=username, target_posts=max_posts, base_dir=base),
    )
    base.mkdir(parents=True, exist_ok=True)
    logger.info("Handle directory ready without deletion | %s", format_kv(path=base))

    profile, posts, comments = fetch_profile_posts_and_comments(
        username, posts_per_profile=max_posts, account_dir=base
    )
    logger.info(
        "Raw scrape returned account payloads | %s",
        format_kv(handle=handle, posts=len(posts), comments=len(comments), method=method),
    )

    for post in posts:
        post["_profile"] = {**profile, "_method": method}

    write_post_artifacts(handle, posts, comments)
    ensure_swipes_dir(ACCOUNT_DIR, handle)

    write_json(base / "raw-posts.json", posts)
    write_json(base / "raw-comments.json", comments)
    logger.info(
        "Wrote top-level raw payloads | %s",
        format_kv(
            handle=handle,
            raw_posts_path=base / "raw-posts.json",
            raw_comments_path=base / "raw-comments.json",
        ),
    )
    (base / "analysis.md").write_text(
        build_analysis_markdown(handle, posts, comments), encoding="utf-8"
    )
    logger.info(
        "Analysis markdown written | %s",
        format_kv(handle=handle, path=base / "analysis.md"),
    )

    for idx, post in enumerate(posts[:5], start=1):
        post_url = get_post_url(post)
        swipe = [
            f"# Swipe {idx}",
            "",
            f"- URL: {post_url or 'unknown'}",
            f"- Engagement proxy: likes={post.get('like_count', 0)}, comments={post.get('comment_count', 0)}",
        ]
        (base / "swipes" / f"post-{idx:02d}.md").write_text(
            "\n".join(swipe) + "\n", encoding="utf-8"
        )
        logger.info(
            "Swipe summary written | %s",
            format_kv(handle=handle, swipe_index=idx, url=post_url or "unknown"),
        )

    logger.info(
        "Handle sync complete | %s",
        format_kv(
            handle=handle,
            method=method,
            posts=len(posts),
            comments=len(comments),
            elapsed_seconds=round(time.perf_counter() - handle_started_at, 2),
        ),
    )
    return method

def update_readme_status(handle: str, analysis: str, access: str, notes: str = "") -> None:
    """Update the README status row for *handle* with the latest analysis/access result."""
    text = README_FILE.read_text(encoding="utf-8")
    pattern = rf"^\| {re.escape(handle)} \| .*?\| .*?\| .*?\|$"
    replacement = f"| {handle} | {analysis} | {access} | {notes} |"
    README_FILE.write_text(re.sub(pattern, replacement, text, flags=re.MULTILINE), encoding="utf-8")
