# Copyright 2026 xNetVN Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for disk cleanup safety and configuration helpers."""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from xnetvn_monitord.monitors.disk_cleanup import purge_quarantine_items  # noqa: E402
from xnetvn_monitord.monitors.disk_cleanup import quarantine_cleanup_candidates  # noqa: E402
from xnetvn_monitord.monitors.disk_cleanup import restore_quarantine_directory  # noqa: E402
from xnetvn_monitord.monitors.disk_cleanup import restore_quarantine_manifest  # noqa: E402
from xnetvn_monitord.monitors.disk_cleanup import (  # noqa: E402
    DEFAULT_PROTECTED_PATHS,
    normalize_cleanup_config,
    path_matches_selector,
    scan_cleanup_candidates,
)


class TestDiskCleanupConfigNormalization:
    """Tests for cleanup config normalization and selector validation."""

    def test_should_accept_exact_regex_and_glob_selectors(self):
        """Supported selector types should normalize without errors."""
        config = {
            "enabled": True,
            "mode": "quarantine_then_delete",
            "selectors": {
                "include": [
                    {"type": "exact", "pattern": "/var/log/app.log"},
                    {"type": "regex", "pattern": r"^/var/tmp/.+"},
                    {"type": "glob", "pattern": "/home/*/.cache/**"},
                ],
                "exclude": [],
            },
            "safety": {},
        }

        normalized = normalize_cleanup_config(config)

        assert [item["type"] for item in normalized["selectors"]["include"]] == ["exact", "regex", "glob"]

    def test_should_reject_invalid_selector_type(self):
        """Unsupported selector types must be rejected."""
        config = {
            "mode": "quarantine_then_delete",
            "selectors": {
                "include": [{"type": "prefix", "pattern": "/tmp"}],
                "exclude": [],
            },
            "safety": {},
        }

        with pytest.raises(ValueError, match="Unsupported selector type"):
            normalize_cleanup_config(config)

    def test_should_reject_invalid_regex_selector(self):
        """Broken regular expressions must be rejected during normalization."""
        config = {
            "mode": "quarantine_then_delete",
            "selectors": {
                "include": [{"type": "regex", "pattern": r"[unterminated"}],
                "exclude": [],
            },
            "safety": {},
        }

        with pytest.raises(ValueError, match="Invalid regex selector"):
            normalize_cleanup_config(config)

    def test_should_merge_builtin_protected_paths_with_configured_entries(self):
        """Built-in protected paths should always remain active."""
        config = {
            "mode": "quarantine_then_delete",
            "selectors": {"include": [], "exclude": []},
            "safety": {"protected_paths": ["/srv/important"]},
        }

        normalized = normalize_cleanup_config(config)

        for protected_path in DEFAULT_PROTECTED_PATHS:
            assert protected_path in normalized["safety"]["protected_paths"]
        assert "/srv/important" in normalized["safety"]["protected_paths"]

    def test_should_reject_unsupported_cleanup_mode(self):
        """Unsupported cleanup modes must be rejected during normalization."""
        with pytest.raises(ValueError, match="Unsupported cleanup mode"):
            normalize_cleanup_config({"mode": "delete_immediately"})

    def test_should_reject_empty_selector_pattern(self):
        """Selector patterns must be non-empty strings."""
        with pytest.raises(ValueError, match="Selector pattern must be a non-empty string"):
            normalize_cleanup_config(
                {
                    "mode": "quarantine_then_delete",
                    "selectors": {"include": [{"type": "glob", "pattern": ""}], "exclude": []},
                }
            )


