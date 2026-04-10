"""Scraping orchestration: per-handle processing and artifact writing."""

from __future__ import annotations

import time
from typing import Any

from ig_scraper.analysis import (
    clean_handle,
    get_post_url,
    handle_dir,
    post_dir,
    write_json,
    write_text,
)
from ig_scraper.client import get_instaloader_client
from ig_scraper.export import build_manifest, write_manifest, write_profile
from ig_scraper.highlight_collection import collect_highlights
from ig_scraper.logging_utils import format_kv, get_logger
from ig_scraper.paths import ACCOUNT_DIR
from ig_scraper.relationship_collection import collect_followees, collect_followers
from ig_scraper.saved_collection import collect_saved_posts
from ig_scraper.scraper import fetch_profile_posts_and_comments
from ig_scraper.story_collection import collect_stories
from ig_scraper.tagged_collection import collect_tagged_posts


logger = get_logger("runner")


def write_post_artifacts(handle: str, posts: list[dict], comments: list[dict]) -> None:
    """Write per-post artifact files (metadata, comments, caption) under the accounts directory."""
    logger.info(
        "Writing per-post artifacts | %s",
        format_kv(handle=handle, posts=len(posts), comments=len(comments)),
    )
    comments_by_post_url: dict[str, list[dict]] = {}
    for comment in comments:
        post_url_key = str(comment.get("post_url") or comment.get("postUrl") or "")
        comments_by_post_url.setdefault(post_url_key, []).append(comment)

    for index, post in enumerate(posts, start=1):
        folder = post_dir(ACCOUNT_DIR, handle, index, post)
        folder.mkdir(parents=True, exist_ok=True)
        post_comments = comments_by_post_url.get(get_post_url(post), [])
        logger.info(
            "Persisting post artifact bundle | %s",
            format_kv(
                handle=handle,
                progress=f"{index}/{len(posts)}",
                shortcode=post.get("short_code") or post.get("id"),
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
    method = "instaloader"
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

    write_post_artifacts(handle, posts, comments)
    write_profile(base, profile)

    comments_by_post_url: dict[str, list[dict]] = {}
    for comment in comments:
        post_url_key = str(comment.get("post_url") or comment.get("postUrl") or "")
        comments_by_post_url.setdefault(post_url_key, []).append(comment)

    manifest_items: list[dict] = []
    for index, post in enumerate(posts, start=1):
        post_url = get_post_url(post)
        post_comments = comments_by_post_url.get(post_url, [])
        shortcode = post.get("short_code") or post.get("id") or str(index)
        folder_name = f"{index:03d}_{shortcode}"
        manifest_items.append(
            {
                "index": index,
                "shortcode": shortcode,
                "folder": folder_name,
                "media_count": len(post.get("media_files") or []),
                "comment_count": len(post_comments),
            }
        )

    collections: dict[str, Any] = {}
    skipped_reasons: list[str] = []

    try:
        client = get_instaloader_client()
        from instaloader import Profile

        profile_obj = Profile.from_username(client.context, username)
        highlight_result = collect_highlights(client, profile_obj, base)
        if highlight_result.skipped:
            skipped_reasons.append(f"highlights: {highlight_result.skip_reason or 'unknown'}")
        elif highlight_result.items:
            collections["highlights"] = highlight_result.items
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "Highlights collection failed; continuing | %s",
            format_kv(handle=handle, error=exc),
        )
        skipped_reasons.append(f"highlights: {exc}")

    try:
        client = get_instaloader_client()
        from instaloader import Profile

        profile_obj = Profile.from_username(client.context, username)

        story_result = collect_stories(client, profile_obj, base)
        if story_result.skipped:
            skipped_reasons.append(f"stories: {story_result.skip_reason or 'unknown'}")
        elif story_result.items:
            collections["stories"] = story_result.items

        tagged_result = collect_tagged_posts(profile_obj, base)
        if tagged_result.skipped:
            skipped_reasons.append(f"tagged: {tagged_result.skip_reason or 'unknown'}")
        elif tagged_result.items:
            collections["tagged"] = tagged_result.items

        saved_result = collect_saved_posts(client, profile_obj, base)
        if saved_result.skipped:
            skipped_reasons.append(f"saved: {saved_result.skip_reason or 'unknown'}")
        else:
            collections["saved"] = saved_result.to_dict()

        followers_result = collect_followers(profile_obj, base)
        if followers_result.skipped:
            skipped_reasons.append(f"followers: {followers_result.skipped_reason or 'unknown'}")
        else:
            collections["followers"] = followers_result.to_dict()

        followees_result = collect_followees(profile_obj, base)
        if followees_result.skipped:
            skipped_reasons.append(f"followees: {followees_result.skipped_reason or 'unknown'}")
        else:
            collections["followees"] = followees_result.to_dict()

    except Exception as exc:  # pragma: no cover
        logger.warning(
            "Phase 2 collections failed; continuing | %s",
            format_kv(handle=handle, error=exc),
        )
        skipped_reasons.append(f"collections: {exc}")

    manifest = build_manifest(handle, manifest_items, method=method, collections=collections)
    if skipped_reasons:
        manifest["skipped_reasons"] = skipped_reasons
    write_manifest(base, manifest)
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
