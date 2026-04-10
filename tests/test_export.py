"""Tests for ig_scraper.export — manifest building, manifest/profile writing."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path

from ig_scraper.export import build_manifest, write_manifest, write_profile


# ---------------------------------------------------------------------------
# build_manifest
# ---------------------------------------------------------------------------


class TestBuildManifest:
    """Tests for build_manifest()."""

    def test_empty_posts_returns_valid_manifest(self) -> None:
        """Empty post list produces a v1 manifest with zero items."""
        manifest = build_manifest("alice", [])
        assert manifest["version"] == 1
        assert manifest["handle"] == "alice"
        assert manifest["collections"][0]["count"] == 0
        assert manifest["collections"][0]["items"] == []

    def test_posts_populate_collection_items(self) -> None:
        """Post dicts are forwarded into the collection's items list."""
        posts = [
            {
                "index": 0,
                "shortcode": "AbC1",
                "folder": "001_AbC1",
                "media_count": 2,
                "comment_count": 5,
            },
            {
                "index": 1,
                "shortcode": "DeF2",
                "folder": "002_DeF2",
                "media_count": 1,
                "comment_count": 0,
            },
        ]
        manifest = build_manifest("bob", posts)
        items = manifest["collections"][0]["items"]
        assert len(items) == 2
        assert items[0]["shortcode"] == "AbC1"
        assert items[1]["shortcode"] == "DeF2"

    def test_items_sorted_by_index_ascending(self) -> None:
        """Items are sorted by ``index`` regardless of input order."""
        posts = [
            {"index": 2, "shortcode": "C", "folder": "003_C", "media_count": 0, "comment_count": 0},
            {"index": 0, "shortcode": "A", "folder": "001_A", "media_count": 1, "comment_count": 1},
            {"index": 1, "shortcode": "B", "folder": "002_B", "media_count": 3, "comment_count": 2},
        ]
        items = build_manifest("x", posts)["collections"][0]["items"]
        assert [i["shortcode"] for i in items] == ["A", "B", "C"]

    def test_version_always_one(self) -> None:
        """Manifest version is always 1 regardless of inputs."""
        assert build_manifest("any", [])["version"] == 1
        assert build_manifest("any", [{"index": 0}])["version"] == 1

    def test_profile_file_from_argument(self) -> None:
        """profile_file reflects the argument passed by the caller."""
        manifest = build_manifest("u", [], profile_file="custom_profile.json")
        assert manifest["profile_file"] == "custom_profile.json"

    def test_default_method_is_instaloader(self) -> None:
        """Default method value is 'instaloader'."""
        assert build_manifest("u", [])["method"] == "instaloader"

    def test_scraped_at_is_valid_iso8601(self) -> None:
        """scraped_at field parses as a valid ISO-8601 datetime."""
        manifest = build_manifest("u", [])
        dt = datetime.fromisoformat(manifest["scraped_at"])
        assert dt.tzinfo is not None

    def test_collections_none_does_not_add_extra_domains(self) -> None:
        """Passing collections=None produces only the posts collection."""
        manifest = build_manifest("u", [{"index": 0, "shortcode": "A"}], collections=None)
        assert len(manifest["collections"]) == 1
        assert manifest["collections"][0]["domain"] == "posts"

    def test_collections_populates_additional_domains(self) -> None:
        """Additional collection domains are added to the manifest."""
        extra = {
            "stories": [{"pk": 1}, {"pk": 2}],
            "tagged": [{"pk": 3}],
        }
        manifest = build_manifest("u", [{"index": 0}], collections=extra)
        domains = [c["domain"] for c in manifest["collections"]]
        assert domains == ["posts", "stories", "tagged"]

    def test_collection_entry_includes_auth_required_and_chunked(self) -> None:
        """Each collection entry has auth_required and chunked metadata."""
        collections = {
            "stories": [{"id": 1}],
            "saved": [{"id": 2}],
            "followers": [{"id": 3}],
        }
        manifest = build_manifest("u", [], collections=collections)
        by_domain = {c["domain"]: c for c in manifest["collections"]}

        assert by_domain["posts"]["auth_required"] is False
        assert by_domain["posts"]["chunked"] is False
        assert by_domain["stories"]["auth_required"] is True
        assert by_domain["stories"]["chunked"] is False
        assert by_domain["saved"]["auth_required"] is True
        assert by_domain["saved"]["chunked"] is True
        assert by_domain["followers"]["auth_required"] is True
        assert by_domain["followers"]["chunked"] is True

    def test_unknown_domains_are_ignored(self) -> None:
        """Domains not in _COLLECTION_META are silently skipped."""
        collections = {"stories": [{}], "unknown_domain": [{}], "followees": [{}]}
        manifest = build_manifest("u", [], collections=collections)
        domains = [c["domain"] for c in manifest["collections"]]
        assert "unknown_domain" not in domains
        assert "stories" in domains
        assert "followees" in domains

    def test_collection_items_are_not_sorted(self) -> None:
        """Additional collection items preserve input order (not sorted by index)."""
        collections = {
            "followers": [
                {"index": 2, "username": "c"},
                {"index": 0, "username": "a"},
                {"index": 1, "username": "b"},
            ],
        }
        manifest = build_manifest("u", [], collections=collections)
        items = manifest["collections"][1]["items"]
        assert [i["username"] for i in items] == ["c", "a", "b"]

    def test_skipped_reasons_defaults_to_empty_list(self) -> None:
        """skipped_reasons is an empty list when not provided."""
        manifest = build_manifest("u", [])
        assert manifest["skipped_reasons"] == []

    def test_skipped_reasons_populated(self) -> None:
        """skipped_reasons preserves provided reasons."""
        reasons = ["rate-limited: post 3", "private: post 7"]
        manifest = build_manifest("u", [], skipped_reasons=reasons)
        assert manifest["skipped_reasons"] == reasons

    def test_skipped_reasons_does_not_mutate_input(self) -> None:
        """Returned skipped_reasons is a copy, not the original list."""
        original = ["reason-a"]
        manifest = build_manifest("u", [], skipped_reasons=original)
        manifest["skipped_reasons"].append("reason-b")
        assert original == ["reason-a"]

    def test_summary_dict_emits_count_from_summary_not_len_items(self) -> None:
        """A summary dict's explicit ``count`` is used; ``items`` is always ``[]``."""
        collections = {
            "saved": {"count": 1500, "chunks": [{"offset": 0, "total": 1500}]},
        }
        manifest = build_manifest("u", [], collections=collections)
        entry = next(c for c in manifest["collections"] if c["domain"] == "saved")
        assert entry["count"] == 1500
        assert entry["items"] == []

    def test_summary_dict_includes_optional_chunks(self) -> None:
        """A summary dict with ``chunks`` emits that key in the manifest entry."""
        collections = {
            "followers": {
                "count": 300,
                "chunks": [{"offset": 0, "total": 300}],
            },
        }
        manifest = build_manifest("u", [], collections=collections)
        entry = next(c for c in manifest["collections"] if c["domain"] == "followers")
        assert "chunks" in entry
        assert entry["chunks"] == [{"offset": 0, "total": 300}]

    def test_summary_dict_without_chunks_no_chunks_key(self) -> None:
        """A summary dict without ``chunks`` does not emit a ``chunks`` key."""
        collections = {
            "followees": {"count": 42},
        }
        manifest = build_manifest("u", [], collections=collections)
        entry = next(c for c in manifest["collections"] if c["domain"] == "followees")
        assert "chunks" not in entry

    def test_summary_dict_auth_required_overrides_meta(self) -> None:
        """A summary dict can override ``auth_required`` independently of _COLLECTION_META."""
        collections = {
            "saved": {"count": 10, "auth_required": False},
        }
        manifest = build_manifest("u", [], collections=collections)
        entry = next(c for c in manifest["collections"] if c["domain"] == "saved")
        # Summary dict overrides; note saved normally has auth_required=True in meta.
        assert entry["auth_required"] is False

    def test_summary_dict_chunked_overrides_meta(self) -> None:
        """A summary dict can override ``chunked`` independently of _COLLECTION_META."""
        collections = {
            "saved": {"count": 5, "chunked": False},
        }
        manifest = build_manifest("u", [], collections=collections)
        entry = next(c for c in manifest["collections"] if c["domain"] == "saved")
        # Summary dict overrides; note saved normally has chunked=True in meta.
        assert entry["chunked"] is False

    def test_list_input_still_uses_len_items_for_count(self) -> None:
        """Passing a list still derives ``count`` from ``len(items)``."""
        collections = {
            "followers": [{"username": "a"}, {"username": "b"}, {"username": "c"}],
        }
        manifest = build_manifest("u", [], collections=collections)
        entry = next(c for c in manifest["collections"] if c["domain"] == "followers")
        assert entry["count"] == 3
        assert entry["items"] == [{"username": "a"}, {"username": "b"}, {"username": "c"}]

    def test_list_input_preserves_meta_defaults(self) -> None:
        """List inputs still use _COLLECTION_META defaults for auth_required and chunked."""
        collections = {
            "stories": [{}],
            "saved": [{}],
        }
        manifest = build_manifest("u", [], collections=collections)
        by_domain = {c["domain"]: c for c in manifest["collections"]}
        assert by_domain["stories"]["auth_required"] is True
        assert by_domain["stories"]["chunked"] is False
        assert by_domain["saved"]["auth_required"] is True
        assert by_domain["saved"]["chunked"] is True


