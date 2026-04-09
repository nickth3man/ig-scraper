"""Invoke tasks for development workflow automation."""

from __future__ import annotations

from invoke import task


@task
def clean(c):
    """Clean build artifacts and cache directories."""
    c.run("rm -rf dist/ build/ .pytest_cache/ .mypy_cache/ .ruff_cache/")
    c.run('find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true')
    c.run('find . -type f -name "*.pyc" -delete 2>/dev/null || true')
    c.run("echo 'Cleaned build artifacts'")


@task
def lint(c):
    """Run all linters (ruff)."""
    c.run("uv run ruff check .")
    c.run("uv run ruff format --check .")
    c.run("echo 'Linting passed'")


@task
def typecheck(c):
    """Run type checkers (ty and mypy)."""
    c.run("uv run ty check src/")
    c.run("uv run mypy src/")
    c.run("echo 'Type checking passed'")


@task
def security(c):
    """Run security scans (bandit and pip-audit)."""
    c.run("uv run bandit -r src/ig_scraper")
    c.run("uv run pip-audit")
    c.run("echo 'Security scans passed'")


@task
def test(c, cov=True, markers=""):  # noqa: PT028
    """Run test suite.

    Args:
        c: Invoke context
        cov: Enable coverage reporting (default: True)
        markers: pytest markers to filter tests (e.g., "slow", "not integration")
    """
    cmd = "uv run pytest"
    if cov:
        cmd += " --cov --cov-report=term-missing"
    if markers:
        cmd += f" -m '{markers}'"
    c.run(cmd)
    c.run("echo 'Tests passed'")


@task
def check(c):
    """Run all checks (lint, typecheck, security, test)."""
    lint(c)
    typecheck(c)
    security(c)
    test(c, cov=True, markers="")
    c.run("uv run python scripts/check_file_length.py")
    c.run("echo 'All checks passed'")


@task
def build(c):
    """Build the package."""
    c.run("uv build")
    c.run("echo 'Build completed'")


@task(pre=[clean, check, build])
def release(c):
    """Full release workflow: clean, check, build."""
    c.run("echo 'Release artifacts ready in dist/'")


def scrape(c, handles, max_posts=100):
    """Run scraper for specific handles.

    Args:
        c: Invoke context
        handles: Comma-separated handles (e.g., '@user1,@user2')
        max_posts: Maximum posts per handle (default: 100)
    """
    c.run(f"uv run python -m ig_scraper --handles {handles} --max-posts-per-handle {max_posts}")


@task
def scrape_all(c, max_posts=100):
    """Run scraper for all handles in resources/instagram_handles.md."""
    c.run(f"uv run python -m ig_scraper --all --max-posts-per-handle {max_posts}")
