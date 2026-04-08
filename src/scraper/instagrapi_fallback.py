from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from instagrapi import Client

from scraper.instagram_client import get_instagram_client
from scraper.logging_utils import format_kv, get_logger


COMMENTS_PAGE_SIZE = 250
REQUEST_PAUSE_SECONDS = 0.25
COMMENT_PAGE_RETRIES = 3
MEDIA_DOWNLOAD_RETRIES = 3


logger = get_logger("instagrapi")


def _sleep(reason: str) -> None:
    logger.info(
        "Sleeping between Instagram requests | %s",
        format_kv(reason=reason, seconds=REQUEST_PAUSE_SECONDS),
    )
    time.sleep(REQUEST_PAUSE_SECONDS)


def _media_permalink(username: str, media: Any) -> str:
    kind = "reel" if getattr(media, "product_type", "") == "clips" else "p"
    return f"https://www.instagram.com/{kind}/{media.code}/"


def _resource_to_dict(resource: Any) -> dict[str, Any]:
    return {
        "pk": str(getattr(resource, "pk", "") or ""),
        "media_type": int(getattr(resource, "media_type", 0) or 0),
        "thumbnail_url": str(getattr(resource, "thumbnail_url", "") or ""),
        "video_url": str(getattr(resource, "video_url", "") or ""),
    }


def _download_media(client: Client, media: Any, target_dir: Path) -> list[str]:
    target_dir.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None

    for attempt in range(1, MEDIA_DOWNLOAD_RETRIES + 1):
        try:
            logger.info(
                "Downloading media assets | %s",
                format_kv(
                    shortcode=media.code,
                    media_pk=media.pk,
                    media_type=media.media_type,
                    product_type=getattr(media, "product_type", ""),
                    attempt=f"{attempt}/{MEDIA_DOWNLOAD_RETRIES}",
                    target_dir=target_dir,
                ),
            )

            if media.media_type == 8:
                paths = client.album_download(media.pk, folder=target_dir)
            elif media.media_type == 1:
                paths = [client.photo_download(media.pk, folder=target_dir)]
            elif getattr(media, "product_type", "") == "clips":
                paths = [Path(client.clip_download(media.pk, folder=target_dir))]
            else:
                paths = [client.video_download(media.pk, folder=target_dir)]

            filenames = [Path(path).name for path in paths if path]
            logger.info(
                "Media download complete | %s",
                format_kv(
                    shortcode=media.code, file_count=len(filenames), files=filenames
                ),
            )
            return filenames
        except Exception as exc:
            last_error = exc
            wait_seconds = round(REQUEST_PAUSE_SECONDS * (2**attempt), 2)
            logger.warning(
                "Media download attempt failed | %s",
                format_kv(
                    shortcode=media.code,
                    attempt=f"{attempt}/{MEDIA_DOWNLOAD_RETRIES}",
                    error=exc,
                    retry_wait_seconds=wait_seconds,
                ),
            )
            if attempt == MEDIA_DOWNLOAD_RETRIES:
                break
            time.sleep(wait_seconds)

    raise RuntimeError(
        f"Media download failed for {media.code}: {last_error}"
    ) from last_error


def _comment_to_dict(comment: Any, media_url: str) -> dict[str, Any]:
    return {
        "postUrl": media_url,
        "commentUrl": f"{media_url}#comment-{comment.pk}",
        "id": str(comment.pk),
        "text": comment.text or "",
        "ownerUsername": comment.user.username if comment.user else "",
        "ownerFullName": comment.user.full_name if comment.user else "",
        "ownerProfilePicUrl": str(comment.user.profile_pic_url or "")
        if comment.user
        else "",
        "timestamp": comment.created_at_utc.isoformat()
        if comment.created_at_utc
        else "",
        "likesCount": int(comment.like_count or 0),
        "repliesCount": int(getattr(comment, "child_comment_count", 0) or 0),
        "replies": [],
    }


def _fetch_all_comments(
    client: Client, media_id: str, media_url: str
) -> list[dict[str, Any]]:
    all_comments: list[dict[str, Any]] = []
    min_id: str | None = None
    page = 0

    while True:
        page += 1
        comments_chunk: list[Any] = []
        next_min_id: str | None = None

        for attempt in range(1, COMMENT_PAGE_RETRIES + 1):
            try:
                logger.info(
                    "Fetching comment page | %s",
                    format_kv(
                        media_id=media_id,
                        page=page,
                        attempt=f"{attempt}/{COMMENT_PAGE_RETRIES}",
                        cursor=min_id or "initial",
                        page_size=COMMENTS_PAGE_SIZE,
                    ),
                )
                if min_id is None:
                    comments_chunk, next_min_id = client.media_comments_chunk(
                        media_id, max_amount=COMMENTS_PAGE_SIZE
                    )
                else:
                    comments_chunk, next_min_id = client.media_comments_chunk(
                        media_id, max_amount=COMMENTS_PAGE_SIZE, min_id=min_id
                    )
                break
            except Exception as exc:
                wait_seconds = round(REQUEST_PAUSE_SECONDS * (2**attempt), 2)
                logger.warning(
                    "Comment page fetch failed | %s",
                    format_kv(
                        media_id=media_id,
                        page=page,
                        attempt=f"{attempt}/{COMMENT_PAGE_RETRIES}",
                        error=exc,
                        retry_wait_seconds=wait_seconds,
                    ),
                )
                if attempt == COMMENT_PAGE_RETRIES:
                    logger.warning(
                        "Giving up on further comment pagination; preserving partial comments | %s",
                        format_kv(
                            media_id=media_id,
                            page=page,
                            partial_count=len(all_comments),
                        ),
                    )
                    return all_comments
                time.sleep(wait_seconds)

        if not comments_chunk:
            logger.info(
                "No comments returned for page; ending pagination | %s",
                format_kv(
                    media_id=media_id, page=page, total_comments=len(all_comments)
                ),
            )
            break

        all_comments.extend(
            _comment_to_dict(comment, media_url) for comment in comments_chunk
        )
        logger.info(
            "Comment page fetched | %s",
            format_kv(
                media_id=media_id,
                page=page,
                page_comment_count=len(comments_chunk),
                total_comments=len(all_comments),
                next_cursor=next_min_id or "end",
            ),
        )
        if not next_min_id or next_min_id == min_id:
            break

        min_id = next_min_id
        _sleep("comment pagination backoff")

    return all_comments