# ---------------------------------------------------------------------------
# write_manifest
# ---------------------------------------------------------------------------


class TestWriteManifest:
    """Tests for write_manifest()."""

    def test_creates_manifest_json(self, tmp_path: Path) -> None:
        """write_manifest creates manifest.json under the given directory."""
        account_dir = tmp_path / "@alice"
        manifest = build_manifest("alice", [])
        result = write_manifest(account_dir, manifest)
        assert result == account_dir / "manifest.json"
        assert result.exists()
        data = json.loads(result.read_text(encoding="utf-8"))
        assert data["version"] == 1


# ---------------------------------------------------------------------------
# write_profile
# ---------------------------------------------------------------------------


class TestWriteProfile:
    """Tests for write_profile()."""

    def test_creates_profile_json(self, tmp_path: Path) -> None:
        """write_profile creates profile.json under the given directory."""
        account_dir = tmp_path / "@bob"
        result = write_profile(account_dir, {"username": "bob", "followers": 42})
        assert result == account_dir / "profile.json"
        assert result.exists()
        data = json.loads(result.read_text(encoding="utf-8"))
        assert data["username"] == "bob"
        assert data["followers"] == 42

    def test_strips_underscore_prefixed_keys(self, tmp_path: Path) -> None:
        """Keys starting with '_' are removed before writing."""
        account_dir = tmp_path / "@carol"
        result = write_profile(
            account_dir,
            {"username": "carol", "_method": "cookie", "_internal": True, "bio": "hello"},
        )
        data = json.loads(result.read_text(encoding="utf-8"))
        assert "_method" not in data
        assert "_internal" not in data
        assert data == {"username": "carol", "bio": "hello"}
