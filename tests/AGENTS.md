# tests/AGENTS.md

## Test Fixtures (conftest.py)

`conftest.py` inserts `src/` into `sys.path`. Fixtures exposed:
- `sample_captions` — list of 5 Instagram captions with hashtags/mentions
- `sample_texts` — list of 3 short texts for word frequency testing
- `profile_factory`, `post_factory`, `comment_factory`, `resource_factory` — Polyfactory classes

## Factories (factories.py)

Use `ProfileFactory`, `PostFactory`, `CommentFactory`, `PostResourceFactory`.
- Fields prefixed with `_` (like `_profile`, `_method`) use `Ignore()` — excluded from serialization
- `PostFactory` defaults: `taken_at=datetime(2024, 6, 15, 12, 0, 0)`, empty resources batch
- Build instances: `ProfileFactory.build(username="test")`

## Test Styles

**Standard unit tests**: Plain pytest functions/classes in `test_*.py`.

**BDD** (`tests/features/*.feature`, `test_bdd.py`):
- Feature files define Gherkin scenarios
- `test_bdd.py` implements steps with `@given/@when/@then` decorators
- Use shared context classes (e.g., `HandleContext`) for scenario state

**Regression tests** (`test_regressions.py`, `tests/test_regressions/`):
- Uses `pytest-regressions` with `data_regression` fixture
- Golden files auto-created on first run in `tests/test_regressions/`
- Regenerate: delete `.yml`/`.md` file and re-run test
- YAML for data, `.md` for markdown output

**Inline snapshots** (`test_snapshots.py`):
- Uses `inline-snapshot` library: `assert value == snapshot(expected)`
- Fix command: `uv run pytest tests/test_snapshots.py --inline-snapshot=fix`
- Review command: `uv run pytest tests/test_snapshots.py --inline-snapshot=review`
- Use for structural contracts (to_dict() shapes, markdown headers)

**Property-based tests** (`test_property.py`):
- Uses Hypothesis with `@given` + `@settings(max_examples=N)`
- Strategies built via `st.builds(Factory.build, ...)`
- Tests pure functions with generated inputs to find edge cases

## Markers

- `slow` — slow tests (deselect with `-m "not slow"`)
- `integration` — tests hitting real APIs (deselect with `-m "not integration"`)
- Config enforces `--strict-markers` — undefined markers raise errors

## Commands

```bash
uv run pytest                              # All tests
uv run pytest --cov                        # With coverage (80% min)
uv run pytest -m "not integration"         # Skip integration tests
uv run pytest tests/test_regressions.py    # Regression tests only
uv run pytest --inline-snapshot=fix        # Fix inline snapshots
```

## When to Regenerate vs Fix

**Regenerate golden/snapshot artifacts** when:
- Intentionally changed serialization format
- Added new fields to dataclasses
- Markdown output structure changed by design

**Fix code** when:
- Test fails due to bug (assertion should pass)
- Regression shows unexpected drift in output
- Snapshot mismatch indicates broken contract
