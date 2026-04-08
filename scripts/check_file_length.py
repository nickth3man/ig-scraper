#!/usr/bin/env python3
"""Check Python file line counts to enforce the 200-line limit."""

from pathlib import Path


MAX_LINES = 200
SRC_DIR = Path("src/ig_scraper")


def count_lines(file_path: Path) -> int:
    """Count total lines in a Python file (including blank lines and comments)."""
    with open(file_path, encoding="utf-8") as f:
        return sum(1 for _ in f)


def main() -> int:
    """Scan Python files and check line counts. Returns 0 if all pass, 1 if any fail."""
    offending_files: list[tuple[Path, int]] = []

    for py_file in sorted(SRC_DIR.glob("*.py")):
        line_count = count_lines(py_file)
        if line_count > MAX_LINES:
            offending_files.append((py_file, line_count))

    if offending_files:
        print("ERROR: The following Python files exceed the 200-line limit:")
        for file_path, count in offending_files:
            print(f"  - {file_path}: {count} lines")
        print()
        print("Please split large files into smaller modules.")
        return 1

    print("OK: All Python files are within the 200-line limit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
