# Agent Instructions

## Shell Requirement

This environment uses **bash** as the execution shell, including on Windows.
Always write and run commands using **bash syntax**, not PowerShell syntax.
For example, use `VAR=value command` or `export VAR=value`, not `$env:VAR='value'`.

### Bash-Only Command Guardrail

- **Never** use PowerShell environment-variable syntax in this repo, even on Windows:
  - Wrong: `$env:CI='true'; git status --short`
  - Wrong: `$env:GIT_PAGER='cat'; git commit -m "message"`
- **Never** prepend a generic "safe command prefix" copied from another shell or project.
- For simple commands, prefer the plain bash command with **no** env prefix at all:
  - Right: `git status --short`
  - Right: `git mv "old" "new"`
  - Right: `git commit -m "message"`
- If environment variables are actually needed, use **bash** forms only:
  - Right: `CI='true' GIT_PAGER='cat' git status --short`
  - Right: `export CI='true' GIT_PAGER='cat'` then run the command
- Before running any command on Windows, quickly sanity-check that every token is valid **bash** syntax.
- If you see `$env:` anywhere in a command, stop and rewrite it before execution.

## Post-Edit Workflow

After making any file changes, **ALWAYS** run the all-in-one check script:

```bash
uv run python scripts/check_all.py
```

This runs all checks in order: ruff lint, ruff format check, ty, mypy, pytest, file length.
It stops on the first failure. Fix the issue and re-run until all checks pass.

**NEVER use `--no-verify` to bypass these checks.** The pre-commit hook exists to catch issues before they reach CI. Bypassing it with `--no-verify` defeats this protection and can introduce bugs or style violations into the codebase.

Alternatively, run individual checks:

### 1. Run the Linter
```bash
uv run ruff check .
```

### 2. Run the Formatter
```bash
uv run ruff format .
```

### 3. Run Type Checkers
```bash
uv run ty check src/
uv run mypy src/
```

### 4. Run All Tests
```bash
uv run pytest
```

### 5. Check File Lengths
```bash
uv run python scripts/check_file_length.py
```

## Project Tooling Reference

| Tool | Purpose | Command |
|------|---------|---------|
| ruff | Linting | `uv run ruff check .` |
| ruff | Formatting | `uv run ruff format .` |
| ty | Type checking | `uv run ty check src/` |
| mypy | Type checking | `uv run mypy src/` |
| pytest | Testing | `uv run pytest` |
| pytest + coverage | Test coverage | `uv run pytest --cov` |
| check_all.py | All checks | `uv run python scripts/check_all.py` |

## Pre-Commit Hooks

This project has pre-commit hooks configured. On every commit the following runs:

1. **Standard hooks** (trailing whitespace, end-of-file fixer, YAML validation, merge conflict detection)
2. **check_all.py** — unified runner that executes in order:
   - ruff check (lint)
   - ruff format (check only)
   - ty (type checking)
   - mypy (type checking)
   - pytest (all tests)
   - file length check (200 line limit)

   Stops on the first failure.

To run pre-commit hooks manually:
```bash
uv run pre-commit run --all-files
```
