# AGENTS.md — models/

## OVERVIEW

Four dataclasses: Profile, Post, PostResource, Comment. All use a single-constructor pattern for instaloader sources.

## MODEL CONTRACT

- All fields typed; use `field(default_factory=list)` for mutable defaults
- Underscore-prefixed fields (`_profile`, `_method`) are internal metadata, excluded from `to_dict()`
- Defensive `getattr(obj, "field", default)` required — Instagram objects are untyped and may lack attributes

## CONSTRUCTOR RULES

Each dataclass has one `@classmethod` constructor:

- `from_instaloader_*()` — active code path

Requirements:
1. Log via `format_kv()` with raw source field values for debugging
2. Convert PKs/IDs to `str()` explicitly
3. Use `or ""` / `or 0` fallbacks for nullable source fields
4. Build related objects (PostResource list) inline

## SERIALIZATION RULES

`to_dict()` contract:
- Strip underscore-prefixed fields: `{k: v for k, v in asdict(self).items() if not k.startswith("_")}`
- Post special-cases datetime: `taken_at.isoformat()` if datetime, else `str()`, else `""`
- Comment uses plain `asdict(self)` (no underscore fields to exclude)

## FIELD-CHANGE CHECKLIST

When adding a field to any model:

- [ ] Add to dataclass with type annotation and default
- [ ] Add to `from_instaloader_*()` constructor with `getattr()` mapping
- [ ] Update `to_dict()` if special serialization needed
- [ ] Update `tests/factories.py` — add field or `Ignore()` if underscore-prefixed
- [ ] Regenerate regression tests: delete `tests/test_regressions/*.yml` and re-run
- [ ] Fix inline snapshots: `uv run pytest tests/test_snapshots.py --inline-snapshot=fix`

## TEST IMPACT

- Factories use `Ignore()` for underscore fields (`_profile`, `_method`)
- Regression tests capture `to_dict()` output — field additions change golden files
- Snapshots test structural contracts — new fields require `--inline-snapshot=fix`
