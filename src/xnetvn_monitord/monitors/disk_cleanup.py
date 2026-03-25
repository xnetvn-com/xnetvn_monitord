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

"""Disk cleanup configuration helpers.

This module starts with normalization and validation primitives used by the
future quarantine-based disk cleanup engine.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import time
from copy import deepcopy
from typing import Any, Dict, List, Optional

SUPPORTED_SELECTOR_TYPES = {"exact", "regex", "glob"}

DEFAULT_PROTECTED_PATHS = (
    "/",
    "/boot",
    "/dev",
    "/etc",
    "/proc",
    "/run",
    "/snap",
    "/sys",
    "/usr",
    "/var/lib",
    "/var/lib/dpkg",
    "/var/lib/systemd",
    "/var/log/journal",
)


def normalize_cleanup_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize cleanup configuration and validate selector inputs.

    Args:
        config: Cleanup configuration fragment from the disk monitor settings.

    Returns:
        A normalized configuration dictionary with merged default safety rules.

    Raises:
        ValueError: If the cleanup mode, selector type, or selector regex is invalid.
    """
    normalized = deepcopy(config)
    mode = normalized.get("mode", "quarantine_then_delete")
    if mode != "quarantine_then_delete":
        raise ValueError("Unsupported cleanup mode: %s" % mode)

    selectors = normalized.setdefault("selectors", {})
    selectors["include"] = _normalize_selectors(selectors.get("include", []))
    selectors["exclude"] = _normalize_selectors(selectors.get("exclude", []))
    normalized.setdefault("allow_directories", False)

    safety = normalized.setdefault("safety", {})
    configured_paths = safety.get("protected_paths", []) or []
    merged_paths = list(dict.fromkeys([*DEFAULT_PROTECTED_PATHS, *configured_paths]))
    safety["protected_paths"] = merged_paths
    safety.setdefault("require_quarantine_same_filesystem", True)

    return normalized


