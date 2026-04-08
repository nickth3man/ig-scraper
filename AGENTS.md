# Agent Instructions

## Post-Edit Workflow

After making any file changes, **ALWAYS** run the following commands in order:

### 1. Run the Linter
```bash
uv run ruff check .
```
Fix any linting errors before proceeding.

### 2. Run the Formatter
```bash
uv run ruff format .
```
This automatically formats all Python files to match the project's style.

### 3. Run All Tests
```bash
uv run pytest
```
All tests must pass before committing changes.

### Quick Check (All-in-One)
```bash
uv run ruff check . && uv run ruff format . && uv run pytest
```

## Project Tooling Reference

| Tool | Purpose | Command |
|------|---------|---------|
| ruff | Linting | `uv run ruff check .` |
| ruff | Formatting | `uv run ruff format .` |
| mypy | Type checking | `uv run mypy src/` |
| pytest | Testing | `uv run pytest` |
| pytest + coverage | Test coverage | `uv run pytest --cov` |

## Pre-Commit Hooks

This project has pre-commit hooks configured. The following checks run automatically on commit:
- Trailing whitespace removal
- End-of-file fixer
- YAML validation
- Merge conflict detection
- Ruff linting and formatting
- mypy type checking
- File length check (200 line limit)

To run pre-commit hooks manually:
```bash
uv run pre-commit run --all-files
```