class TestDiskCleanupPathSelection:
    """Tests for selector matching and safe candidate scanning."""

    def test_should_match_exact_path_case_sensitively(self):
        """Exact matches must remain case-sensitive."""
        selector = {"type": "exact", "pattern": "/var/log/App.LOG"}

        assert path_matches_selector("/var/log/App.LOG", selector) is True
        assert path_matches_selector("/var/log/app.log", selector) is False

    def test_should_match_regex_against_normalized_absolute_path(self):
        """Regex selectors should evaluate against the normalized absolute path."""
        selector = {"type": "regex", "pattern": r"^/srv/cache/.+\.tmp$"}

        assert path_matches_selector("/srv/cache/file.tmp", selector) is True
        assert path_matches_selector("/srv/cache/file.log", selector) is False

    def test_should_match_glob_against_normalized_absolute_path(self):
        """Glob selectors should support shell-style absolute path matching."""
        selector = {"type": "glob", "pattern": "/home/*/.cache/**"}

        assert path_matches_selector("/home/alice/.cache/pip/http-v2", selector) is True
        assert path_matches_selector("/home/alice/cache/pip/http-v2", selector) is False

    def test_should_raise_when_matching_unknown_selector_type_directly(self):
        """Direct selector matching should still reject unknown selector types."""
        with pytest.raises(ValueError, match="Unsupported selector type"):
            path_matches_selector("/tmp/file.log", {"type": "prefix", "pattern": "/tmp"})

    def test_should_skip_excluded_paths_before_descending(self, tmp_path):
        """Excluded directories should be pruned before their children are scanned."""
        root_path = tmp_path / "mount"
        included_dir = root_path / "cache"
        excluded_dir = root_path / "skip-me"
        included_dir.mkdir(parents=True)
        excluded_dir.mkdir(parents=True)
        (included_dir / "keep.log").write_text("x" * 1024, encoding="utf-8")
        (excluded_dir / "skip.log").write_text("x" * 1024, encoding="utf-8")

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "selectors": {
                    "include": [{"type": "glob", "pattern": f"{root_path}/**"}],
                    "exclude": [{"type": "glob", "pattern": f"{excluded_dir}/**"}],
                },
                "rules": {"min_age_days": 0, "min_size_mb": 0, "file_types": ["file"]},
                "safety": {},
            }
        )

        candidates = scan_cleanup_candidates(str(root_path), cleanup_config, current_time=1_000_000)

        assert str(included_dir / "keep.log") in [item["path"] for item in candidates]
        assert str(excluded_dir / "skip.log") not in [item["path"] for item in candidates]

    def test_should_skip_protected_paths(self, tmp_path):
        """Protected paths must never appear in cleanup candidates."""
        root_path = tmp_path / "mount"
        protected_dir = root_path / "protected"
        protected_dir.mkdir(parents=True)
        protected_file = protected_dir / "secret.log"
        protected_file.write_text("x" * 1024, encoding="utf-8")

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "selectors": {
                    "include": [{"type": "glob", "pattern": f"{root_path}/**"}],
                    "exclude": [],
                },
                "rules": {"min_age_days": 0, "min_size_mb": 0, "file_types": ["file"]},
                "safety": {"protected_paths": [str(protected_dir)]},
            }
        )

        candidates = scan_cleanup_candidates(str(root_path), cleanup_config, current_time=1_000_000)

        assert str(protected_file) not in [item["path"] for item in candidates]

    def test_should_skip_symlink_targets(self, tmp_path):
        """Symlinked entries must not be scanned as cleanup candidates."""
        root_path = tmp_path / "mount"
        root_path.mkdir(parents=True)
        target_file = tmp_path / "outside.log"
        target_file.write_text("x" * 1024, encoding="utf-8")
        symlink_path = root_path / "outside-link.log"
        symlink_path.symlink_to(target_file)

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "selectors": {
                    "include": [{"type": "glob", "pattern": f"{root_path}/**"}],
                    "exclude": [],
                },
                "rules": {"min_age_days": 0, "min_size_mb": 0, "file_types": ["file"]},
                "safety": {},
            }
        )

        candidates = scan_cleanup_candidates(str(root_path), cleanup_config, current_time=1_000_000)

        assert str(symlink_path) not in [item["path"] for item in candidates]

    def test_should_skip_paths_outside_mount_boundary(self, tmp_path):
        """Candidate scanning must never escape the target mount root."""
        mount_root = tmp_path / "mount"
        outside_root = tmp_path / "outside"
        mount_root.mkdir(parents=True)
        outside_root.mkdir(parents=True)
        inside_file = mount_root / "inside.log"
        outside_file = outside_root / "outside.log"
        inside_file.write_text("x" * 1024, encoding="utf-8")
        outside_file.write_text("x" * 1024, encoding="utf-8")

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "selectors": {
                    "include": [
                        {"type": "glob", "pattern": f"{mount_root}/**"},
                        {"type": "glob", "pattern": f"{outside_root}/**"},
                    ],
                    "exclude": [],
                },
                "rules": {"min_age_days": 0, "min_size_mb": 0, "file_types": ["file"]},
                "safety": {"require_same_filesystem_as_mount_point": True},
            }
        )

        candidates = scan_cleanup_candidates(str(mount_root), cleanup_config, current_time=1_000_000)

        assert str(inside_file) in [item["path"] for item in candidates]
        assert str(outside_file) not in [item["path"] for item in candidates]

    def test_should_return_no_candidates_when_include_selectors_are_empty(self, tmp_path):
        """A scan without include selectors must fail closed and return no candidates."""
        mount_root = tmp_path / "mount"
        mount_root.mkdir(parents=True)
        candidate = mount_root / "candidate.log"
        candidate.write_text("payload", encoding="utf-8")

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "selectors": {"include": [], "exclude": []},
                "rules": {"min_age_days": 0, "min_size_mb": 0, "file_types": ["file"]},
                "safety": {},
            }
        )

        assert scan_cleanup_candidates(str(mount_root), cleanup_config, current_time=1_000_000) == []

    def test_should_enforce_min_age_and_min_size_rules(self, tmp_path):
        """Candidates below age or size thresholds must be skipped."""
        mount_root = tmp_path / "mount"
        mount_root.mkdir(parents=True)
        young_file = mount_root / "young.log"
        small_file = mount_root / "small.log"
        eligible_file = mount_root / "eligible.log"
        young_file.write_text("payload" * 1024, encoding="utf-8")
        small_file.write_text("tiny", encoding="utf-8")
        eligible_file.write_text("payload" * 1024, encoding="utf-8")
        os.utime(young_file, (1_000_000, 1_000_000))
        os.utime(small_file, (1_000_000 - 10 * 24 * 60 * 60, 1_000_000 - 10 * 24 * 60 * 60))
        os.utime(eligible_file, (1_000_000 - 10 * 24 * 60 * 60, 1_000_000 - 10 * 24 * 60 * 60))

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "selectors": {"include": [{"type": "glob", "pattern": f"{mount_root}/**"}], "exclude": []},
                "rules": {"min_age_days": 7, "min_size_mb": 0.001, "file_types": ["file"]},
                "safety": {},
            }
        )

        candidates = scan_cleanup_candidates(str(mount_root), cleanup_config, current_time=1_000_000)

        assert [item["path"] for item in candidates] == [str(eligible_file)]