def _normalize_selectors(selectors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate selector definitions and normalize supported selector items."""
    normalized_selectors: List[Dict[str, Any]] = []

    for selector in selectors:
        selector_type = selector.get("type")
        pattern = selector.get("pattern")

        if selector_type not in SUPPORTED_SELECTOR_TYPES:
            raise ValueError("Unsupported selector type: %s" % selector_type)
        if not isinstance(pattern, str) or not pattern:
            raise ValueError("Selector pattern must be a non-empty string")

        if selector_type == "regex":
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError("Invalid regex selector: %s" % pattern) from exc

        normalized_selectors.append({"type": selector_type, "pattern": pattern})

    return normalized_selectors


def path_matches_selector(path: str, selector: Dict[str, str]) -> bool:
    """Check whether an absolute path matches a selector definition."""
    normalized_path = os.path.normpath(path)
    selector_type = selector["type"]
    pattern = selector["pattern"]

    if selector_type == "exact":
        return normalized_path == os.path.normpath(pattern)
    if selector_type == "regex":
        return re.search(pattern, normalized_path) is not None
    if selector_type == "glob":
        normalized_pattern = os.path.normpath(pattern)
        if fnmatch.fnmatchcase(normalized_path, normalized_pattern):
            return True
        if normalized_pattern.endswith(f"{os.sep}**"):
            recursive_root = normalized_pattern[: -(len(os.sep) + 2)]
            return normalized_path == recursive_root or normalized_path.startswith(f"{recursive_root}{os.sep}")
        return False

    raise ValueError("Unsupported selector type: %s" % selector_type)


def scan_cleanup_candidates(
    mount_point: str,
    cleanup_config: Dict[str, Any],
    current_time: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Stream cleanup candidates for a mount point with conservative safety checks."""
    normalized_mount_point = os.path.realpath(mount_point)
    now = time.time() if current_time is None else current_time
    selectors = cleanup_config.get("selectors", {})
    include_selectors = selectors.get("include", [])
    exclude_selectors = selectors.get("exclude", [])
    safety = cleanup_config.get("safety", {})
    protected_paths = {os.path.realpath(path) for path in safety.get("protected_paths", [])}
    rules = cleanup_config.get("rules", {})
    file_types = set(rules.get("file_types", ["file", "directory"]))
    min_age_days = float(rules.get("min_age_days", 0) or 0)
    min_size_mb = float(rules.get("min_size_mb", 0) or 0)
    min_age_seconds = min_age_days * 24 * 60 * 60
    min_size_bytes = min_size_mb * 1024 * 1024
    max_items = int(cleanup_config.get("max_items_per_run", 500) or 500)
    max_runtime_seconds = float(cleanup_config.get("max_runtime_seconds", 120) or 120)

    candidates: List[Dict[str, Any]] = []
    deadline = now + max_runtime_seconds
    directory_stack = [normalized_mount_point]

    while directory_stack and len(candidates) < max_items and now <= deadline:
        current_dir = directory_stack.pop()
        if _is_protected_path(current_dir, protected_paths):
            continue

        with os.scandir(current_dir) as entries:
            for entry in entries:
                entry_path = os.path.realpath(entry.path)
                if not _is_within_mount_boundary(entry_path, normalized_mount_point):
                    continue
                if entry.is_symlink():
                    continue
                if _is_protected_path(entry_path, protected_paths):
                    continue
                if _matches_any_selector(entry_path, exclude_selectors):
                    continue

                is_dir = entry.is_dir(follow_symlinks=False)
                if is_dir:
                    directory_stack.append(entry_path)

                if not _matches_any_selector(entry_path, include_selectors):
                    continue

                stat_result = entry.stat(follow_symlinks=False)
                age_seconds = max(0.0, now - stat_result.st_mtime)
                if age_seconds < min_age_seconds:
                    continue
                if stat_result.st_size < min_size_bytes:
                    continue

                if is_dir and "directory" not in file_types:
                    continue
                if not is_dir and "file" not in file_types:
                    continue

                candidates.append(
                    {
                        "path": entry_path,
                        "type": "directory" if is_dir else "file",
                        "size_bytes": stat_result.st_size,
                    }
                )
                if len(candidates) >= max_items:
                    break

    return candidates


def quarantine_cleanup_candidates(
    candidates: List[Dict[str, Any]],
    cleanup_config: Dict[str, Any],
    mount_point: str,
    run_id: str,
    current_time: Optional[float] = None,
) -> Dict[str, Any]:
    """Move candidates into quarantine and write a restore manifest for the run."""
    now = time.time() if current_time is None else current_time
    quarantine_root = os.path.realpath(cleanup_config["quarantine_dir"])
    normalized_mount_point = os.path.realpath(mount_point)
    errors: List[Dict[str, str]] = []
    quarantined: List[Dict[str, Any]] = []
    manifest_path = os.path.join(quarantine_root, "manifests", f"{run_id}.json")

    os.makedirs(quarantine_root, exist_ok=True)

    if cleanup_config.get("safety", {}).get("require_quarantine_same_filesystem", True):
        mount_stat = os.stat(normalized_mount_point)
        quarantine_stat = os.stat(quarantine_root)
        if mount_stat.st_dev != quarantine_stat.st_dev:
            return {
                "quarantined": [],
                "errors": [
                    {
                        "path": normalized_mount_point,
                        "reason": "Quarantine directory must reside on the same filesystem as the cleanup target",
                    }
                ],
                "manifest_path": manifest_path,
            }

    items_root = os.path.join(quarantine_root, "items", run_id)
    os.makedirs(items_root, exist_ok=True)

    for index, candidate in enumerate(candidates, start=1):
        source_path = os.path.realpath(candidate["path"])
        item_type = candidate.get("type", "file")

        if item_type == "directory" and not cleanup_config.get("allow_directories", False):
            errors.append({"path": source_path, "reason": "Directory cleanup is disabled"})
            continue

        destination_name = f"{index:06d}_{os.path.basename(source_path) or 'item'}"
        destination_path = os.path.join(items_root, destination_name)

        try:
            shutil.move(source_path, destination_path)
        except OSError as exc:
            errors.append({"path": source_path, "reason": str(exc)})
            continue

        quarantined.append(
            {
                "item_id": destination_name,
                "original_path": source_path,
                "quarantine_path": destination_path,
                "item_type": item_type,
                "size_bytes": int(candidate.get("size_bytes", 0) or 0),
                "quarantined_at": now,
            }
        )

    if quarantined:
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        manifest_payload = {
            "run_id": run_id,
            "mount_point": normalized_mount_point,
            "quarantine_dir": quarantine_root,
            "generated_at": now,
            "items": quarantined,
        }
        with open(manifest_path, "w", encoding="utf-8") as manifest_file:
            json.dump(manifest_payload, manifest_file, indent=2, sort_keys=True)
            manifest_file.write("\n")

    return {"quarantined": quarantined, "errors": errors, "manifest_path": manifest_path}


def purge_quarantine_items(
    cleanup_config: Dict[str, Any],
    current_time: Optional[float] = None,
    retention_seconds: int = 0,
    dry_run: bool = False,
) -> Dict[str, List[str]]:
    """Delete expired quarantined items referenced by run manifests."""
    now = time.time() if current_time is None else current_time
    quarantine_root = os.path.realpath(cleanup_config["quarantine_dir"])
    manifests_dir = os.path.join(quarantine_root, "manifests")
    deleted_paths: List[str] = []
    eligible_paths: List[str] = []

    if not os.path.isdir(manifests_dir):
        return {"eligible_paths": [], "deleted_paths": []}

    for entry in sorted(os.scandir(manifests_dir), key=lambda item: item.name):
        if not entry.is_file() or not entry.name.endswith(".json"):
            continue

        with open(entry.path, "r", encoding="utf-8") as manifest_file:
            manifest_payload = json.load(manifest_file)

        generated_at = float(manifest_payload.get("generated_at", 0) or 0)
        if now - generated_at < retention_seconds:
            continue

        manifest_deleted_paths: List[str] = []
        for item in manifest_payload.get("items", []):
            quarantine_path = os.path.realpath(item["quarantine_path"])
            if not _is_within_mount_boundary(quarantine_path, quarantine_root):
                continue
            eligible_paths.append(quarantine_path)
            if dry_run or not os.path.exists(quarantine_path):
                continue

            if os.path.isdir(quarantine_path):
                shutil.rmtree(quarantine_path)
            else:
                os.remove(quarantine_path)
            deleted_paths.append(quarantine_path)
            manifest_deleted_paths.append(quarantine_path)

        if not dry_run and manifest_deleted_paths:
            os.remove(entry.path)

    return {"eligible_paths": eligible_paths, "deleted_paths": deleted_paths}


def restore_quarantine_manifest(manifest_path: str, dry_run: bool = False) -> Dict[str, Any]:
    """Restore quarantined items from a run manifest back to their original paths."""
    restored_paths: List[str] = []
    errors: List[Dict[str, str]] = []

    with open(manifest_path, "r", encoding="utf-8") as manifest_file:
        manifest_payload = json.load(manifest_file)

    for item in manifest_payload.get("items", []):
        original_path = item["original_path"]
        quarantine_path = item["quarantine_path"]

        if os.path.exists(original_path):
            errors.append({"path": original_path, "reason": "Destination already exists"})
            continue
        if not os.path.exists(quarantine_path):
            errors.append({"path": quarantine_path, "reason": "Quarantine item is missing"})
            continue

        if dry_run:
            restored_paths.append(original_path)
            continue

        os.makedirs(os.path.dirname(original_path), exist_ok=True)
        shutil.move(quarantine_path, original_path)
        restored_paths.append(original_path)

    if not dry_run and restored_paths and not errors:
        os.remove(manifest_path)

    return {"restored_paths": restored_paths, "errors": errors}


def restore_quarantine_directory(quarantine_dir: str, dry_run: bool = False) -> Dict[str, Any]:
    """Restore every manifest currently stored under a quarantine directory."""
    manifests_dir = os.path.join(os.path.realpath(quarantine_dir), "manifests")
    restored_paths: List[str] = []
    errors: List[Dict[str, str]] = []

    if not os.path.isdir(manifests_dir):
        return {"restored_paths": [], "errors": []}

    for entry in sorted(os.scandir(manifests_dir), key=lambda item: item.name):
        if not entry.is_file() or not entry.name.endswith(".json"):
            continue

        result = restore_quarantine_manifest(entry.path, dry_run=dry_run)
        restored_paths.extend(result.get("restored_paths", []))
        errors.extend(result.get("errors", []))

    return {"restored_paths": restored_paths, "errors": errors}


def _matches_any_selector(path: str, selectors: List[Dict[str, str]]) -> bool:
    """Return True when the path matches any selector in the list."""
    if not selectors:
        return False
    return any(path_matches_selector(path, selector) for selector in selectors)


def _is_protected_path(path: str, protected_paths: set[str]) -> bool:
    """Return True when a path is equal to or nested under a protected path."""
    for protected in protected_paths:
        if path == protected:
            return True
        if protected == os.sep:
            continue
        if path.startswith(f"{protected}{os.sep}"):
            return True
    return False


def _is_within_mount_boundary(path: str, mount_point: str) -> bool:
    """Return True when a path is equal to or nested under the target mount point."""
    return path == mount_point or path.startswith(f"{mount_point}{os.sep}")
