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

"""Unit tests for ResourceMonitor.

This module contains comprehensive unit tests for system resource
monitoring functionality.
"""

import subprocess
import time

import pytest

from xnetvn_monitord.monitors.resource_monitor import ResourceMonitor


class TestResourceMonitorInitialization:
    """Tests for ResourceMonitor initialization."""

    def test_should_initialize_with_config(self):
        """Test successful initialization with configuration."""
        config = {"enabled": True}
        monitor = ResourceMonitor(config)

        assert monitor.config == config
        assert monitor.enabled is True
        assert isinstance(monitor.last_action_time, dict)

    def test_should_default_to_enabled(self):
        """Test that monitor defaults to enabled."""
        config = {}
        monitor = ResourceMonitor(config)

        assert monitor.enabled is True


class TestResourceMonitorCPUCheck:
    """Tests for CPU load monitoring."""

    def test_should_detect_high_cpu_1min_load(self, mocker):
        """Test detection of high 1-minute CPU load."""
        mocker.patch("os.getloadavg", return_value=(15.0, 10.0, 8.0))

        config = {
            "enabled": True,
            "cpu_load": {
                "enabled": True,
                "check_1min": True,
                "threshold_1min": 10.0,
            },
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_cpu_load(config["cpu_load"])

        assert result["threshold_exceeded"] is True
        assert result["exceeded_type"] == "1min"
        assert result["load_1min"] == 15.0

    def test_should_detect_high_cpu_5min_load(self, mocker):
        """Test detection of high 5-minute CPU load."""
        mocker.patch("os.getloadavg", return_value=(5.0, 12.0, 8.0))

        config = {
            "enabled": True,
            "cpu_load": {
                "enabled": True,
                "check_5min": True,
                "threshold_5min": 10.0,
            },
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_cpu_load(config["cpu_load"])

        assert result["threshold_exceeded"] is True
        assert result["exceeded_type"] == "5min"

    def test_should_not_trigger_below_threshold(self, mocker):
        """Test that alert is not triggered below threshold."""
        mocker.patch("os.getloadavg", return_value=(5.0, 4.0, 3.0))

        config = {
            "enabled": True,
            "cpu_load": {
                "enabled": True,
                "check_1min": True,
                "threshold_1min": 10.0,
            },
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_cpu_load(config["cpu_load"])

        assert result["threshold_exceeded"] is False

    def test_should_return_all_load_averages(self, mocker):
        """Test that all load averages are returned."""
        mocker.patch("os.getloadavg", return_value=(1.5, 2.0, 2.5))

        config = {
            "enabled": True,
            "cpu_load": {"enabled": True},
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_cpu_load(config["cpu_load"])

        assert result["load_1min"] == 1.5
        assert result["load_5min"] == 2.0
        assert result["load_15min"] == 2.5

    def test_should_detect_high_cpu_15min_load(self, mocker):
        """Test detection of high 15-minute CPU load."""
        mocker.patch("os.getloadavg", return_value=(1.0, 2.0, 12.0))

        config = {
            "enabled": True,
            "cpu_load": {
                "enabled": True,
                "check_15min": True,
                "threshold_15min": 10.0,
            },
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_cpu_load(config["cpu_load"])

        assert result["threshold_exceeded"] is True
        assert result["exceeded_type"] == "15min"

    def test_should_return_error_when_getloadavg_fails(self, mocker):
        """Test CPU load check handles errors."""
        mocker.patch("os.getloadavg", side_effect=OSError("load error"))

        monitor = ResourceMonitor({"enabled": True})
        result = monitor._check_cpu_load({"enabled": True})

        assert result["threshold_exceeded"] is False
        assert result["error"] == "load error"


class TestResourceMonitorMemoryCheck:
    """Tests for memory monitoring."""

    def test_should_detect_low_memory_percentage(self, mocker):
        """Test detection of low memory percentage."""
        mock_mem = mocker.MagicMock()
        mock_mem.total = 8 * 1024 * 1024 * 1024  # 8 GB
        mock_mem.available = 200 * 1024 * 1024  # 200 MB (2.5%)
        mock_mem.percent = 97.5
        mocker.patch("psutil.virtual_memory", return_value=mock_mem)

        config = {
            "enabled": True,
            "memory": {
                "enabled": True,
                "free_percent_threshold": 5.0,
                "condition": "or",
            },
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_memory(config["memory"])

        assert result["threshold_exceeded"] is True
        # exceeded_type can be "percent" or "both" depending on MB threshold
        assert result["exceeded_type"] in ["percent", "both"]

    def test_should_detect_low_memory_megabytes(self, mocker):
        """Test detection of low memory in megabytes."""
        mock_mem = mocker.MagicMock()
        mock_mem.total = 8 * 1024 * 1024 * 1024  # 8 GB
        mock_mem.available = 256 * 1024 * 1024  # 256 MB
        mock_mem.percent = 95.0
        mocker.patch("psutil.virtual_memory", return_value=mock_mem)

        config = {
            "enabled": True,
            "memory": {
                "enabled": True,
                "free_mb_threshold": 512,
                "condition": "or",
            },
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_memory(config["memory"])

        assert result["threshold_exceeded"] is True
        assert result["available_mb"] < 512

    def test_should_use_or_condition_for_thresholds(self, mocker):
        """Test OR condition for memory thresholds."""
        mock_mem = mocker.MagicMock()
        mock_mem.total = 8 * 1024 * 1024 * 1024
        mock_mem.available = 400 * 1024 * 1024  # 400 MB (~5%)
        mock_mem.percent = 95.0
        mocker.patch("psutil.virtual_memory", return_value=mock_mem)

        config = {
            "enabled": True,
            "memory": {
                "enabled": True,
                "free_percent_threshold": 10.0,  # Not met (5% < 10%)
                "free_mb_threshold": 512,  # Not met (400 < 512)
                "condition": "or",
            },
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_memory(config["memory"])

        # Should trigger because either condition is met
        assert result["threshold_exceeded"] is True

    def test_should_use_and_condition_for_thresholds(self, mocker):
        """Test AND condition for memory thresholds."""
        mock_mem = mocker.MagicMock()
        mock_mem.total = 8 * 1024 * 1024 * 1024
        mock_mem.available = 400 * 1024 * 1024
        mock_mem.percent = 95.0
        mocker.patch("psutil.virtual_memory", return_value=mock_mem)

        config = {
            "enabled": True,
            "memory": {
                "enabled": True,
                "free_percent_threshold": 10.0,
                "free_mb_threshold": 300,  # Met (400 > 300)
                "condition": "and",
            },
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_memory(config["memory"])

        # Should not trigger because both conditions must be met
        assert result["threshold_exceeded"] is False

    def test_should_mark_percent_exceeded_only(self, mocker):
        """Test exceeded_type when percentage threshold is exceeded only."""
        mock_mem = mocker.MagicMock()
        mock_mem.total = 8 * 1024 * 1024 * 1024
        mock_mem.available = 200 * 1024 * 1024
        mock_mem.percent = 97.5
        mocker.patch("psutil.virtual_memory", return_value=mock_mem)

        config = {
            "enabled": True,
            "memory": {
                "enabled": True,
                "free_percent_threshold": 10.0,
                "free_mb_threshold": 100,
                "condition": "or",
            },
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_memory(config["memory"])

        assert result["threshold_exceeded"] is True
        assert result["exceeded_type"] == "percent"

    def test_should_mark_mb_exceeded_only(self, mocker):
        """Test exceeded_type when MB threshold is exceeded only."""
        mock_mem = mocker.MagicMock()
        mock_mem.total = 8 * 1024 * 1024 * 1024
        mock_mem.available = 200 * 1024 * 1024
        mock_mem.percent = 10.0
        mocker.patch("psutil.virtual_memory", return_value=mock_mem)

        config = {
            "enabled": True,
            "memory": {
                "enabled": True,
                "free_percent_threshold": 1.0,
                "free_mb_threshold": 300,
                "condition": "or",
            },
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_memory(config["memory"])

        assert result["threshold_exceeded"] is True
        assert result["exceeded_type"] == "mb"


class TestResourceMonitorDiskCheck:
    """Tests for disk space monitoring."""

    def test_should_detect_low_disk_space(self, mocker):
        """Test detection of low disk space."""
        mock_usage = mocker.MagicMock()
        mock_usage.total = 100 * 1024 * 1024 * 1024  # 100 GB
        mock_usage.used = 95 * 1024 * 1024 * 1024  # 95 GB
        mock_usage.free = 5 * 1024 * 1024 * 1024  # 5 GB
        mock_usage.percent = 95.0
        mocker.patch("psutil.disk_usage", return_value=mock_usage)

        config = {
            "enabled": True,
            "disk": {
                "enabled": True,
                "paths": [{"path": "/", "threshold_percent": 90.0}],
            },
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_disk(config["disk"])

        assert result["threshold_exceeded"] is True
        # Check that "/" path exists in mount_points list
        assert any(mp["path"] == "/" for mp in result["mount_points"])

    def test_should_check_multiple_mount_points(self, mocker):
        """Test checking multiple mount points."""
        def mock_disk_usage(path):
            usage = mocker.MagicMock()
            if path == "/":
                usage.percent = 85.0
            elif path == "/var":
                usage.percent = 95.0
            else:
                usage.percent = 50.0
            usage.total = 100 * 1024 ** 3
            usage.used = int(100 * 1024 ** 3 * usage.percent / 100)
            usage.free = usage.total - usage.used
            return usage

        mocker.patch("psutil.disk_usage", side_effect=mock_disk_usage)

        config = {
            "enabled": True,
            "disk": {
                "enabled": True,
                "paths": [
                    {"path": "/", "threshold_percent": 90.0},
                    {"path": "/var", "threshold_percent": 90.0},
                ],
            },
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_disk(config["disk"])

        assert result["threshold_exceeded"] is True
        assert len(result["mount_points"]) == 2

    def test_should_handle_unmounted_paths(self, mocker):
        """Test handling of unmounted or inaccessible paths."""
        mocker.patch("psutil.disk_usage", side_effect=OSError("No such file or directory"))

        config = {
            "enabled": True,
            "disk": {
                "enabled": True,
                "paths": [{"path": "/nonexistent", "threshold_percent": 90.0}],
            },
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_disk(config["disk"])

        # Should handle error gracefully
        assert "error" in result or result["threshold_exceeded"] is False

    def test_should_support_mount_points_key(self, mocker):
        """Test disk checks using mount_points configuration."""
        mock_usage = mocker.MagicMock()
        mock_usage.total = 100 * 1024 * 1024 * 1024
        mock_usage.used = 50 * 1024 * 1024 * 1024
        mock_usage.free = 50 * 1024 * 1024 * 1024
        mock_usage.percent = 50.0
        mocker.patch("psutil.disk_usage", return_value=mock_usage)
        mocker.patch("os.path.exists", return_value=True)

        config = {
            "enabled": True,
            "disk": {
                "enabled": True,
                "mount_points": [{"path": "/", "free_percent_threshold": 5.0}],
            },
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_disk(config["disk"])

        assert result["threshold_exceeded"] is False
        assert result["mount_points"][0]["path"] == "/"

    def test_should_support_string_mount_points(self, mocker):
        """Test disk checks when mount_points is a list of strings."""
        mock_usage = mocker.MagicMock()
        mock_usage.total = 100 * 1024 * 1024 * 1024
        mock_usage.used = 50 * 1024 * 1024 * 1024
        mock_usage.free = 50 * 1024 * 1024 * 1024
        mock_usage.percent = 50.0
        mocker.patch("psutil.disk_usage", return_value=mock_usage)
        mocker.patch("os.path.exists", return_value=True)

        config = {
            "enabled": True,
            "disk": {
                "enabled": True,
                "mount_points": ["/"],
            },
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_disk(config["disk"])

        assert result["threshold_exceeded"] is False
        assert result["mount_points"][0]["path"] == "/"

    def test_should_trigger_free_gb_threshold(self, mocker):
        """Test detection of low disk free GB threshold."""
        mock_usage = mocker.MagicMock()
        mock_usage.total = 100 * 1024 ** 3
        mock_usage.used = 99 * 1024 ** 3
        mock_usage.free = 1 * 1024 ** 3
        mock_usage.percent = 99.0
        mocker.patch("psutil.disk_usage", return_value=mock_usage)
        mocker.patch("os.path.exists", return_value=True)

        config = {
            "enabled": True,
            "disk": {
                "enabled": True,
                "mount_points": [
                    {"path": "/", "free_gb_threshold": 5.0, "free_percent_threshold": 0.5}
                ],
            },
        }

        monitor = ResourceMonitor(config)
        result = monitor._check_disk(config["disk"])

        assert result["threshold_exceeded"] is True
        assert result["mount_points"][0]["threshold_exceeded"] is True


class TestResourceMonitorRecoveryActions:
    """Tests for recovery action execution."""

    def test_should_execute_cpu_recovery_command(self, mocker):
        """Test execution of CPU recovery command."""
        mock_run = mocker.patch("subprocess.run")
        mocker.patch("os.getloadavg", return_value=(15.0, 10.0, 8.0))

        config = {
            "enabled": True,
            "cpu_load": {
                "enabled": True,
                "check_1min": True,
                "threshold_1min": 10.0,
                "recovery_command": "/usr/local/bin/reduce_load.sh",
            },
        }

        monitor = ResourceMonitor(config)
        monitor.check_resources()

        # Should execute recovery command
        mock_run.assert_called()

    def test_should_respect_recovery_cooldown(self, mocker, freezer):
        """Test that recovery cooldown is respected."""
        mock_run = mocker.patch("subprocess.run")
        mocker.patch("os.getloadavg", return_value=(15.0, 10.0, 8.0))

        config = {
            "enabled": True,
            "recovery_actions": {
                "cooldown_period": 300,
            },
            "cpu_load": {
                "enabled": True,
                "check_1min": True,
                "threshold_1min": 10.0,
                "recovery_command": "/usr/local/bin/reduce_load.sh",
            },
        }

        monitor = ResourceMonitor(config)

        # First recovery
        monitor._handle_high_cpu()
        first_call_count = mock_run.call_count

        # Immediate second attempt - should be blocked
        monitor._handle_high_cpu()
        assert mock_run.call_count == first_call_count

        # Manually adjust cooldown to simulate time passing
        monitor.last_action_time["high_cpu"] = time.time() - 301

        # After cooldown - should execute again
        monitor._handle_high_cpu()
        assert mock_run.call_count > first_call_count

    def test_should_skip_low_memory_recovery_during_cooldown(self, mocker):
        """Test low memory recovery is skipped when in cooldown."""
        monitor = ResourceMonitor(
            {
                "enabled": True,
                "recovery_actions": {"cooldown_period": 300, "low_memory_services": ["nginx"]},
            }
        )
        monitor.last_action_time["low_memory"] = time.time()

        restart_mock = mocker.patch.object(monitor, "_restart_services")

        monitor._handle_low_memory()

        restart_mock.assert_not_called()

    def test_should_handle_cpu_recovery_command_timeout(self, mocker):
        """Test CPU recovery command timeout handling."""
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="/bin/true", timeout=60),
        )

        monitor = ResourceMonitor(
            {
                "enabled": True,
                "cpu_load": {"recovery_command": "/bin/true"},
            }
        )

        monitor._handle_high_cpu()

        assert "high_cpu" in monitor.last_action_time

    def test_should_handle_restart_services_timeout(self, mocker):
        """Test restart services handles timeout without raising."""
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="systemctl", timeout=60),
        )

        monitor = ResourceMonitor({"enabled": True})
        monitor._restart_services(["nginx"], {"restart_interval": 0})

    def test_should_restart_services_for_low_memory(self, mocker):
        """Test low memory recovery restarts services."""
        monitor = ResourceMonitor({
            "enabled": True,
            "recovery_actions": {"low_memory_services": ["nginx"]},
        })

        restart_mock = mocker.patch.object(monitor, "_restart_services")

        monitor._handle_low_memory()

        restart_mock.assert_called_once()

    def test_should_restart_services_for_low_disk(self, mocker):
        """Test low disk recovery restarts services."""
        monitor = ResourceMonitor({
            "enabled": True,
            "recovery_actions": {"low_disk_services": ["mysql"]},
        })

        restart_mock = mocker.patch.object(monitor, "_restart_services")

        monitor._handle_low_disk()

        restart_mock.assert_called_once()

    def test_should_restart_services_with_interval(self, mocker):
        """Test restart service loop and interval handling."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0, stderr=""),
            mocker.MagicMock(returncode=1, stderr="fail"),
        ]
        sleep_mock = mocker.patch("time.sleep")

        monitor = ResourceMonitor({"enabled": True})
        monitor._restart_services(["nginx", "mysql"], {"restart_interval": 2})

        assert mock_run.call_count == 2
        sleep_mock.assert_called_once_with(2)


class TestResourceMonitorIntegration:
    """Tests for integrated resource checking."""

    def test_should_return_complete_results_dict(self, mocker):
        """Test that complete results dictionary is returned."""
        mocker.patch("os.getloadavg", return_value=(5.0, 4.0, 3.0))
        mock_mem = mocker.MagicMock()
        mock_mem.total = 8 * 1024 ** 3
        mock_mem.available = 2 * 1024 ** 3
        mock_mem.percent = 75.0
        mocker.patch("psutil.virtual_memory", return_value=mock_mem)

        config = {
            "enabled": True,
            "cpu_load": {"enabled": True},
            "memory": {"enabled": True},
            "disk": {"enabled": False},
        }

        monitor = ResourceMonitor(config)
        results = monitor.check_resources()

        assert "timestamp" in results
        assert "cpu_load" in results
        assert "memory" in results
        assert "disk" in results
        assert "actions_taken" in results

    def test_should_handle_all_checks_disabled(self):
        """Test handling when all checks are disabled."""
        config = {
            "enabled": True,
            "cpu_load": {"enabled": False},
            "memory": {"enabled": False},
            "disk": {"enabled": False},
        }

        monitor = ResourceMonitor(config)
        results = monitor.check_resources()

        assert results["cpu_load"] is None
        assert results["memory"] is None
        assert results["disk"] is None
        assert results["actions_taken"] == []

    def test_should_handle_psutil_error(self, mocker, caplog):
        """Test handling of psutil errors."""
        mocker.patch("psutil.virtual_memory", side_effect=Exception("psutil error"))

        config = {
            "enabled": True,
            "memory": {"enabled": True},
        }

        monitor = ResourceMonitor(config)
        results = monitor.check_resources()

        # Should handle error gracefully - memory section should have error
        assert results["memory"] is not None
        assert "error" in results["memory"]

    def test_should_return_disabled_when_monitor_disabled(self):
        """Test check_resources returns disabled response when monitor is off."""
        monitor = ResourceMonitor({"enabled": False})

        results = monitor.check_resources()

        assert results == {"enabled": False}

    def test_should_get_current_stats(self, mocker):
        """Test get_current_stats returns structured data."""
        mocker.patch("os.getloadavg", return_value=(1.0, 2.0, 3.0))

        mock_cpu = mocker.patch("psutil.cpu_percent", return_value=10.0)

        mock_mem = mocker.MagicMock()
        mock_mem.total = 8 * 1024 * 1024 * 1024
        mock_mem.available = 2 * 1024 * 1024 * 1024
        mock_mem.used = 6 * 1024 * 1024 * 1024
        mock_mem.percent = 75.0
        mocker.patch("psutil.virtual_memory", return_value=mock_mem)

        mocker.patch("os.path.exists", return_value=True)

        mock_usage = mocker.MagicMock()
        mock_usage.total = 100 * 1024 ** 3
        mock_usage.used = 60 * 1024 ** 3
        mock_usage.free = 40 * 1024 ** 3
        mock_usage.percent = 60.0
        mocker.patch("psutil.disk_usage", return_value=mock_usage)

        mock_net = mocker.MagicMock()
        mock_net.bytes_sent = 100
        mock_net.bytes_recv = 200
        mock_net.packets_sent = 1
        mock_net.packets_recv = 2
        mock_net.errin = 0
        mock_net.errout = 0
        mock_net.dropin = 0
        mock_net.dropout = 0
        mocker.patch(
            "psutil.net_io_counters",
            side_effect=[mock_net, {"eth0": mock_net}],
        )

        monitor = ResourceMonitor({"disk": {"mount_points": [{"path": "/"}]}})
        stats = monitor.get_current_stats()

        assert stats["cpu"]["load_1min"] == 1.0
        assert stats["memory"]["total_mb"] > 0
        assert stats["disk"]["mount_points"][0]["path"] == "/"
        assert stats["network"]["total"]["bytes_sent"] == 100
        assert "eth0" in stats["network"]["interfaces"]

    def test_should_evaluate_action_success(self):
        """Test action success evaluation logic."""
        monitor = ResourceMonitor({})

        assert monitor._evaluate_action_success({"recovery_command_success": True}) is True
        assert monitor._evaluate_action_success({"recovery_command_success": False}) is False
        assert (
            monitor._evaluate_action_success(
                {"services": [{"success": True}, {"success": True}]}
            )
            is True
        )
        assert (
            monitor._evaluate_action_success(
                {"services": [{"success": True}, {"success": False}]}
            )
            is False
        )

    def test_should_handle_errors_in_get_current_stats(self, mocker):
        """Test error handling in get_current_stats."""
        mocker.patch("os.getloadavg", side_effect=Exception("load error"))

        monitor = ResourceMonitor({})
        stats = monitor.get_current_stats()

        assert "error" in stats

    def test_should_skip_missing_mount_points(self, mocker):
        """Test get_current_stats skips missing mount points."""
        mocker.patch("os.getloadavg", return_value=(0.1, 0.2, 0.3))
        mocker.patch("psutil.cpu_percent", return_value=5.0)

        mock_mem = mocker.MagicMock()
        mock_mem.total = 1024 * 1024 * 1024
        mock_mem.available = 512 * 1024 * 1024
        mock_mem.used = 512 * 1024 * 1024
        mock_mem.percent = 50.0
        mocker.patch("psutil.virtual_memory", return_value=mock_mem)

        mocker.patch("os.path.exists", return_value=False)

        monitor = ResourceMonitor({"disk": {"mount_points": [{"path": "/missing"}]}})
        stats = monitor.get_current_stats()

        assert stats["disk"]["mount_points"] == []


class TestResourceMonitorAdditionalCoverage:
    """Additional tests to cover missing branches."""

    def test_should_append_action_results_when_present(self, mocker):
        """Test action_results list is populated when recovery returns details."""
        monitor = ResourceMonitor({"enabled": True, "cpu_load": {"enabled": True}})

        mocker.patch.object(monitor, "_check_cpu_load", return_value={"threshold_exceeded": True})
        mocker.patch.object(monitor, "_handle_high_cpu", return_value={"action": "high_cpu"})

        results = monitor.check_resources()

        assert results["actions_taken"] == ["high_cpu_recovery"]
        assert results["action_results"] == [{"action": "high_cpu"}]

    def test_should_handle_disk_usage_error(self, mocker):
        """Test disk check handles disk usage errors per mount point."""
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("psutil.disk_usage", side_effect=RuntimeError("disk error"))

        monitor = ResourceMonitor({"enabled": True})
        result = monitor._check_disk({"mount_points": [{"path": "/"}]})

        assert result["mount_points"][0]["error"] == "disk error"

    def test_should_mark_recovery_command_failure(self, mocker):
        """Test high CPU recovery marks command failure on non-zero exit."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(returncode=1, stderr="fail")

        monitor = ResourceMonitor(
            {
                "enabled": True,
                "cpu_load": {"recovery_command": "/bin/false"},
            }
        )

        action = monitor._handle_high_cpu()

        assert action["details"]["recovery_command_success"] is False
        assert action["success"] is False

    def test_should_skip_low_disk_recovery_during_cooldown(self):
        """Test low disk recovery is skipped when in cooldown."""
        monitor = ResourceMonitor({"enabled": True})
        monitor.last_action_time["low_disk"] = time.time()

        assert monitor._handle_low_disk() is None

    def test_should_handle_restart_services_exception(self, mocker):
        """Test restart services handles generic exceptions."""
        mocker.patch("subprocess.run", side_effect=RuntimeError("boom"))

        monitor = ResourceMonitor({"enabled": True})
        results = monitor._restart_services(["nginx"], {"restart_interval": 0})

        assert results[0]["success"] is False
        assert results[0]["stderr"] == "boom"

    def test_should_handle_check_resources_exception(self, mocker):
        """Test check_resources catches unexpected exceptions."""
        monitor = ResourceMonitor({"enabled": True, "cpu_load": {"enabled": True}})
        mocker.patch.object(monitor, "_check_cpu_load", side_effect=RuntimeError("boom"))

        results = monitor.check_resources()

        assert "error" in results

    def test_should_mark_memory_threshold_exceeded_both(self, mocker):
        """Test memory threshold exceeded for both percent and MB."""
        mock_mem = mocker.MagicMock()
        mock_mem.total = 1000
        mock_mem.available = 1
        mock_mem.percent = 99.9
        mocker.patch("psutil.virtual_memory", return_value=mock_mem)

        monitor = ResourceMonitor({"enabled": True})
        result = monitor._check_memory(
            {"free_percent_threshold": 5.0, "free_mb_threshold": 512, "condition": "or"}
        )

        assert result["threshold_exceeded"] is True
        assert result["exceeded_type"] == "both"

    def test_should_mark_memory_threshold_exceeded_mb_only(self, mocker):
        """Test memory threshold exceeded only by MB condition."""
        mock_mem = mocker.MagicMock()
        mock_mem.total = 1000 * 1024 * 1024
        mock_mem.available = 100 * 1024 * 1024
        mock_mem.percent = 10.0
        mocker.patch("psutil.virtual_memory", return_value=mock_mem)

        monitor = ResourceMonitor({"enabled": True})
        result = monitor._check_memory(
            {"free_percent_threshold": 5.0, "free_mb_threshold": 512, "condition": "or"}
        )

        assert result["threshold_exceeded"] is True
        assert result["exceeded_type"] == "mb"

    def test_should_allow_action_after_cooldown(self):
        """Test cooldown check allows action after elapsed period."""
        monitor = ResourceMonitor({"enabled": True, "recovery_actions": {"cooldown_period": 1}})
        monitor.last_action_time["high_cpu"] = time.time() - 5

        assert monitor._check_action_cooldown("high_cpu") is True

    def test_should_append_memory_action_results(self, mocker):
        """Test memory action results are appended."""
        monitor = ResourceMonitor({"enabled": True, "memory": {"enabled": True}})

        mocker.patch.object(monitor, "_check_memory", return_value={"threshold_exceeded": True})
        mocker.patch.object(
            monitor,
            "_handle_low_memory",
            return_value={"action": "low_memory_recovery"},
        )

        results = monitor.check_resources()

        assert results["actions_taken"] == ["low_memory_recovery"]
        assert results["action_results"] == [{"action": "low_memory_recovery"}]

    def test_should_append_disk_action_results(self, mocker):
        """Test disk action results are appended."""
        monitor = ResourceMonitor({"enabled": True, "disk": {"enabled": True}})

        mocker.patch.object(monitor, "_check_disk", return_value={"threshold_exceeded": True})
        mocker.patch.object(
            monitor,
            "_handle_low_disk",
            return_value={"action": "low_disk_recovery"},
        )

        results = monitor.check_resources()

        assert results["actions_taken"] == ["low_disk_recovery"]
        assert results["action_results"] == [{"action": "low_disk_recovery"}]

    def test_should_handle_disk_outer_exception(self, mocker):
        """Test _check_disk handles outer exceptions."""
        mocker.patch("os.path.exists", side_effect=RuntimeError("boom"))

        monitor = ResourceMonitor({"enabled": True})
        result = monitor._check_disk({"mount_points": [{"path": "/"}]})

        assert result["error"] == "boom"

    def test_should_handle_high_cpu_with_service_restarts(self, mocker):
        """Test high CPU recovery restarts services when configured."""
        monitor = ResourceMonitor(
            {
                "enabled": True,
                "recovery_actions": {"high_cpu_services": ["nginx"]},
            }
        )

        restart_mock = mocker.patch.object(monitor, "_restart_services", return_value=[{"success": True}])

        result = monitor._handle_high_cpu()

        restart_mock.assert_called_once()
        assert result["details"]["services"] == [{"success": True}]

    def test_should_wait_between_restarts(self, mocker):
        """Test restart services waits between service restarts."""
        mocker.patch("subprocess.run", return_value=mocker.MagicMock(returncode=0, stdout="", stderr=""))
        sleep_mock = mocker.patch("time.sleep")

        monitor = ResourceMonitor({"enabled": True})
        monitor._restart_services(["svc1", "svc2"], {"restart_interval": 1})

        sleep_mock.assert_called_once_with(1)