class TestDiskCleanupQuarantine:
    """Tests for quarantine move safety and manifest generation."""

    def test_should_require_quarantine_on_same_filesystem_when_configured(self, tmp_path, mocker):
        """Quarantine should fail closed when filesystem affinity is required and violated."""
        mount_root = tmp_path / "mount"
        quarantine_root = tmp_path / "quarantine"
        mount_root.mkdir(parents=True)
        quarantine_root.mkdir(parents=True)
        candidate = mount_root / "candidate.log"
        candidate.write_text("x" * 1024, encoding="utf-8")

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "quarantine_dir": str(quarantine_root),
                "safety": {"require_quarantine_same_filesystem": True},
            }
        )
        real_os_stat = os.stat

        def fake_os_stat(path, *args, **kwargs):
            normalized_path = os.path.realpath(path)
            if normalized_path == os.path.realpath(mount_root):
                stat_result = real_os_stat(path, *args, **kwargs)
                return SimpleNamespace(st_dev=100, st_mode=stat_result.st_mode)
            if normalized_path == os.path.realpath(quarantine_root):
                stat_result = real_os_stat(path, *args, **kwargs)
                return SimpleNamespace(st_dev=200, st_mode=stat_result.st_mode)
            return real_os_stat(path, *args, **kwargs)

        mocker.patch("xnetvn_monitord.monitors.disk_cleanup.os.stat", side_effect=fake_os_stat)

        result = quarantine_cleanup_candidates(
            [{"path": str(candidate), "type": "file", "size_bytes": candidate.stat().st_size}],
            cleanup_config,
            mount_point=str(mount_root),
            run_id="run-001",
            current_time=1_000_000,
        )

        assert result["quarantined"] == []
        assert result["errors"]
        assert candidate.exists() is True

    def test_should_move_file_into_quarantine_and_record_manifest(self, tmp_path):
        """Eligible files should be moved into quarantine and written to the run manifest."""
        mount_root = tmp_path / "mount"
        quarantine_root = tmp_path / "quarantine"
        mount_root.mkdir(parents=True)
        quarantine_root.mkdir(parents=True)
        candidate = mount_root / "candidate.log"
        candidate.write_text("payload", encoding="utf-8")

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "quarantine_dir": str(quarantine_root),
                "safety": {"require_quarantine_same_filesystem": False},
            }
        )

        result = quarantine_cleanup_candidates(
            [{"path": str(candidate), "type": "file", "size_bytes": candidate.stat().st_size}],
            cleanup_config,
            mount_point=str(mount_root),
            run_id="run-002",
            current_time=1_000_000,
        )

        assert candidate.exists() is False
        assert result["quarantined"][0]["original_path"] == str(candidate)
        assert Path(result["quarantined"][0]["quarantine_path"]).exists() is True
        assert Path(result["manifest_path"]).exists() is True

    def test_should_move_directory_into_quarantine_when_allowed(self, tmp_path):
        """Directories should be quarantined when the config allows directory cleanup."""
        mount_root = tmp_path / "mount"
        quarantine_root = tmp_path / "quarantine"
        candidate_dir = mount_root / "cache-dir"
        candidate_dir.mkdir(parents=True)
        (candidate_dir / "cached.bin").write_text("payload", encoding="utf-8")
        quarantine_root.mkdir(parents=True)

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "quarantine_dir": str(quarantine_root),
                "allow_directories": True,
                "safety": {"require_quarantine_same_filesystem": False},
            }
        )

        result = quarantine_cleanup_candidates(
            [{"path": str(candidate_dir), "type": "directory", "size_bytes": 0}],
            cleanup_config,
            mount_point=str(mount_root),
            run_id="run-003",
            current_time=1_000_000,
        )

        assert candidate_dir.exists() is False
        assert result["quarantined"][0]["item_type"] == "directory"

    def test_should_refuse_directory_quarantine_when_disallowed(self, tmp_path):
        """Directory candidates must be rejected unless explicitly enabled."""
        mount_root = tmp_path / "mount"
        quarantine_root = tmp_path / "quarantine"
        candidate_dir = mount_root / "cache-dir"
        candidate_dir.mkdir(parents=True)
        quarantine_root.mkdir(parents=True)

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "quarantine_dir": str(quarantine_root),
                "allow_directories": False,
                "safety": {"require_quarantine_same_filesystem": False},
            }
        )

        result = quarantine_cleanup_candidates(
            [{"path": str(candidate_dir), "type": "directory", "size_bytes": 0}],
            cleanup_config,
            mount_point=str(mount_root),
            run_id="run-004",
            current_time=1_000_000,
        )

        assert candidate_dir.exists() is True
        assert result["quarantined"] == []
        assert result["errors"]

    def test_should_preserve_original_path_in_manifest(self, tmp_path):
        """Manifest data should keep the exact original absolute path for restore."""
        mount_root = tmp_path / "mount"
        quarantine_root = tmp_path / "quarantine"
        mount_root.mkdir(parents=True)
        quarantine_root.mkdir(parents=True)
        candidate = mount_root / "nested" / "candidate.log"
        candidate.parent.mkdir(parents=True)
        candidate.write_text("payload", encoding="utf-8")

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "quarantine_dir": str(quarantine_root),
                "safety": {"require_quarantine_same_filesystem": False},
            }
        )

        result = quarantine_cleanup_candidates(
            [{"path": str(candidate), "type": "file", "size_bytes": candidate.stat().st_size}],
            cleanup_config,
            mount_point=str(mount_root),
            run_id="run-005",
            current_time=1_000_000,
        )

        assert result["quarantined"][0]["original_path"] == str(candidate)

    def test_should_not_fallback_to_direct_delete_when_quarantine_move_fails(self, tmp_path, mocker):
        """A failed quarantine move must not trigger any live-path deletion fallback."""
        mount_root = tmp_path / "mount"
        quarantine_root = tmp_path / "quarantine"
        mount_root.mkdir(parents=True)
        quarantine_root.mkdir(parents=True)
        candidate = mount_root / "candidate.log"
        candidate.write_text("payload", encoding="utf-8")

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "quarantine_dir": str(quarantine_root),
                "safety": {"require_quarantine_same_filesystem": False},
            }
        )
        mocker.patch("shutil.move", side_effect=OSError("move failed"))

        result = quarantine_cleanup_candidates(
            [{"path": str(candidate), "type": "file", "size_bytes": candidate.stat().st_size}],
            cleanup_config,
            mount_point=str(mount_root),
            run_id="run-006",
            current_time=1_000_000,
        )

        assert candidate.exists() is True
        assert result["quarantined"] == []
        assert result["errors"]


