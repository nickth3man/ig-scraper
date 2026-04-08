from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


HOOK_WORDS = {
    "how",
    "why",
    "what",
    "watch",
    "if",
    "the",
    "you",
    "your",
    "stop",
    "this",
    "that",
    "with",
    "from",
    "into",
    "your",
    "have",
    "want",
    "more",
    "will",
    "just",
    "they",
    "them",
    "then",
    "than",
    "about",
    "because",
    "here",
    "there",
    "when",
    "where",
    "which",
    "their",
    "follow",
    "along",
    "lets",
    "crush",
    "together",
    "comment",
    "free",
    "personalized",
    "roadmap",
    "business",
    "under",
    "seconds",
    "years",
    "year",
    "old",
    "started",
    "story",
}


def clean_handle(handle: str) -> str:
    return handle.strip().lstrip("@").strip()


def handle_dir(base_dir: Path, handle: str) -> Path:
    return base_dir / f"@{clean_handle(handle)}"


def sanitize_path_segment(value: str, fallback: str = "item") -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return text[:120] or fallback


def post_dir(base_dir: Path, handle: str, index: int, post: dict[str, Any]) -> Path:
    shortcode = get_shortcode(post) or str(post.get("id") or index)
    name = sanitize_path_segment(f"{index:03d}_{shortcode}", fallback=f"{index:03d}")
    return handle_dir(base_dir, handle) / "posts" / name


def ensure_swipes_dir(base_dir: Path, handle: str) -> Path:
    path = handle_dir(base_dir, handle) / "swipes"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def _first_non_empty(item: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def get_caption(post: dict[str, Any]) -> str:
    value = _first_non_empty(post, ["caption", "text", "description"])
    if isinstance(value, list):
        return "\n".join(str(v) for v in value if v)
    return str(value or "").strip()


def get_post_url(post: dict[str, Any]) -> str:
    value = _first_non_empty(post, ["url", "postUrl", "post_url", "displayUrl"])
    return str(value or "").strip()


def get_shortcode(post: dict[str, Any]) -> str:
    value = _first_non_empty(post, ["shortCode", "shortcode", "code"])
    return str(value or "").strip()


def get_comment_count(post: dict[str, Any]) -> int:
    value = _first_non_empty(
        post, ["commentsCount", "comments_count", "commentCount", "comment_count"]
    )
    try:
        return int(value or 0)
    except Exception:
        return 0


def get_like_count(post: dict[str, Any]) -> int:
    value = _first_non_empty(
        post, ["likesCount", "likes_count", "likeCount", "like_count"]
    )
    try:
        return int(value or 0)
    except Exception:
        return 0


def get_timestamp(post: dict[str, Any]) -> str:
    value = _first_non_empty(
        post, ["timestamp", "takenAtTimestamp", "taken_at", "createdAt", "displayTime"]
    )
    return str(value or "").strip()


def get_post_type(post: dict[str, Any]) -> str:
    value = _first_non_empty(post, ["type", "typename", "productType", "mediaType"])
    text = str(value or "unknown").lower()
    if "reel" in text or "clip" in text or "video" in text:
        return "reel/video"
    if "sidecar" in text or "carousel" in text:
        return "carousel"
    if text == "unknown" and (
        post.get("videoUrl") or post.get("video_url") or post.get("is_video")
    ):
        return "reel/video"
    from_url = str(post.get("from_url") or "").lower()
    url = str(post.get("url") or "").lower()
    if "/reel/" in url or "/reels/" in from_url:
        return "reel/video"
    if post.get("images") and len(post.get("images", [])) > 1:
        return "carousel"
    return text


def extract_hashtags(text: str) -> list[str]:
    return re.findall(r"#\w+", text)


def extract_mentions(text: str) -> list[str]:
    return re.findall(r"@\w+(?:\.\w+)?", text)


def extract_hook(text: str) -> str:
    if not text:
        return ""
    first_line = text.splitlines()[0].strip()
    if len(first_line) <= 140:
        return first_line
    sentence = re.split(r"(?<=[.!?])\s+", first_line)[0].strip()
    return sentence[:140]


def top_words(texts: list[str], limit: int = 12) -> list[str]:
    tokens: list[str] = []
    for text in texts:
        for word in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text.lower()):
            if word not in HOOK_WORDS and not word.isdigit():
                tokens.append(word)
    return [word for word, _ in Counter(tokens).most_common(limit)]


