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

"""Focused integration tests for debug observability call sites."""

from __future__ import annotations

from xnetvn_monitord.daemon import MonitorDaemon
from xnetvn_monitord.monitors.resource_monitor import ResourceMonitor
from xnetvn_monitord.monitors.service_monitor import ServiceMonitor
from xnetvn_monitord.utils.update_checker import UpdateChecker


def _minimal_daemon_config(tmp_path, *, level: str = "DEBUG", deep_debug: bool = False) -> dict:
    return {
        "general": {
            "check_interval": 1,
            "pid_file": str(tmp_path / "xnetvn.pid"),
            "work_dir": str(tmp_path),
            "logging": {
                "enabled": True,
                "level": level,
                "deep_debug": deep_debug,
                "file": str(tmp_path / "monitor.log"),
                "deep_debug_file": str(tmp_path / "deep-debug.log"),
            },
        },
        "service_monitor": {"enabled": True, "services": []},
        "resource_monitor": {"enabled": True},
        "notifications": {"enabled": False},
    }


def test_should_capture_startup_host_state_only_when_deep_debug_enabled(mocker, tmp_path) -> None:
    """Daemon should only trigger startup host sweep in DEBUG+deep_debug mode."""
    config = _minimal_daemon_config(tmp_path, deep_debug=True)
    observability = mocker.Mock()

    mocker.patch("xnetvn_monitord.daemon.ConfigLoader.load", return_value=config)
    mocker.patch("xnetvn_monitord.daemon.ServiceMonitor")
    mocker.patch("xnetvn_monitord.daemon.ResourceMonitor")
    manager_mock = mocker.patch("xnetvn_monitord.daemon.NotificationManager")
    manager_mock.return_value.get_enabled_channels.return_value = []
    mocker.patch("xnetvn_monitord.daemon.configure_debug_observability", return_value=observability)
    mocker.patch("xnetvn_monitord.daemon.logging.handlers.RotatingFileHandler")
    mocker.patch("xnetvn_monitord.daemon.logging.StreamHandler")
    mocker.patch("os.makedirs")

    daemon = MonitorDaemon("/tmp/config.yaml")
    mocker.patch.object(daemon, "_create_pid_file")

    daemon.initialize()

    observability.capture_startup_host_state.assert_called_once()


def test_should_skip_startup_host_state_when_deep_debug_disabled(mocker, tmp_path) -> None:
    """Daemon must not trigger host sweep for plain DEBUG mode."""
    config = _minimal_daemon_config(tmp_path, deep_debug=False)
    observability = mocker.Mock()

    mocker.patch("xnetvn_monitord.daemon.ConfigLoader.load", return_value=config)
    mocker.patch("xnetvn_monitord.daemon.ServiceMonitor")
    mocker.patch("xnetvn_monitord.daemon.ResourceMonitor")
    manager_mock = mocker.patch("xnetvn_monitord.daemon.NotificationManager")
    manager_mock.return_value.get_enabled_channels.return_value = []
    mocker.patch("xnetvn_monitord.daemon.configure_debug_observability", return_value=observability)
    mocker.patch("xnetvn_monitord.daemon.logging.handlers.RotatingFileHandler")
    mocker.patch("xnetvn_monitord.daemon.logging.StreamHandler")
    mocker.patch("os.makedirs")

    daemon = MonitorDaemon("/tmp/config.yaml")
    mocker.patch.object(daemon, "_create_pid_file")

    daemon.initialize()

    observability.capture_startup_host_state.assert_not_called()


def test_should_emit_debug_command_preview_for_custom_service_checks(mocker) -> None:
    """Custom service checks should emit stdout/stderr previews in DEBUG mode."""
    observability = mocker.Mock()
    mocker.patch("xnetvn_monitord.monitors.service_monitor.get_debug_observability", return_value=observability)
    mocker.patch(
        "subprocess.run",
        return_value=mocker.Mock(returncode=1, stdout="stdout preview", stderr="stderr preview"),
    )

    monitor = ServiceMonitor({"enabled": True})
    result = monitor._check_custom_command(
        {
            "name": "custom",
            "check_method": "custom_command",
            "check_command": "echo health-check",
            "check_timeout": 5,
        }
    )

    assert result is False
    observability.emit_command_result.assert_called_once()


def test_should_emit_debug_restart_preview_for_resource_recovery(mocker) -> None:
    """Resource recovery restarts should emit stdout/stderr previews in DEBUG mode."""
    observability = mocker.Mock()
    mocker.patch("xnetvn_monitord.monitors.resource_monitor.get_debug_observability", return_value=observability)

    monitor = ResourceMonitor({"enabled": True})
    monitor.service_manager = mocker.Mock()
    monitor.service_manager.restart_service.return_value = {
        "success": True,
        "stdout": "restart ok",
        "stderr": "",
        "command": "systemctl restart nginx",
        "returncode": 0,
    }

    results = monitor._restart_services(["nginx"], {"restart_interval": 0})

    assert results[0]["success"] is True
    observability.emit_command_result.assert_called_once()


def test_should_emit_debug_http_metadata_for_update_checks(mocker, tmp_path) -> None:
    """Update checks should emit request/response previews in DEBUG mode."""
    observability = mocker.Mock()
    mocker.patch("xnetvn_monitord.utils.update_checker.get_debug_observability", return_value=observability)
    mocker.patch(
        "xnetvn_monitord.utils.update_checker.open_url",
        return_value=mocker.MagicMock(
            __enter__=lambda self: self,
            __exit__=lambda self, exc_type, exc, tb: False,
            read=lambda: (
                b'{"tag_name":"v1.5.1","tarball_url":"https://example.com/tar.gz",'
                b'"html_url":"https://example.com/release"}'
            ),
        ),
    )

    checker = UpdateChecker(
        {
            "enabled": True,
            "interval": {"value": 1, "unit": "weeks"},
            "github_repo": "xnetvn-com/xnetvn_monitord",
            "github_api_base_url": "https://api.github.com",
            "state_file": str(tmp_path / "state.json"),
        },
        current_version="1.5.0",
        install_dir=tmp_path,
    )

    release = checker._fetch_latest_release()

    assert release is not None
    observability.emit_http_exchange.assert_called_once()