def fetch_profile_posts_and_comments(
    username: str, posts_per_profile: int = 100, account_dir: Path | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    logger.info(
        "Starting account scrape | %s",
        format_kv(
            username=username, posts_target=posts_per_profile, account_dir=account_dir
        ),
    )
    client = get_instagram_client()
    logger.info("Fetching profile info | %s", format_kv(username=username))
    user = client.user_info_by_username_v1(username)
    logger.info(
        "Profile info fetched | %s",
        format_kv(
            username=username,
            user_pk=user.pk,
            followers=user.follower_count,
            following=user.following_count,
            total_profile_posts=user.media_count,
        ),
    )
    logger.info(
        "Fetching recent medias | %s",
        format_kv(username=username, amount=posts_per_profile),
    )
    medias = client.user_medias_v1(user.pk, amount=posts_per_profile)
    logger.info(
        "Media list fetched | %s",
        format_kv(username=username, media_count=len(medias)),
    )

    profile = {
        "id": str(user.pk),
        "username": user.username,
        "fullName": user.full_name,
        "biography": user.biography,
        "followersCount": user.follower_count,
        "followsCount": user.following_count,
        "postsCount": user.media_count,
        "verified": user.is_verified,
        "isBusinessAccount": user.is_business,
        "profilePicUrl": str(user.profile_pic_url or ""),
        "externalUrl": str(user.external_url or ""),
    }

    posts: list[dict[str, Any]] = []
    comments: list[dict[str, Any]] = []
    posts_root = account_dir / "posts" if account_dir else None
    total_medias = len(medias)
    for index, media in enumerate(medias, start=1):
        media_url = _media_permalink(username, media)
        post_folder = posts_root / f"{index:03d}_{media.code}" if posts_root else None
        media_folder = post_folder / "media" if post_folder else None
        logger.info(
            "Processing media | %s",
            format_kv(
                username=username,
                progress=f"{index}/{total_medias}",
                shortcode=media.code,
                media_pk=media.pk,
                media_type=media.media_type,
                product_type=getattr(media, "product_type", ""),
                likes=media.like_count or 0,
                comments=media.comment_count or 0,
                target_folder=post_folder,
            ),
        )
        media_files = (
            _download_media(client, media, media_folder) if media_folder else []
        )

        post = {
            "id": str(media.pk),
            "pk": str(media.pk),
            "shortCode": media.code,
            "url": media_url,
            "type": str(media.product_type or media.media_type),
            "caption": media.caption_text or "",
            "comment_count": media.comment_count or 0,
            "like_count": media.like_count or 0,
            "taken_at": media.taken_at.isoformat() if media.taken_at else "",
            "ownerUsername": username,
            "ownerFullName": user.full_name,
            "ownerId": str(user.pk),
            "video_url": str(getattr(media, "video_url", "") or ""),
            "thumbnail_url": str(getattr(media, "thumbnail_url", "") or ""),
            "is_video": media.media_type == 2,
            "mentions": [],
            "hashtags": [],
            "resources": [
                _resource_to_dict(resource)
                for resource in getattr(media, "resources", [])
            ],
            "media_files": media_files,
            "post_folder": str(post_folder.relative_to(account_dir))
            if post_folder and account_dir
            else "",
            "from_url": f"https://www.instagram.com/{username}/",
        }
        posts.append(post)

        try:
            logger.info(
                "Starting full comment pagination | %s",
                format_kv(shortcode=media.code, media_id=media.id, media_url=media_url),
            )
            media_comments = _fetch_all_comments(client, media.id, media_url)
            logger.info(
                "Comment pagination complete | %s",
                format_kv(shortcode=media.code, total_comments=len(media_comments)),
            )
        except Exception as exc:
            logger.warning(
                "Comment collection failed for media; preserving post with zero/partial comments | %s",
                format_kv(shortcode=media.code, media_id=media.id, error=exc),
            )
            media_comments = []

        comments.extend(media_comments)
        logger.info(
            "Media processing complete | %s",
            format_kv(
                username=username,
                progress=f"{index}/{total_medias}",
                shortcode=media.code,
                downloaded_files=len(media_files),
                cumulative_posts=len(posts),
                cumulative_comments=len(comments),
            ),
        )
        _sleep("between media iterations")

    logger.info(
        "Account scrape complete | %s",
        format_kv(username=username, posts=len(posts), comments=len(comments)),
    )

    return profile, posts, comments