def group_comments_by_post(
    comments: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for comment in comments:
        key = str(
            _first_non_empty(
                comment,
                ["postUrl", "post_url", "postId", "post_id", "shortCode", "shortcode"],
            )
            or "unknown"
        )
        grouped[key].append(comment)
    return grouped


def summarize_comment_texts(comments: list[dict[str, Any]], limit: int = 5) -> str:
    texts = []
    for comment in comments[:limit]:
        text = str(
            _first_non_empty(comment, ["text", "commentText", "comment"]) or ""
        ).strip()
        if text:
            texts.append(f'- "{text[:180]}"')
    return "\n".join(texts) if texts else "No comment text retrieved."


def build_analysis_markdown(
    handle: str, posts: list[dict[str, Any]], comments: list[dict[str, Any]]
) -> str:
    profile = posts[0].get("_profile", {}) if posts else {}
    captions = [get_caption(post) for post in posts if get_caption(post)]
    hooks = [extract_hook(text) for text in captions if text]
    formats = Counter(get_post_type(post) for post in posts)
    hashtags = Counter(tag for caption in captions for tag in extract_hashtags(caption))
    mentions = Counter(tag for caption in captions for tag in extract_mentions(caption))
    common_words = top_words(captions)
    comments_by_post = group_comments_by_post(comments)
    top_posts = sorted(
        posts,
        key=lambda post: (get_like_count(post), get_comment_count(post)),
        reverse=True,
    )[:5]
    total_comments = len(comments)

    post_count_observed = len(posts)

    lines: list[str] = []
    lines.append("# Account Analysis")
    lines.append("")
    lines.append("- Status: analyzed")
    lines.append(f"- Access: {profile.get('_method') or 'instagrapi'}")
    lines.append("")
    lines.append("## 1. Account Profile")
    lines.append("")
    lines.append(
        f"- Bio: {profile.get('biography') or 'Captured in raw profile/post payloads when available.'}"
    )
    lines.append(
        f"- Observed follower count: {profile.get('followersCount') or 'See raw post/profile payloads.'}"
    )
    lines.append(
        f"- Observed following count: {profile.get('followsCount') or 'See raw post/profile payloads.'}"
    )
    lines.append(f"- Observed post count: {post_count_observed} scraped posts")
    lines.append(
        f"- Primary formats: {', '.join(f'{name} ({count})' for name, count in formats.most_common()) or 'unknown'}"
    )
    lines.append(
        f"- Positioning: Inferred from captions/themes — {', '.join(common_words[:8]) or 'insufficient caption data'}"
    )
    lines.append("")
    lines.append("## 2. Pattern Observations")
    lines.append("")
    lines.append("### Hook patterns")
    lines.append("")
    for hook in hooks[:8]:
        lines.append(f"- {hook}")
    if not hooks:
        lines.append("- No usable hooks extracted from captions.")
    lines.append("")
    lines.append("### Format patterns")
    lines.append("")
    for name, count in formats.most_common():
        lines.append(f"- {name}: {count} observed posts")
    if not formats:
        lines.append("- No clear format metadata returned.")
    lines.append("")
    lines.append("### Caption patterns")
    lines.append("")
    lines.append(
        f"- Frequent caption themes/words: {', '.join(common_words) or 'insufficient data'}"
    )
    lines.append(
        f"- Frequent hashtags: {', '.join(tag for tag, _ in hashtags.most_common(10)) or 'none surfaced'}"
    )
    lines.append(
        f"- Frequent mentions: {', '.join(tag for tag, _ in mentions.most_common(10)) or 'none surfaced'}"
    )
    lines.append("")
    lines.append("### CTA patterns")
    lines.append("")
    cta_lines = []
    for caption in captions:
        lowered = caption.lower()
        if any(
            token in lowered
            for token in [
                "comment",
                "dm",
                "link in bio",
                "save",
                "share",
                "follow",
                "reply",
            ]
        ):
            cta_lines.append(extract_hook(caption))
    for line in cta_lines[:6]:
        lines.append(f"- {line}")
    if not cta_lines:
        lines.append("- No explicit CTA language surfaced in sampled captions.")
    lines.append("")
    lines.append("### Comment patterns")
    lines.append("")
    lines.append(f"- Retrieved comments: {total_comments}")
    lines.append(
        f"- Posts with comment payloads: {sum(1 for items in comments_by_post.values() if items)}"
    )
    if total_comments:
        lines.append("- Sample comment themes:")
        lines.append(summarize_comment_texts(comments, limit=5))
    else:
        lines.append("- No comments retrieved from comment scraper for sampled posts.")
    lines.append("")
    lines.append("## 3. Swipe-Worthy Posts")
    lines.append("")
    for idx, post in enumerate(top_posts, start=1):
        url = get_post_url(post)
        caption = get_caption(post)
        comment_key = url or get_shortcode(post) or "unknown"
        lines.append(f"### Post {idx}")
        lines.append(f"- Format: {get_post_type(post)}")
        lines.append(f"- Hook: {extract_hook(caption) or 'No caption hook extracted'}")
        lines.append(
            f"- Caption summary: {(caption[:500] + ('…' if len(caption) > 500 else '')) or 'No caption returned'}"
        )
        lines.append(
            f"- Comment summary: {len(comments_by_post.get(comment_key, []))} comments captured"
        )
        lines.append(
            f"- Why it works: Engagement proxy likes={get_like_count(post)}, comments={get_comment_count(post)}, timestamp={get_timestamp(post) or 'unknown'}"
        )
        lines.append(
            "- Found42 pillar mapping: To be interpreted from hook/theme in later synthesis."
        )
        lines.append(
            "- Adaptation note: Reuse hook/frame only if it aligns with Found42's executive audience and proof-first positioning."
        )
        lines.append("")
    if not top_posts:
        lines.append("No posts were returned by the scraper.")
        lines.append("")
    lines.append("## 4. What Doesn't Work")
    lines.append("")
    lines.append(
        "- Any post/caption/comment access gaps are logged below rather than inferred away."
    )
    lines.append(
        "- Generic motivational phrasing without proof artifacts should be treated cautiously for Found42 adaptation."
    )
    lines.append("")
    lines.append("## 5. Strategy Implications")
    lines.append("")
    lines.append(
        f"1. Highest-signal repeated themes: {', '.join(common_words[:6]) or 'insufficient data'}."
    )
    lines.append(
        f"2. Dominant observed format mix: {', '.join(f'{name} ({count})' for name, count in formats.most_common(3)) or 'unknown'}."
    )
    lines.append(
        f"3. Comment retrievability for this handle: {'good' if total_comments else 'limited/none'}."
    )
    lines.append("")
    lines.append("## Access Log")
    lines.append("")
    lines.append(
        f"- Method tested: {profile.get('_method') or 'Apify posts actor + Apify comment actor'}"
    )
    lines.append(
        f"- Result: {post_count_observed} posts and {total_comments} comments captured"
    )
    lines.append(
        "- Constraints: Brand/private/restricted posts may return sparse captions or no comments; raw payloads preserved for audit."
    )
    return "\n".join(lines).strip() + "\n"
