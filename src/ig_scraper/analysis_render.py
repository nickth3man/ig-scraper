"""Markdown rendering for Instagram account analysis reports."""

from __future__ import annotations

from collections import Counter
from typing import Any

from ig_scraper.analysis import (
    CTA_TOKENS,
    extract_hashtags,
    extract_hook,
    extract_mentions,
    get_caption,
    get_comment_count,
    get_like_count,
    get_post_type,
    get_post_url,
    get_shortcode,
    get_timestamp,
    group_comments_by_post,
    summarize_comment_texts,
    top_words,
)


__all__ = ["build_analysis_markdown"]


def _compute_analysis_stats(
    posts: list[dict[str, Any]], comments: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compute all derived statistics from posts and comments for analysis report."""
    profile = posts[0].get("_profile", {}) if posts else {}
    captions = [c for post in posts if (c := get_caption(post))]
    hooks = [extract_hook(text) for text in captions if text]
    common_words = top_words(captions)
    comments_by_post = group_comments_by_post(comments)
    top_posts = sorted(
        posts, key=lambda p: (get_like_count(p), get_comment_count(p)), reverse=True
    )[:5]
    return {
        "profile": profile,
        "captions": captions,
        "hooks": hooks,
        "formats": Counter(get_post_type(post) for post in posts),
        "hashtags": Counter(t for c in captions for t in extract_hashtags(c)),
        "mentions": Counter(t for c in captions for t in extract_mentions(c)),
        "common_words": common_words,
        "comments_by_post": comments_by_post,
        "top_posts": top_posts,
        "total_comments": len(comments),
        "post_count_observed": len(posts),
        "comments": comments,
    }


def _render_profile_section(stats: dict[str, Any], post_count: int) -> list[str]:
    """Render the Account Profile section."""
    p, fmts, words = stats["profile"], stats["formats"], stats["common_words"]
    return [
        "## 1. Account Profile",
        "",
        f"- Bio: {p.get('biography') or 'Captured in raw profile/post payloads when available.'}",
        f"- Observed follower count: {p.get('followers_count') or p.get('followersCount') or 'See raw post/profile payloads.'}",
        f"- Observed following count: {p.get('follows_count') or p.get('followsCount') or 'See raw post/profile payloads.'}",
        f"- Observed post count: {post_count} scraped posts",
        f"- Primary formats: {', '.join(f'{n} ({c})' for n, c in fmts.most_common()) or 'unknown'}",
        f"- Positioning: Inferred from captions/themes — {', '.join(words[:8]) or 'insufficient caption data'}",
        "",
    ]


def _render_patterns_section(stats: dict[str, Any]) -> list[str]:
    """Render the Pattern Observations section."""
    lines: list[str] = ["## 2. Pattern Observations", "", "### Hook patterns", ""]
    lines.extend(f"- {h}" for h in stats["hooks"][:8])
    if not stats["hooks"]:
        lines.append("- No usable hooks extracted from captions.")
    lines += ["", "### Format patterns", ""]
    for name, count in stats["formats"].most_common():
        lines.append(f"- {name}: {count} observed posts")
    if not stats["formats"]:
        lines.append("- No clear format metadata returned.")
    lines += ["", "### Caption patterns", ""]
    lines.append(
        f"- Frequent caption themes/words: {', '.join(stats['common_words']) or 'insufficient data'}"
    )
    lines.append(
        f"- Frequent hashtags: {', '.join(t for t, _ in stats['hashtags'].most_common(10)) or 'none surfaced'}"
    )
    lines.append(
        f"- Frequent mentions: {', '.join(t for t, _ in stats['mentions'].most_common(10)) or 'none surfaced'}"
    )
    lines += ["", "### CTA patterns", ""]
    cta_lines = [
        extract_hook(c) for c in stats["captions"] if any(t in c.lower() for t in CTA_TOKENS)
    ]
    lines.extend(f"- {line}" for line in cta_lines[:6])
    if not cta_lines:
        lines.append("- No explicit CTA language surfaced in sampled captions.")
    lines += ["", "### Comment patterns", ""]
    lines.append(f"- Retrieved comments: {stats['total_comments']}")
    lines.append(
        f"- Posts with comment payloads: {sum(1 for v in stats['comments_by_post'].values() if v)}"
    )
    if stats["total_comments"]:
        lines += ["- Sample comment themes:", summarize_comment_texts(stats["comments"], limit=5)]
    else:
        lines.append("- No comments retrieved from comment scraper for sampled posts.")
    lines.append("")
    return lines


def _render_swipes_section(stats: dict[str, Any]) -> list[str]:
    """Render the Swipe-Worthy Posts section."""
    lines: list[str] = ["## 3. Swipe-Worthy Posts", ""]
    for idx, post in enumerate(stats["top_posts"], start=1):
        url = get_post_url(post)
        caption = get_caption(post)
        key = url or get_shortcode(post) or "unknown"
        n_comments = len(stats["comments_by_post"].get(key, []))
        lines += [
            f"### Post {idx}",
            f"- Format: {get_post_type(post)}",
            f"- Hook: {extract_hook(caption) or 'No caption hook extracted'}",
            f"- Caption summary: {(caption[:500] + ('…' if len(caption) > 500 else '')) or 'No caption returned'}",
            f"- Comment summary: {n_comments} comments captured",
            f"- Why it works: Engagement proxy likes={get_like_count(post)}, comments={get_comment_count(post)}, timestamp={get_timestamp(post) or 'unknown'}",
            "- Pillar mapping: To be interpreted from hook/theme in later synthesis.",
            "- Adaptation note: Reuse hook/frame only if it aligns with target audience and positioning.",
            "",
        ]
    if not stats["top_posts"]:
        lines += ["No posts were returned by the scraper.", ""]
    return lines


def _render_strategy_section(stats: dict[str, Any]) -> list[str]:
    """Render the What Doesn't Work and Strategy Implications sections."""
    words, fmts, tc = stats["common_words"], stats["formats"], stats["total_comments"]
    return [
        "## 4. What Doesn't Work",
        "",
        "- Any post/caption/comment access gaps are logged below rather than inferred away.",
        "- Generic motivational phrasing without proof artifacts should be treated cautiously for adaptation.",
        "",
        "## 5. Strategy Implications",
        "",
        f"1. Highest-signal repeated themes: {', '.join(words[:6]) or 'insufficient data'}.",
        f"2. Dominant observed format mix: {', '.join(f'{n} ({c})' for n, c in fmts.most_common(3)) or 'unknown'}.",
        f"3. Comment retrievability for this handle: {'good' if tc else 'limited/none'}.",
        "",
    ]


def _render_access_log(stats: dict[str, Any]) -> list[str]:
    """Render the Access Log section."""
    return [
        "## Access Log",
        "",
        f"- Method tested: {stats['profile'].get('_method') or 'Apify posts actor + Apify comment actor'}",
        f"- Result: {stats['post_count_observed']} posts and {stats['total_comments']} comments captured",
        "- Constraints: Brand/private/restricted posts may return sparse captions or no comments; raw payloads preserved for audit.",
    ]


def build_analysis_markdown(
    handle: str, posts: list[dict[str, Any]], comments: list[dict[str, Any]]
) -> str:
    """Build a full account-analysis markdown document from scraped posts and comments."""
    stats = _compute_analysis_stats(posts, comments)
    lines = [
        "# Account Analysis",
        "",
        "- Status: analyzed",
        f"- Access: {stats['profile'].get('_method') or 'instagrapi'}",
        "",
    ]
    lines.extend(_render_profile_section(stats, stats["post_count_observed"]))
    lines.extend(_render_patterns_section(stats))
    lines.extend(_render_swipes_section(stats))
    lines.extend(_render_strategy_section(stats))
    lines.extend(_render_access_log(stats))
    return "\n".join(lines).strip() + "\n"
