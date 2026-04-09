"""CLI entry point for scraping Instagram handles into per-account data directories."""

from __future__ import annotations

import argparse
import time

from ig_scraper.errors import IgScraperError
from ig_scraper.logging_utils import configure_logging, format_kv, get_logger
from ig_scraper.paths import HANDLES_FILE
from ig_scraper.run_scrape import (
    cleanup_removed_handle_dirs,
    initialize_readme,
    process_handle,
    update_readme_status,
)


logger = get_logger("runner")


def load_handles() -> list[str]:
    """Read Instagram handles from the handles markdown file, returning one handle per line."""
    handles = []
    for line in HANDLES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("@"):
            handles.append(line)
    return handles


def parse_args() -> argparse.Namespace:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Scrape Instagram handles into account/ using authenticated Instagram access"
    )
    parser.add_argument(
        "--handles",
        default="",
        help="Comma-separated handles like @account_one,@account_two",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all handles from resources/instagram_handles.md",
    )
    parser.add_argument("--max-posts-per-handle", type=int, default=100)
    return parser.parse_args()


def selected_handles(args: argparse.Namespace) -> list[str]:
    """Return the list of handles to process based on parsed CLI arguments."""
    if args.all:
        return load_handles()
    if args.handles:
        return [item.strip() for item in args.handles.split(",") if item.strip()]
    raise SystemExit("Provide --all or --handles")


def main() -> None:
    """CLI entry point: parse arguments, scrape all selected handles, and update README status."""
    configure_logging()
    args = parse_args()
    handles = selected_handles(args)
    total_handles = len(handles)
    job_started_at = time.perf_counter()
    success_count = 0
    failure_count = 0
    logger.info(
        "Starting scrape job | %s",
        format_kv(
            total_handles=total_handles,
            max_posts_per_handle=args.max_posts_per_handle,
        ),
    )
    initialize_readme(handles)
    cleanup_removed_handle_dirs(handles)
    for handle_index, handle in enumerate(handles, start=1):
        logger.info(
            "Dispatching handle | %s",
            format_kv(progress=f"{handle_index}/{total_handles}", handle=handle),
        )
        try:
            method = process_handle(
                handle,
                max_posts=args.max_posts_per_handle,
            )
            update_readme_status(
                handle,
                "analyzed",
                method,
                f"{args.max_posts_per_handle} posts target; all comments",
            )
            success_count += 1
            logger.info(
                "Handle succeeded | %s",
                format_kv(
                    progress=f"{handle_index}/{total_handles}",
                    handle=handle,
                    method=method,
                ),
            )
        except (KeyboardInterrupt, SystemExit):
            raise
        except (IgScraperError, OSError, RuntimeError, ConnectionError, ValueError) as exc:
            update_readme_status(handle, "failed", "error", str(exc).replace("|", "/")[:80])
            failure_count += 1
            logger.exception(
                "Handle failed with traceback | %s",
                format_kv(progress=f"{handle_index}/{total_handles}", handle=handle, error=exc),
            )

    logger.info(
        "Scrape job complete | %s",
        format_kv(
            total_handles=total_handles,
            succeeded=success_count,
            failed=failure_count,
            elapsed_seconds=round(time.perf_counter() - job_started_at, 2),
        ),
    )


if __name__ == "__main__":
    main()
