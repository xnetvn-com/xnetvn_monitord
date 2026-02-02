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

"""Update checker utilities for GitHub Releases."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tarfile
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib import error, request

from .service_manager import ServiceManager

logger = logging.getLogger(__name__)

_VERSION_PATTERN = re.compile(
    r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$"
)


@dataclass(frozen=True)
class ReleaseInfo:
    """Release metadata from GitHub."""

    version: str
    tarball_url: str
    html_url: str


@dataclass(frozen=True)
class UpdateCheckResult:
    """Result of an update check."""

    checked: bool
    update_available: bool
    current_version: str
    latest_version: Optional[str]
    release_url: Optional[str]
    tarball_url: Optional[str]
    message: str


def _parse_version(version: str) -> Optional[Tuple[int, int, int, List[str]]]:
    """Parse a semantic version string.

    Args:
        version: Version string, optionally prefixed with "v".

    Returns:
        Parsed version components or None when invalid.
    """
    match = _VERSION_PATTERN.match(version.strip())
    if not match:
        return None
    major, minor, patch, prerelease = match.groups()
    pre_parts = prerelease.split(".") if prerelease else []
    return int(major), int(minor), int(patch), pre_parts


def _compare_prerelease(left: List[str], right: List[str]) -> int:
    """Compare prerelease identifiers following SemVer rules.

    Args:
        left: Left prerelease identifiers.
        right: Right prerelease identifiers.

    Returns:
        -1 if left < right, 0 if equal, 1 if left > right.
    """
    for left_part, right_part in zip(left, right):
        left_is_num = left_part.isdigit()
        right_is_num = right_part.isdigit()

        if left_is_num and right_is_num:
            left_val = int(left_part)
            right_val = int(right_part)
            if left_val != right_val:
                return -1 if left_val < right_val else 1
        elif left_is_num != right_is_num:
            return -1 if left_is_num else 1
        else:
            if left_part != right_part:
                return -1 if left_part < right_part else 1

    if len(left) != len(right):
        return -1 if len(left) < len(right) else 1
    return 0


def compare_versions(current: str, latest: str) -> Optional[int]:
    """Compare two semantic versions.

    Args:
        current: Current version string.
        latest: Latest version string.

    Returns:
        -1 if current < latest, 0 if equal, 1 if current > latest,
        None if either version is invalid.
    """
    current_parsed = _parse_version(current)
    latest_parsed = _parse_version(latest)
    if not current_parsed or not latest_parsed:
        return None

    current_core = current_parsed[:3]
    latest_core = latest_parsed[:3]
    if current_core != latest_core:
        return -1 if current_core < latest_core else 1

    current_pre = current_parsed[3]
    latest_pre = latest_parsed[3]
    if not current_pre and not latest_pre:
        return 0
    if not current_pre:
        return 1
    if not latest_pre:
        return -1
    return _compare_prerelease(current_pre, latest_pre)


class UpdateChecker:
    """Check for updates and optionally apply them."""

    def __init__(
        self,
        config: Dict,
        current_version: str,
        install_dir: Path,
    ) -> None:
        """Initialize the update checker.

        Args:
            config: Update checker configuration.
            current_version: Current running version.
            install_dir: Install directory of the daemon.
        """
        self.config = config
        self.current_version = current_version
        self.github_repo = config.get("github_repo", "xnetvn-com/xnetvn_monitord")
        self.github_api_base_url = config.get(
            "github_api_base_url",
            "https://api.github.com",
        )
        state_file = config.get(
            "state_file",
            str(install_dir / ".local" / "tmp" / "update_check.json"),
        )
        self.state_file = Path(state_file)
        self.install_dir = install_dir
        self._interval_seconds = self._get_interval_seconds()
        self._state_cache: Optional[Dict[str, float]] = None

    def _get_interval_seconds(self) -> int:
        """Return interval in seconds based on configuration."""
        interval_config = self.config.get("interval", {})
        value = int(interval_config.get("value", 1))
        unit = str(interval_config.get("unit", "weeks")).lower()
        multiplier = {
            "hours": 3600,
            "days": 86400,
            "weeks": 604800,
        }.get(unit, 604800)
        if unit not in {"hours", "days", "weeks"}:
            logger.warning("Unsupported update interval unit: %s", unit)
        return max(1, value) * multiplier

    def _load_state(self) -> Dict[str, float]:
        """Load last update check state."""
        if not self.state_file.exists():
            return {}
        try:
            with self.state_file.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return data
        except Exception as exc:
            logger.warning("Failed to load update state: %s", exc)
        return {}

    def _save_state(self, last_check: float) -> None:
        """Persist update check state."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {"last_check_epoch": last_check}
            with self.state_file.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle)
            self._state_cache = payload
        except Exception as exc:
            logger.warning("Failed to save update state: %s", exc)

    def _load_state_cached(self) -> Dict[str, float]:
        """Return cached state or load it from disk once."""
        if self._state_cache is not None:
            return self._state_cache
        self._state_cache = self._load_state()
        return self._state_cache

    def should_check(self) -> bool:
        """Return True if update check interval has elapsed."""
        state = self._load_state_cached()
        last_check = state.get("last_check_epoch", 0)
        return (time.time() - float(last_check)) >= self._interval_seconds

    def _fetch_latest_release(self) -> Optional[ReleaseInfo]:
        """Fetch latest GitHub release metadata."""
        url = f"{self.github_api_base_url}/repos/{self.github_repo}/releases/latest"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "xnetvn_monitord-update-checker",
        }
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = request.Request(url, headers=headers)
        try:
            with request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            logger.error("GitHub release check failed: %s", exc)
            return None
        except error.URLError as exc:
            logger.error("GitHub release check failed: %s", exc)
            return None
        except Exception as exc:
            logger.error("Failed to parse GitHub response: %s", exc)
            return None

        tag_name = str(data.get("tag_name", "")).strip()
        tarball_url = str(data.get("tarball_url", "")).strip()
        html_url = str(data.get("html_url", "")).strip()
        if not tag_name or not tarball_url:
            logger.warning("GitHub release response missing tag or tarball URL")
            return None
        return ReleaseInfo(tag_name, tarball_url, html_url)

    def check_for_updates(self) -> UpdateCheckResult:
        """Check for available updates from GitHub Releases."""
        if not self.should_check():
            return UpdateCheckResult(
                checked=False,
                update_available=False,
                current_version=self.current_version,
                latest_version=None,
                release_url=None,
                tarball_url=None,
                message="Update interval has not elapsed",
            )

        release = self._fetch_latest_release()
        now = time.time()
        if not release:
            return UpdateCheckResult(
                checked=True,
                update_available=False,
                current_version=self.current_version,
                latest_version=None,
                release_url=None,
                tarball_url=None,
                message="Failed to fetch release metadata",
            )

        comparison = compare_versions(self.current_version, release.version)
        if comparison is None:
            message = "Unable to compare versions"
            logger.warning(message)
            return UpdateCheckResult(
                checked=True,
                update_available=False,
                current_version=self.current_version,
                latest_version=release.version,
                release_url=release.html_url,
                tarball_url=release.tarball_url,
                message=message,
            )

        update_available = comparison == -1
        message = (
            "New version available"
            if update_available
            else "Already on latest version"
        )
        self._save_state(now)

        return UpdateCheckResult(
            checked=True,
            update_available=update_available,
            current_version=self.current_version,
            latest_version=release.version,
            release_url=release.html_url,
            tarball_url=release.tarball_url,
            message=message,
        )

    def apply_update(self, tarball_url: str) -> bool:
        """Download and apply update from GitHub tarball.

        Args:
            tarball_url: URL of the tarball to download.

        Returns:
            True if update applied successfully.
        """
        target_dir = self.install_dir / "xnetvn_monitord"
        if not target_dir.exists():
            logger.error("Target install directory not found: %s", target_dir)
            return False

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                tarball_path = Path(temp_dir) / "release.tar.gz"
                request.urlretrieve(tarball_url, tarball_path)

                with tarfile.open(tarball_path, "r:gz") as tar_handle:
                    tar_handle.extractall(path=temp_dir)

                extracted_dirs = [
                    path
                    for path in Path(temp_dir).iterdir()
                    if path.is_dir()
                ]
                if not extracted_dirs:
                    logger.error("No extracted release directory found")
                    return False

                release_root = extracted_dirs[0]
                source_dir = release_root / "src" / "xnetvn_monitord"
                if not source_dir.exists():
                    logger.error("Release source directory not found: %s", source_dir)
                    return False

                backup_dir = (
                    self.install_dir
                    / ".local"
                    / "backups"
                    / f"xnetvn_monitord_{int(time.time())}"
                )
                backup_dir.parent.mkdir(parents=True, exist_ok=True)
                if target_dir.exists():
                    shutil.copytree(target_dir, backup_dir)

                shutil.rmtree(target_dir)
                shutil.copytree(source_dir, target_dir)

                config_dir = self.install_dir / "config"
                config_dir.mkdir(parents=True, exist_ok=True)
                release_config_dir = release_root / "config"
                if release_config_dir.exists():
                    example_config = release_config_dir / "main.example.yaml"
                    if example_config.exists():
                        shutil.copy2(example_config, config_dir / "main.example.yaml")
                    else:
                        logger.warning("Release missing main.example.yaml")

                    env_example = release_config_dir / ".env.example"
                    if env_example.exists():
                        shutil.copy2(env_example, config_dir / ".env.example")
                    else:
                        logger.warning("Release missing .env.example")
                else:
                    logger.warning("Release missing config directory")
        except Exception as exc:
            logger.error("Failed to apply update: %s", exc)
            return False

        logger.info("Update applied successfully")
        return True

    def restart_service(self, service_name: str) -> bool:
        """Restart daemon service after update.

        Args:
            service_name: Name of the service to restart.

        Returns:
            True if restart command succeeded.
        """
        manager_override = os.environ.get("XNETVN_SERVICE_MANAGER")
        manager = ServiceManager(manager_override)
        result = manager.restart_service(service_name)
        if result.get("success"):
            logger.info("Service restarted: %s", service_name)
            return True
        logger.error("Failed to restart service: %s", result.get("stderr"))
        return False