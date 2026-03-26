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

"""Unit tests for UpdateChecker."""

from __future__ import annotations

import json
import shutil
import tarfile
from pathlib import Path
from typing import Any

from xnetvn_monitord.utils.update_checker import (
    ReleaseInfo,
    UpdateChecker,
    UpdateCheckResult,
    compare_versions,
)


class DummyResponse:
    """Minimal response stub for open_url."""

    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "DummyResponse":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


def _build_config(state_file: Path) -> dict:
    """Build a minimal update checker configuration.

    Args:
        state_file: Path to the update checker state file.

    Returns:
        Update checker configuration dictionary.
    """
    return {
        "enabled": True,
        "interval": {"value": 1, "unit": "weeks"},
        "notify_on_update": True,
        "auto_update": False,
        "github_repo": "xnetvn-com/xnetvn_monitord",
        "github_api_base_url": "https://api.github.com",
        "state_file": str(state_file),
        "service_name": "xnetvn_monitord",
    }


class TestCompareVersions:
    """Tests for version comparison utility."""

    def test_should_detect_newer_minor_version(self) -> None:
        """Ensure newer minor versions are detected."""
        assert compare_versions("1.0.0", "1.1.0") == -1

    def test_should_compare_prerelease_versions(self) -> None:
        """Ensure prerelease ordering follows SemVer rules."""
        assert compare_versions("1.0.0-alpha.1", "1.0.0") == -1
        assert compare_versions("1.0.0", "1.0.0-alpha.1") == 1

    def test_should_return_none_for_invalid_versions(self) -> None:
        """Return None when versions are invalid."""
        assert compare_versions("invalid", "1.0.0") is None


class TestUpdateCheckerIntervals:
    """Tests for update interval handling."""

    def test_should_skip_when_interval_not_elapsed(self, tmp_path, monkeypatch) -> None:
        """Skip update checks when the interval has not elapsed."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"last_check_epoch": 1000.0}))

        checker = UpdateChecker(
            _build_config(state_file),
            current_version="1.0.0",
            install_dir=tmp_path,
        )

        monkeypatch.setattr("xnetvn_monitord.utils.update_checker.time.time", lambda: 1001.0)

        result = checker.check_for_updates()

        assert isinstance(result, UpdateCheckResult)
        assert result.checked is False
        assert result.update_available is False

    def test_should_check_when_interval_elapsed(self, tmp_path, monkeypatch) -> None:
        """Run update checks when the interval has elapsed."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"last_check_epoch": 0.0}))

        checker = UpdateChecker(
            _build_config(state_file),
            current_version="1.0.0",
            install_dir=tmp_path,
        )

        monkeypatch.setattr("xnetvn_monitord.utils.update_checker.time.time", lambda: 999999.0)
        monkeypatch.setattr(
            checker,
            "_fetch_latest_release",
            lambda: ReleaseInfo("1.0.0", "https://example.com", "https://example.com"),
        )

        result = checker.check_for_updates()

        assert result.checked is True
        assert result.update_available is False


class TestUpdateCheckerResults:
    """Tests for update check results."""

    def test_should_report_update_available(self, tmp_path, monkeypatch) -> None:
        """Report update availability when newer versions exist."""
        state_file = tmp_path / "state.json"

        checker = UpdateChecker(
            _build_config(state_file),
            current_version="1.0.0",
            install_dir=tmp_path,
        )

        monkeypatch.setattr("xnetvn_monitord.utils.update_checker.time.time", lambda: 2000.0)
        monkeypatch.setattr(
            checker,
            "_fetch_latest_release",
            lambda: ReleaseInfo("1.1.0", "https://example.com", "https://example.com"),
        )

        result = checker.check_for_updates()

        assert result.checked is True
        assert result.update_available is True
        assert result.latest_version == "1.1.0"
        assert result.release_url == "https://example.com"

    def test_should_handle_fetch_failure(self, tmp_path, monkeypatch) -> None:
        """Return a safe result when fetching release metadata fails."""
        state_file = tmp_path / "state.json"

        checker = UpdateChecker(
            _build_config(state_file),
            current_version="1.0.0",
            install_dir=tmp_path,
        )

        monkeypatch.setattr("xnetvn_monitord.utils.update_checker.time.time", lambda: 2000.0)
        monkeypatch.setattr(checker, "_fetch_latest_release", lambda: None)

        result = checker.check_for_updates()

        assert result.checked is True
        assert result.update_available is False
        assert "Failed to fetch" in result.message

    def test_should_use_proxy_config_for_update_check(self, tmp_path, monkeypatch) -> None:
        """Ensure proxy config is passed to open_url for update checks."""
        state_file = tmp_path / "state.json"
        config = _build_config(state_file)
        config["proxy"] = {"enabled": True, "uri": "http://127.0.0.1:8080"}

        checker = UpdateChecker(
            config,
            current_version="1.0.0",
            install_dir=tmp_path,
        )

        captured = {}

        def fake_open_url(request_obj, timeout, ssl_context, proxy_config, only_ipv4):
            captured["proxy_config"] = proxy_config
            return DummyResponse(
                {
                    "tag_name": "v1.0.0",
                    "tarball_url": "https://example.com/tar.gz",
                    "html_url": "https://example.com/release",
                }
            )

        monkeypatch.setattr("xnetvn_monitord.utils.update_checker.open_url", fake_open_url)

        result = checker.check_for_updates()

        assert result.checked is True
        assert captured["proxy_config"] == config["proxy"]