class TestDiskCleanupPurgeAndRestore:
    """Tests for quarantine purge retention and restore workflows."""

    def test_should_purge_only_expired_quarantine_items(self, tmp_path):
        """Purge should only delete quarantined items older than the configured retention."""
        mount_root = tmp_path / "mount"
        quarantine_root = tmp_path / "quarantine"
        mount_root.mkdir(parents=True)
        quarantine_root.mkdir(parents=True)
        old_candidate = mount_root / "old.log"
        fresh_candidate = mount_root / "fresh.log"
        old_candidate.write_text("old", encoding="utf-8")
        fresh_candidate.write_text("fresh", encoding="utf-8")

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "quarantine_dir": str(quarantine_root),
                "safety": {"require_quarantine_same_filesystem": False},
            }
        )
        old_result = quarantine_cleanup_candidates(
            [{"path": str(old_candidate), "type": "file", "size_bytes": old_candidate.stat().st_size}],
            cleanup_config,
            mount_point=str(mount_root),
            run_id="run-old",
            current_time=1_000_000,
        )
        fresh_result = quarantine_cleanup_candidates(
            [{"path": str(fresh_candidate), "type": "file", "size_bytes": fresh_candidate.stat().st_size}],
            cleanup_config,
            mount_point=str(mount_root),
            run_id="run-fresh",
            current_time=1_000_000 + 60,
        )

        purge_result = purge_quarantine_items(
            cleanup_config,
            current_time=1_000_000 + 120,
            retention_seconds=90,
            dry_run=False,
        )

        assert Path(old_result["quarantined"][0]["quarantine_path"]).exists() is False
        assert Path(fresh_result["quarantined"][0]["quarantine_path"]).exists() is True
        assert old_result["quarantined"][0]["quarantine_path"] in purge_result["deleted_paths"]
        assert fresh_result["quarantined"][0]["quarantine_path"] not in purge_result["deleted_paths"]

    def test_should_not_delete_anything_during_purge_dry_run(self, tmp_path):
        """Dry-run purge should report candidates without deleting quarantine data."""
        mount_root = tmp_path / "mount"
        quarantine_root = tmp_path / "quarantine"
        mount_root.mkdir(parents=True)
        quarantine_root.mkdir(parents=True)
        candidate = mount_root / "candidate.log"
        candidate.write_text("payload", encoding="utf-8")

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "quarantine_dir": str(quarantine_root),
                "safety": {"require_quarantine_same_filesystem": False},
            }
        )
        result = quarantine_cleanup_candidates(
            [{"path": str(candidate), "type": "file", "size_bytes": candidate.stat().st_size}],
            cleanup_config,
            mount_point=str(mount_root),
            run_id="run-dry",
            current_time=1_000_000,
        )

        purge_result = purge_quarantine_items(
            cleanup_config,
            current_time=1_000_000 + 120,
            retention_seconds=90,
            dry_run=True,
        )

        assert Path(result["quarantined"][0]["quarantine_path"]).exists() is True
        assert result["quarantined"][0]["quarantine_path"] in purge_result["eligible_paths"]
        assert purge_result["deleted_paths"] == []

    def test_should_handle_missing_quarantine_items_during_purge(self, tmp_path):
        """Purge should list missing items as eligible without failing or deleting anything else."""
        quarantine_root = tmp_path / "quarantine"
        manifest_dir = quarantine_root / "manifests"
        manifest_dir.mkdir(parents=True)
        missing_path = quarantine_root / "items" / "run-missing" / "missing.log"
        manifest_path = manifest_dir / "run-missing.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "generated_at": 1_000_000,
                    "items": [{"quarantine_path": str(missing_path)}],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        cleanup_config = normalize_cleanup_config(
            {"mode": "quarantine_then_delete", "quarantine_dir": str(quarantine_root), "safety": {}}
        )

        purge_result = purge_quarantine_items(
            cleanup_config,
            current_time=1_000_100,
            retention_seconds=60,
            dry_run=False,
        )

        assert str(missing_path) in purge_result["eligible_paths"]
        assert purge_result["deleted_paths"] == []

    def test_should_delete_quarantined_directories_during_purge(self, tmp_path):
        """Expired quarantined directories should be removed recursively."""
        quarantine_root = tmp_path / "quarantine"
        manifest_dir = quarantine_root / "manifests"
        directory_path = quarantine_root / "items" / "run-dir" / "cache-dir"
        directory_path.mkdir(parents=True)
        (directory_path / "cached.bin").write_text("payload", encoding="utf-8")
        manifest_dir.mkdir(parents=True)
        manifest_path = manifest_dir / "run-dir.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "generated_at": 1_000_000,
                    "items": [{"quarantine_path": str(directory_path)}],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        cleanup_config = normalize_cleanup_config(
            {"mode": "quarantine_then_delete", "quarantine_dir": str(quarantine_root), "safety": {}}
        )

        purge_result = purge_quarantine_items(
            cleanup_config,
            current_time=1_000_100,
            retention_seconds=60,
            dry_run=False,
        )

        assert str(directory_path) in purge_result["deleted_paths"]
        assert directory_path.exists() is False

    def test_should_report_restore_targets_during_dry_run(self, tmp_path):
        """Dry-run restore should report paths without moving files or deleting manifests."""
        mount_root = tmp_path / "mount"
        quarantine_root = tmp_path / "quarantine"
        mount_root.mkdir(parents=True)
        quarantine_root.mkdir(parents=True)
        candidate = mount_root / "candidate.log"
        candidate.write_text("payload", encoding="utf-8")
        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "quarantine_dir": str(quarantine_root),
                "safety": {"require_quarantine_same_filesystem": False},
            }
        )
        result = quarantine_cleanup_candidates(
            [{"path": str(candidate), "type": "file", "size_bytes": candidate.stat().st_size}],
            cleanup_config,
            mount_point=str(mount_root),
            run_id="run-dry-restore",
            current_time=1_000_000,
        )

        restore_result = restore_quarantine_manifest(result["manifest_path"], dry_run=True)

        assert restore_result["restored_paths"] == [str(candidate)]
        assert Path(result["quarantined"][0]["quarantine_path"]).exists() is True
        assert Path(result["manifest_path"]).exists() is True

    def test_should_report_missing_quarantine_item_during_restore(self, tmp_path):
        """Restore should report missing quarantine items without deleting the manifest."""
        quarantine_root = tmp_path / "quarantine"
        manifest_dir = quarantine_root / "manifests"
        manifest_dir.mkdir(parents=True)
        missing_path = quarantine_root / "items" / "run-missing" / "missing.log"
        original_path = tmp_path / "restored" / "candidate.log"
        manifest_path = manifest_dir / "run-missing.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "original_path": str(original_path),
                            "quarantine_path": str(missing_path),
                        }
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )

        restore_result = restore_quarantine_manifest(str(manifest_path), dry_run=False)

        assert restore_result["restored_paths"] == []
        assert restore_result["errors"]
        assert manifest_path.exists() is True

    def test_should_return_empty_restore_result_when_no_manifests_exist(self, tmp_path):
        """Directory restore should return an empty result when no manifests directory exists."""
        restore_result = restore_quarantine_directory(str(tmp_path / "quarantine"), dry_run=False)

        assert restore_result == {"restored_paths": [], "errors": []}

    def test_should_restore_quarantined_file_to_its_original_path(self, tmp_path):
        """Restore should recreate the original parent path and move the file back."""
        mount_root = tmp_path / "mount"
        quarantine_root = tmp_path / "quarantine"
        mount_root.mkdir(parents=True)
        quarantine_root.mkdir(parents=True)
        candidate = mount_root / "nested" / "candidate.log"
        candidate.parent.mkdir(parents=True)
        candidate.write_text("payload", encoding="utf-8")

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "quarantine_dir": str(quarantine_root),
                "safety": {"require_quarantine_same_filesystem": False},
            }
        )
        result = quarantine_cleanup_candidates(
            [{"path": str(candidate), "type": "file", "size_bytes": candidate.stat().st_size}],
            cleanup_config,
            mount_point=str(mount_root),
            run_id="run-restore",
            current_time=1_000_000,
        )

        restore_result = restore_quarantine_manifest(result["manifest_path"], dry_run=False)

        assert candidate.exists() is True
        assert candidate.read_text(encoding="utf-8") == "payload"
        assert Path(result["quarantined"][0]["quarantine_path"]).exists() is False
        assert restore_result["restored_paths"] == [str(candidate)]

    def test_should_refuse_restore_when_destination_already_exists(self, tmp_path):
        """Restore must fail closed when the live destination already exists."""
        mount_root = tmp_path / "mount"
        quarantine_root = tmp_path / "quarantine"
        mount_root.mkdir(parents=True)
        quarantine_root.mkdir(parents=True)
        candidate = mount_root / "candidate.log"
        candidate.write_text("payload", encoding="utf-8")

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "quarantine_dir": str(quarantine_root),
                "safety": {"require_quarantine_same_filesystem": False},
            }
        )
        result = quarantine_cleanup_candidates(
            [{"path": str(candidate), "type": "file", "size_bytes": candidate.stat().st_size}],
            cleanup_config,
            mount_point=str(mount_root),
            run_id="run-conflict",
            current_time=1_000_000,
        )
        candidate.write_text("live-conflict", encoding="utf-8")

        restore_result = restore_quarantine_manifest(result["manifest_path"], dry_run=False)

        assert candidate.read_text(encoding="utf-8") == "live-conflict"
        assert Path(result["quarantined"][0]["quarantine_path"]).exists() is True
        assert restore_result["restored_paths"] == []
        assert restore_result["errors"]

    def test_should_restore_all_manifests_from_quarantine_directory(self, tmp_path):
        """Directory restore should replay every manifest stored in the quarantine root."""
        mount_root = tmp_path / "mount"
        quarantine_root = tmp_path / "quarantine"
        mount_root.mkdir(parents=True)
        quarantine_root.mkdir(parents=True)
        first_candidate = mount_root / "first.log"
        second_candidate = mount_root / "second.log"
        first_candidate.write_text("first", encoding="utf-8")
        second_candidate.write_text("second", encoding="utf-8")

        cleanup_config = normalize_cleanup_config(
            {
                "mode": "quarantine_then_delete",
                "quarantine_dir": str(quarantine_root),
                "safety": {"require_quarantine_same_filesystem": False},
            }
        )
        quarantine_cleanup_candidates(
            [{"path": str(first_candidate), "type": "file", "size_bytes": first_candidate.stat().st_size}],
            cleanup_config,
            mount_point=str(mount_root),
            run_id="run-1",
            current_time=1_000_000,
        )
        quarantine_cleanup_candidates(
            [{"path": str(second_candidate), "type": "file", "size_bytes": second_candidate.stat().st_size}],
            cleanup_config,
            mount_point=str(mount_root),
            run_id="run-2",
            current_time=1_000_001,
        )

        restore_result = restore_quarantine_directory(str(quarantine_root), dry_run=False)

        assert first_candidate.read_text(encoding="utf-8") == "first"
        assert second_candidate.read_text(encoding="utf-8") == "second"
        assert restore_result["restored_paths"] == [str(first_candidate), str(second_candidate)]
