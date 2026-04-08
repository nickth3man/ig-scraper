#!/usr/bin/env python3
"""Run all project checks in sequence: lint, format, type checking, tests, file length.

Exits on the first failure with a non-zero exit code.
Intended for use as a pre-commit hook and manual CI-like verification.
"""

import subprocess
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent

# Ordered steps: (label, command)
STEPS: list[tuple[str, list[str]]] = [
    ("ruff check (lint)", ["uv", "run", "ruff", "check", "."]),
    ("ruff format (check)", ["uv", "run", "ruff", "format", "--check", "."]),
    ("ty (type checking)", ["uv", "run", "ty", "check", "src/"]),
    ("mypy (type checking)", ["uv", "run", "mypy", "src/"]),
    ("pytest (tests)", ["uv", "run", "pytest"]),
    ("file length check", ["uv", "run", "python", str(SCRIPTS_DIR / "check_file_length.py")]),
]


def run_step(label: str, cmd: list[str]) -> bool:
    """Run a single check step. Returns True on success."""
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"  $ {' '.join(cmd)}")
    print(f"{'=' * 60}")

    result = subprocess.run(cmd)  # noqa: S603

    if result.returncode == 0:
        print(f"  PASS: {label}")
        return True

    print(f"  FAIL: {label} (exit code {result.returncode})", file=sys.stderr)
    return False


def main() -> int:
    """Run all checks. Returns 0 if all pass, 1 if any fail."""
    print("Running all project checks...")
    failures: list[str] = []

    for label, cmd in STEPS:
        if not run_step(label, cmd):
            failures.append(label)
            break  # stop on first failure

    print(f"\n{'=' * 60}")
    if not failures:
        print("  All checks passed!")
        return 0

    print(f"  FAILED at: {failures[0]}", file=sys.stderr)
    print("  Fix the issue above and re-run.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