class TestUpdateCheckerApplyUpdate:
    """Tests for applying updates and refreshing example files."""

    def test_should_refresh_update_and_restore_scripts_and_example_files_without_overwriting_user_config(
        self, tmp_path, monkeypatch
    ) -> None:
        """Ensure Python auto-update matches manual updater for core artifacts."""
        install_dir = tmp_path / "install"
        install_dir.mkdir()

        target_dir = install_dir / "xnetvn_monitord"
        target_dir.mkdir()
        (target_dir / "old.txt").write_text("old")

        scripts_dir = install_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "update.sh").write_text("#!/usr/bin/env bash\necho old updater\n")
        (scripts_dir / "restore_quarantine.sh").write_text("#!/usr/bin/env bash\necho old restore\n")

        config_dir = install_dir / "config"
        config_dir.mkdir()
        (config_dir / "main.yaml").write_text("user-config")
        (config_dir / ".env").write_text("SECRET=1")
        (config_dir / "main.example.yaml").write_text("old example")
        (config_dir / ".env.example").write_text("old env")

        package_root = tmp_path / "package" / "xnetvn_monitord-1.1.0"
        source_dir = package_root / "src" / "xnetvn_monitord"
        source_dir.mkdir(parents=True)
        (source_dir / "new.txt").write_text("new")

        release_scripts = package_root / "scripts"
        release_scripts.mkdir(parents=True)
        (release_scripts / "update.sh").write_text("#!/usr/bin/env bash\necho new updater\n")
        (release_scripts / "restore_quarantine.sh").write_text("#!/usr/bin/env bash\necho new restore\n")

        release_config = package_root / "config"
        release_config.mkdir(parents=True)
        (release_config / "main.example.yaml").write_text("new example")
        (release_config / ".env.example").write_text("new env")

        tarball_path = tmp_path / "release.tar.gz"
        with tarfile.open(tarball_path, "w:gz") as tar_handle:
            tar_handle.add(package_root, arcname=package_root.name)

        def _fake_download(
            url: str,
            target_path: str,
            timeout: int,
            proxy_config: dict,
            only_ipv4: bool,
        ) -> None:
            shutil.copy(tarball_path, target_path)

        monkeypatch.setattr(
            "xnetvn_monitord.utils.update_checker.download_url_to_file",
            _fake_download,
        )

        state_file = tmp_path / "state.json"
        checker = UpdateChecker(
            _build_config(state_file),
            current_version="1.0.0",
            install_dir=install_dir,
        )

        assert checker.apply_update("https://example.com/release.tar.gz") is True
        assert (install_dir / "xnetvn_monitord" / "new.txt").read_text() == "new"
        assert (scripts_dir / "update.sh").read_text() == "#!/usr/bin/env bash\necho new updater\n"
        assert (scripts_dir / "restore_quarantine.sh").read_text() == "#!/usr/bin/env bash\necho new restore\n"
        assert (config_dir / "main.example.yaml").read_text() == "new example"
        assert (config_dir / ".env.example").read_text() == "new env"
        assert (config_dir / "main.yaml").read_text() == "user-config"
        assert (config_dir / ".env").read_text() == "SECRET=1"
