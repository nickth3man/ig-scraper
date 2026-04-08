"""Enforce max line count per source file.

Each Python file in src/ is a separate test item, so pytest -v shows
per-file PASS/FAIL and --lf reruns only the files that grew too large.
"""

from __future__ import annotations

from pathlib import Path

import pytest


MAX_LINES = 200
SRC_DIR = Path(__file__).resolve().parent.parent / "src"


def _collect_python_files() -> list[Path]:
    return sorted(p for p in SRC_DIR.rglob("*.py") if p.name != "__init__.py")


@pytest.mark.parametrize(
    "src_file",
    _collect_python_files(),
    ids=lambda p: str(p.relative_to(SRC_DIR)),
)
def test_file_line_count(src_file: Path) -> None:
    """File must not exceed the project line limit."""
    lines = src_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= MAX_LINES, (
        f"{src_file.relative_to(SRC_DIR.parent)}: {len(lines)} lines "
        f"(max {MAX_LINES}). Split into smaller modules."
    )
