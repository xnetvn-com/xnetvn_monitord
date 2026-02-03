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

"""Unit tests for ServiceMonitor.

This module contains comprehensive unit tests for service monitoring
and automatic restart functionality.
"""

import subprocess
import time
import urllib.error
from unittest.mock import MagicMock, call

import pytest

from xnetvn_monitord.monitors.service_monitor import ServiceMonitor


class TestServiceMonitorInitialization:
    """Tests for ServiceMonitor initialization."""

    def test_should_initialize_with_config(self):
        """Test successful initialization with configuration."""
        config = {"enabled": True, "services": []}
        monitor = ServiceMonitor(config)

        assert monitor.config == config
        assert monitor.enabled is True
        assert isinstance(monitor.restart_history, dict)
        assert isinstance(monitor.cooldown_tracker, dict)

    def test_should_default_to_enabled(self):
        """Test that monitor defaults to enabled if not specified."""
        config = {"services": []}
        monitor = ServiceMonitor(config)

        assert monitor.enabled is True

    def test_should_initialize_tracking_dicts(self):
        """Test initialization of tracking dictionaries."""
        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        assert monitor.restart_history == {}
        assert monitor.cooldown_tracker == {}


class TestServiceMonitorSystemctlCheck:
    """Tests for systemctl check method."""

    def test_should_detect_active_systemd_service(self, mocker):
        """Test detection of active systemd service."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="active\n")

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        service_config = {
            "name": "nginx",
            "check_method": "systemctl",
            "service_name": "nginx",
        }

        result = monitor._check_systemctl(service_config)

        assert result is True
        mock_run.assert_called_once_with(
            ["systemctl", "is-active", "nginx"],
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_should_detect_inactive_systemd_service(self, mocker):
        """Test detection of inactive systemd service."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=3, stdout="inactive\n")

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        service_config = {
            "name": "nginx",
            "check_method": "systemctl",
            "service_name": "nginx",
        }

        result = monitor._check_systemctl(service_config)

        assert result is False

    def test_should_detect_failed_systemd_service(self, mocker):
        """Test detection of failed systemd service."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=1, stdout="failed\n")

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        service_config = {
            "name": "nginx",
            "check_method": "systemctl",
            "service_name": "nginx",
        }

        result = monitor._check_systemctl(service_config)

        assert result is False

    def test_should_handle_systemctl_timeout(self, mocker):
        """Test handling of systemctl command timeout."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="systemctl", timeout=10)

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        service_config = {
            "name": "nginx",
            "check_method": "systemctl",
            "service_name": "nginx",
        }

        result = monitor._check_systemctl(service_config)

        assert result is False

    def test_should_handle_systemctl_not_found(self, mocker):
        """Test handling when systemctl command is not found."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = FileNotFoundError()

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        service_config = {
            "name": "nginx",
            "check_method": "systemctl",
            "service_name": "nginx",
        }

        result = monitor._check_systemctl(service_config)

        assert result is False

    def test_should_return_false_when_service_name_missing(self):
        """Test systemctl check returns False when service_name is missing."""
        monitor = ServiceMonitor({"enabled": True})

        result = monitor._check_systemctl({"name": "nginx"})

        assert result is False

    def test_should_use_systemctl_pattern_when_configured(self, mocker):
        """Test systemctl check uses pattern matcher when provided."""
        mock_pattern = mocker.patch.object(
            ServiceMonitor, "_check_systemctl_pattern", return_value=True
        )

        monitor = ServiceMonitor({"enabled": True})
        service_config = {
            "name": "nginx",
            "check_method": "systemctl",
            "service_name_pattern": "nginx.*",
        }

        assert monitor._check_systemctl(service_config) is True
        mock_pattern.assert_called_once_with("nginx.*")


class TestServiceMonitorProcessCheck:
    """Tests for process check method."""

    def test_should_detect_running_process_by_name(self, mocker):
        """Test detection of running process by exact name."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="1234\n5678\n")

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        service_config = {
            "name": "nginx",
            "check_method": "process",
            "process_name": "nginx",
        }

        result = monitor._check_process(service_config)

        assert result is True
        mock_run.assert_called_once_with(
            ["pgrep", "-x", "nginx"],
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_should_detect_missing_process(self, mocker):
        """Test detection when process is not running."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        service_config = {
            "name": "nginx",
            "check_method": "process",
            "process_name": "nginx",
        }

        result = monitor._check_process(service_config)

        assert result is False

    def test_should_handle_pgrep_timeout(self, mocker):
        """Test handling of pgrep command timeout."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pgrep", timeout=10)

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        service_config = {
            "name": "nginx",
            "check_method": "process",
            "process_name": "nginx",
        }

        result = monitor._check_process(service_config)

        assert result is False

    def test_should_handle_multiple_processes_same_name(self, mocker):
        """Test handling when multiple processes have the same name."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0, stdout="1234\n5678\n9012\n3456\n"
        )

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        service_config = {
            "name": "php-fpm",
            "check_method": "process",
            "process_name": "php-fpm",
        }

        result = monitor._check_process(service_config)

        # Should return True if any process found
        assert result is True

    def test_should_return_false_when_process_name_missing(self):
        """Test process check returns False when process_name is missing."""
        monitor = ServiceMonitor({"enabled": True})

        result = monitor._check_process({"name": "nginx"})

        assert result is False


class TestServiceMonitorProcessRegexCheck:
    """Tests for process regex check method."""

    def test_should_match_process_by_regex_pattern(self, mocker):
        """Test matching process using regex pattern."""
        mock_run = mocker.patch("subprocess.run")
        # Mock ps aux output with matching process
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "root     1234  0.0  0.1  12345  6789 ?  Ss   10:00   0:00 "
                "php-fpm: master process\n"
            ),
        )

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        service_config = {
            "name": "php-fpm",
            "check_method": "process_regex",
            "process_pattern": "php-fpm.*master",
        }

        result = monitor._check_process_regex(service_config)

        assert result is True

    def test_should_not_match_invalid_pattern(self, mocker):
        """Test no match when pattern doesn't match any process."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        service_config = {
            "name": "php-fpm",
            "check_method": "process_regex",
            "process_pattern": "php-fpm-nonexistent",
        }

        result = monitor._check_process_regex(service_config)

        assert result is False

    def test_should_match_php_fpm_versions(self, mocker):
        """Test matching different PHP-FPM versions."""
        mock_run = mocker.patch("subprocess.run")
        # Mock ps aux output with PHP-FPM processes
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "root     1234  0.0  0.1  12345  6789 ?  Ss   10:00   0:00 "
                "php-fpm7.4: master process\n"
                "root     5678  0.0  0.1  12345  6789 ?  Ss   10:00   0:00 "
                "php-fpm8.1: master process\n"
            ),
        )

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        patterns = [
            r"php-fpm7\.\d+",
            r"php-fpm8\.\d+",
            r"php-fpm.*master",
        ]

        for pattern in patterns:
            service_config = {
                "name": f"php-fpm",
                "check_method": "process_regex",
                "process_pattern": pattern,
            }

            result = monitor._check_process_regex(service_config)
            assert result is True

    def test_should_use_multi_instance_when_pattern_missing(self, mocker):
        """Test multi-instance check when pattern is missing."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="active\n")

        monitor = ServiceMonitor({"enabled": True})
        service_config = {
            "name": "php-fpm",
            "check_method": "process_regex",
            "multi_instance": True,
            "instances": [{"service_name": "php8.1-fpm"}],
        }

        result = monitor._check_process_regex(service_config)

        assert result is True

    def test_should_return_false_when_ps_returns_nonzero(self, mocker):
        """Test process regex returns False when ps command fails."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        monitor = ServiceMonitor({"enabled": True})
        service_config = {
            "name": "php-fpm",
            "check_method": "process_regex",
            "process_pattern": "php-fpm",
        }

        assert monitor._check_process_regex(service_config) is False


class TestServiceMonitorProcessRegexAdditional:
    """Additional tests for process regex matching."""

    def test_should_collect_patterns_from_list_entries(self, mocker):
        """Test pattern collection supports list entries and dict patterns."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="root 1 0 worker\n")

        monitor = ServiceMonitor({"enabled": True})
        service_config = {
            "name": "worker",
            "check_method": "process_regex",
            "process_patterns": [{"pattern": "worker"}],
        }

        assert monitor._check_process_regex(service_config) is True

    def test_should_return_false_when_no_pattern_matches(self, mocker):
        """Test regex check returns False when no match is found."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="root 1 0 nginx\n")

        monitor = ServiceMonitor({"enabled": True})
        service_config = {
            "name": "worker",
            "check_method": "process_regex",
            "process_pattern": "worker",
        }

        assert monitor._check_process_regex(service_config) is False

    def test_should_cache_compiled_regex_patterns(self, mocker):
        """Test regex patterns are cached between calls."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="root 1 0 worker\n")

        monitor = ServiceMonitor({"enabled": True})
        service_config = {
            "name": "worker",
            "check_method": "process_regex",
            "process_pattern": "worker",
        }

        assert monitor._regex_cache == {}
        assert monitor._check_process_regex(service_config) is True
        assert monitor._regex_cache

    def test_should_return_false_when_no_patterns_and_no_multi_instance(self):
        """Test regex check returns False when no patterns provided."""
        monitor = ServiceMonitor({"enabled": True})

        service_config = {
            "name": "worker",
            "check_method": "process_regex",
        }

        assert monitor._check_process_regex(service_config) is False


class TestServiceMonitorMultiInstance:
    """Tests for multi-instance service checks."""

    def test_should_ignore_instances_without_service_name(self):
        """Test multi-instance check ignores invalid instance entries."""
        monitor = ServiceMonitor({"enabled": True})

        result = monitor._check_multi_instance({"instances": [{"name": "skip"}]})

        assert result is False

    def test_should_handle_instance_check_exception(self, mocker):
        """Test multi-instance check handles subprocess failures."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = OSError("boom")

        monitor = ServiceMonitor({"enabled": True})
        service_config = {"instances": [{"service_name": "nginx"}]}

        assert monitor._check_multi_instance(service_config) is False


class TestServiceMonitorCustomCommandCheck:
    """Tests for custom command check method."""

    def test_should_execute_custom_check_command(self, mocker):
        """Test execution of custom check command."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="OK\n")

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        service_config = {
            "name": "custom_service",
            "check_method": "custom_command",
            "check_command": "/usr/local/bin/check_service.sh",
        }

        result = monitor._check_custom_command(service_config)

        assert result is True

    def test_should_handle_custom_command_failure(self, mocker):
        """Test handling of custom command failure."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=1, stdout="FAILED\n")

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        service_config = {
            "name": "custom_service",
            "check_method": "custom_command",
            "check_command": "/usr/local/bin/check_service.sh",
        }

        result = monitor._check_custom_command(service_config)

        assert result is False

    def test_should_handle_custom_command_timeout(self, mocker):
        """Test handling of custom command timeout."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="/usr/local/bin/check_service.sh", timeout=30
        )

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        service_config = {
            "name": "custom_service",
            "check_method": "custom_command",
            "check_command": "/usr/local/bin/check_service.sh",
            "check_timeout": 30,
        }

        result = monitor._check_custom_command(service_config)

        assert result is False

    def test_should_return_false_when_command_missing(self):
        """Test custom command check without command returns False."""
        monitor = ServiceMonitor({"enabled": True})
        service_config = {"name": "custom", "check_method": "custom_command"}

        result = monitor._check_custom_command(service_config)

        assert result is False

    def test_should_return_false_when_command_raises_exception(self, mocker):
        """Test custom command check handles exceptions."""
        mocker.patch("subprocess.run", side_effect=OSError("failure"))

        monitor = ServiceMonitor({"enabled": True})
        service_config = {
            "name": "custom",
            "check_method": "custom_command",
            "check_command": "/bin/false",
        }

        assert monitor._check_custom_command(service_config) is False


class TestServiceMonitorIptablesCheck:
    """Tests for iptables check method."""

    def test_should_return_true_when_iptables_command_succeeds(self, mocker):
        """Test iptables check returns True on success."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        monitor = ServiceMonitor({"enabled": True})
        service_config = {
            "name": "iptables",
            "check_method": "iptables",
            "check_timeout": 10,
        }

        assert monitor._check_iptables(service_config) is True
        mock_run.assert_called_once_with(
            ["iptables", "-L", "-n"],
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_should_return_false_when_iptables_missing(self, mocker):
        """Test iptables check handles FileNotFoundError."""
        mocker.patch("subprocess.run", side_effect=FileNotFoundError())

        monitor = ServiceMonitor({"enabled": True})
        service_config = {
            "name": "iptables",
            "check_method": "iptables",
        }

        assert monitor._check_iptables(service_config) is False

    def test_should_delegate_to_custom_command_when_override_present(self, mocker):
        """Test iptables check uses custom command when provided."""
        mock_custom = mocker.patch.object(
            ServiceMonitor, "_check_custom_command", return_value=True
        )

        monitor = ServiceMonitor({"enabled": True})
        service_config = {
            "name": "iptables",
            "check_method": "iptables",
            "check_command": "iptables -L -n",
        }

        assert monitor._check_iptables(service_config) is True
        mock_custom.assert_called_once_with(service_config)


class TestServiceMonitorHttpCheck:
    """Tests for HTTP/HTTPS check method."""

    def test_should_return_error_when_url_missing(self):
        """Test HTTP check returns error when URL is missing."""
        monitor = ServiceMonitor({"enabled": True})

        result = monitor._check_http({"name": "web"})

        assert result["running"] is False
        assert "Missing URL" in result["message"]

    def test_should_return_ok_for_expected_status(self, mocker):
        """Test HTTP check returns running when status code is expected."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.__enter__.return_value = mock_response
        mocker.patch("urllib.request.urlopen", return_value=mock_response)
        mocker.patch("time.monotonic", side_effect=[0, 0.1])

        monitor = ServiceMonitor({"enabled": True})
        service_config = {
            "name": "web",
            "check_method": "https",
            "url": "https://example.com/health",
            "expected_status_codes": [200],
            "max_response_time_ms": 1000,
        }

        result = monitor._check_http(service_config)

        assert result["running"] is True
        assert result["status_code"] == 200

    def test_should_fail_on_slow_response(self, mocker):
        """Test HTTP check fails when response is too slow."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.__enter__.return_value = mock_response
        mocker.patch("urllib.request.urlopen", return_value=mock_response)
        mocker.patch("time.monotonic", side_effect=[0, 2.0])

        monitor = ServiceMonitor({"enabled": True})
        service_config = {
            "name": "web",
            "check_method": "https",
            "url": "https://example.com/health",
            "expected_status_codes": [200],
            "max_response_time_ms": 1000,
        }

        result = monitor._check_http(service_config)

        assert result["running"] is False
        assert "Slow response" in result["message"]

    def test_should_fail_on_http_error(self, mocker):
        """Test HTTP check returns failure on HTTP error codes."""
        error = urllib.error.HTTPError(
            url="https://example.com/health",
            code=500,
            msg="Server Error",
            hdrs=None,
            fp=None,
        )
        mocker.patch("urllib.request.urlopen", side_effect=error)
        mocker.patch("time.monotonic", side_effect=[0, 0.2])

        monitor = ServiceMonitor({"enabled": True})
        service_config = {
            "name": "web",
            "check_method": "https",
            "url": "https://example.com/health",
        }

        result = monitor._check_http(service_config)

        assert result["running"] is False
        assert result["status_code"] == 500

    def test_should_fail_on_unexpected_status(self, mocker):
        """Test HTTP check fails when status code is unexpected."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 503
        mock_response.__enter__.return_value = mock_response
        mocker.patch("urllib.request.urlopen", return_value=mock_response)
        mocker.patch("time.monotonic", side_effect=[0, 0.1])

        monitor = ServiceMonitor({"enabled": True})
        service_config = {
            "name": "web",
            "check_method": "http",
            "url": "http://example.com/health",
            "expected_status_codes": [200],
        }

        result = monitor._check_http(service_config)

        assert result["running"] is False
        assert "Unexpected HTTP status" in result["message"]

    def test_should_disable_tls_verification_when_configured(self, mocker):
        """Test HTTP check uses unverified TLS context when disabled."""
        mock_context = MagicMock()
        mocker.patch(
            "xnetvn_monitord.monitors.service_monitor.ssl.create_default_context",
            return_value=mock_context,
        )
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.__enter__.return_value = mock_response
        mocker.patch("urllib.request.urlopen", return_value=mock_response)
        mocker.patch("time.monotonic", side_effect=[0, 0.05])

        monitor = ServiceMonitor({"enabled": True})
        service_config = {
            "name": "web",
            "check_method": "https",
            "url": "https://example.com/health",
            "verify_tls": False,
        }

        result = monitor._check_http(service_config)

        assert result["running"] is True

    def test_should_fail_on_connection_error(self, mocker):
        """Test HTTP check returns failure on connection errors."""
        mocker.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection failed"),
        )
        mocker.patch("time.monotonic", side_effect=[0, 0.3])

        monitor = ServiceMonitor({"enabled": True})
        service_config = {
            "name": "web",
            "check_method": "https",
            "url": "https://example.com/health",
        }

        result = monitor._check_http(service_config)

        assert result["running"] is False
        assert "Connection error" in result["message"]


class TestServiceMonitorCheckAllServices:
    """Tests for checking all configured services."""

    def test_should_check_all_services_in_sequence(self, mocker):
        """Test checking multiple services in sequence."""
        mock_systemctl = mocker.patch.object(ServiceMonitor, "_check_systemctl")
        mock_systemctl.return_value = True

        config = {
            "enabled": True,
            "services": [
                {"name": "nginx", "enabled": True, "check_method": "systemctl"},
                {"name": "mysql", "enabled": True, "check_method": "systemctl"},
            ],
        }

        monitor = ServiceMonitor(config)
        results = monitor.check_all_services()

        assert len(results) == 2
        assert all(r["running"] for r in results)

    def test_should_skip_disabled_services(self, mocker):
        """Test that disabled services are skipped."""
        mock_systemctl = mocker.patch.object(ServiceMonitor, "_check_systemctl")

        config = {
            "enabled": True,
            "services": [
                {"name": "nginx", "enabled": True, "check_method": "systemctl"},
                {"name": "mysql", "enabled": False, "check_method": "systemctl"},
            ],
        }

        monitor = ServiceMonitor(config)
        results = monitor.check_all_services()

        assert len(results) == 1
        assert results[0]["name"] == "nginx"

    def test_should_handle_empty_service_list(self):
        """Test handling of empty service list."""
        config = {"enabled": True, "services": []}
        monitor = ServiceMonitor(config)

        results = monitor.check_all_services()

        assert results == []

    def test_should_return_empty_list_when_disabled(self):
        """Test returning empty list when monitor is disabled."""
        config = {"enabled": False, "services": [{"name": "nginx"}]}
        monitor = ServiceMonitor(config)

        results = monitor.check_all_services()

        assert results == []

    def test_should_continue_on_single_service_error(self, mocker):
        """Test that monitoring continues after a single service error."""
        mock_check = mocker.patch.object(ServiceMonitor, "_check_service")
        mock_check.side_effect = [
            {"name": "nginx", "running": True},
            Exception("Check failed"),
            {"name": "mysql", "running": True},
        ]

        config = {
            "enabled": True,
            "services": [
                {"name": "nginx", "enabled": True},
                {"name": "apache", "enabled": True},
                {"name": "mysql", "enabled": True},
            ],
        }

        monitor = ServiceMonitor(config)
        results = monitor.check_all_services()

        # Should have results for all services, even if one failed
        assert len(results) == 3
        assert results[1]["running"] is False
        assert "error" in results[1]

    def test_should_handle_unknown_check_method(self):
        """Test unknown check method returns warning message."""
        monitor = ServiceMonitor({"enabled": True})
        service_config = {"name": "unknown", "check_method": "unsupported"}

        status = monitor._check_service(service_config)

        assert status["running"] is False
        assert "Unknown check method" in status["message"]

    def test_should_check_service_using_process_method(self, mocker):
        """Test _check_service uses process check method."""
        monitor = ServiceMonitor({"enabled": True})
        mocker.patch.object(monitor, "_check_process", return_value=True)

        service_config = {"name": "nginx", "check_method": "process"}
        status = monitor._check_service(service_config)

        assert status["running"] is True
        assert status["message"] == "Process found"

    def test_should_check_service_using_custom_command(self, mocker):
        """Test _check_service uses custom command check method."""
        monitor = ServiceMonitor({"enabled": True})
        mocker.patch.object(monitor, "_check_custom_command", return_value=False)

        service_config = {"name": "nginx", "check_method": "custom_command"}
        status = monitor._check_service(service_config)

        assert status["running"] is False
        assert status["message"] == "Check failed"

    def test_should_check_service_using_process_regex(self, mocker):
        """Test _check_service uses process_regex method."""
        monitor = ServiceMonitor({"enabled": True})
        mocker.patch.object(monitor, "_check_process_regex", return_value=True)

        service_config = {"name": "nginx", "check_method": "process_regex"}
        status = monitor._check_service(service_config)

        assert status["running"] is True
        assert status["message"] == "Process pattern matched"


class TestServiceMonitorProcessRegex:
    """Tests for process regex and multi-instance checks."""

    def test_should_use_multi_instance_when_pattern_missing(self, mocker):
        """Test multi-instance check executes when pattern missing."""
        monitor = ServiceMonitor({"enabled": True})
        mocker.patch.object(monitor, "_check_multi_instance", return_value=True)

        service_config = {"multi_instance": True}
        assert monitor._check_process_regex(service_config) is True

    def test_should_return_false_on_process_regex_error(self, mocker):
        """Test process regex handles exceptions."""
        mocker.patch("subprocess.run", side_effect=RuntimeError("boom"))

        monitor = ServiceMonitor({"enabled": True})
        service_config = {"process_pattern": "nginx"}

        assert monitor._check_process_regex(service_config) is False


class TestServiceMonitorScheduling:
    """Tests for per-service check scheduling."""

    def test_should_skip_check_when_interval_not_elapsed(self, mocker):
        """Test service check is skipped when interval not elapsed."""
        mocker.patch.object(ServiceMonitor, "_check_systemctl", return_value=True)
        mocker.patch("time.time", return_value=1020)

        config = {
            "enabled": True,
            "services": [
                {
                    "name": "nginx",
                    "check_method": "systemctl",
                    "check_interval": {"value": 60, "unit": "seconds"},
                }
            ],
        }

        monitor = ServiceMonitor(config)
        monitor.last_check_time["nginx"] = 1000

        results = monitor.check_all_services()

        assert results == []


class TestServiceMonitorIntervals:
    """Tests for interval parsing utilities."""

    def test_should_parse_interval_seconds(self):
        """Test parsing interval configuration to seconds."""
        monitor = ServiceMonitor({"enabled": True})

        assert monitor._parse_interval_seconds(15) == 15
        assert monitor._parse_interval_seconds({"value": 2, "unit": "minutes"}) == 120
        assert monitor._parse_interval_seconds({"value": 1, "unit": "hours"}) == 3600
        assert monitor._parse_interval_seconds({"value": 3, "unit": "secs"}) == 3
        assert monitor._parse_interval_seconds({"value": 5, "unit": "unknown"}) is None

    def test_should_return_none_when_interval_value_missing(self):
        """Test interval parsing returns None when value is missing."""
        monitor = ServiceMonitor({"enabled": True})

        assert monitor._parse_interval_seconds({"unit": "seconds"}) is None

    def test_should_return_none_for_unsupported_interval_type(self):
        """Test interval parsing returns None for unsupported types."""
        monitor = ServiceMonitor({"enabled": True})

        assert monitor._parse_interval_seconds("invalid") is None

    def test_should_update_last_check_time_when_interval_elapsed(self, mocker):
        """Test last_check_time is updated for a scheduled check."""
        monitor = ServiceMonitor({"enabled": True})
        mocker.patch("time.time", return_value=1000)

        service_config = {
            "name": "nginx",
            "check_interval": {"value": 10, "unit": "seconds"},
        }

        should_check = monitor._should_check_service(service_config)

        assert should_check is True
        assert monitor.last_check_time["nginx"] == 1000


class TestServiceMonitorCheckService:
    """Tests for ServiceMonitor._check_service."""

    def test_should_include_http_status_when_check_method_http(self, mocker):
        """Test HTTP check results are included in service status."""
        monitor = ServiceMonitor({"enabled": True})
        mocker.patch.object(
            ServiceMonitor,
            "_check_http",
            return_value={"running": True, "message": "OK"},
        )

        status = monitor._check_service(
            {"name": "api", "check_method": "http", "url": "http://example"}
        )

        assert status["running"] is True
        assert status["message"] == "OK"
        assert status["http_status"]["running"] is True

    def test_should_handle_check_service_exception(self, mocker):
        """Test _check_service handles check errors gracefully."""
        monitor = ServiceMonitor({"enabled": True})
        mocker.patch.object(
            ServiceMonitor,
            "_check_systemctl",
            side_effect=RuntimeError("boom"),
        )

        status = monitor._check_service(
            {"name": "nginx", "check_method": "systemctl", "service_name": "nginx"}
        )

        assert status["running"] is False
        assert status["message"].startswith("Check error:")


class TestServiceMonitorSystemctlPattern:
    """Tests for systemctl regex pattern checks."""

    def test_should_match_active_unit_by_pattern(self, mocker):
        """Test systemctl pattern matching when unit is active."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="nginx.service loaded active running Nginx\n",
        )

        monitor = ServiceMonitor({"enabled": True})
        assert monitor._check_systemctl_pattern("nginx\\.service") is True

    def test_should_return_false_when_no_active_units(self, mocker):
        """Test systemctl pattern returns False when no active unit matches."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="nginx.service loaded inactive dead Nginx\n",
        )

        monitor = ServiceMonitor({"enabled": True})
        assert monitor._check_systemctl_pattern("nginx\\.service") is False

    def test_should_return_false_when_systemctl_pattern_command_fails(self, mocker):
        """Test systemctl pattern returns False when command fails."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        monitor = ServiceMonitor({"enabled": True})
        assert monitor._check_systemctl_pattern("nginx") is False

    def test_should_skip_invalid_lines_when_checking_pattern(self, mocker):
        """Test systemctl pattern ignores invalid output lines."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="invalid\nnginx.service loaded active running Nginx\n",
        )

        monitor = ServiceMonitor({"enabled": True})
        assert monitor._check_systemctl_pattern("nginx\\.service") is True

    def test_should_handle_systemctl_pattern_exception(self, mocker):
        """Test systemctl pattern handles unexpected exceptions."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = OSError("boom")

        monitor = ServiceMonitor({"enabled": True})
        assert monitor._check_systemctl_pattern("nginx") is False


class TestServiceMonitorActionReadiness:
    """Tests for service action readiness checks."""

    def test_should_block_action_when_service_not_found(self, mocker):
        """Test action readiness fails when systemd service is missing."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="LoadState=not-found\nActiveState=inactive\nSubState=dead\n",
        )

        monitor = ServiceMonitor({"enabled": True})
        ready, reason = monitor._check_action_readiness({"service_name": "ghost"})

        assert ready is False
        assert reason == "Service not found"

    def test_should_block_action_when_service_restarting(self, mocker):
        """Test action readiness fails when service is restarting."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="LoadState=loaded\nActiveState=activating\nSubState=auto-restart\n",
        )

        monitor = ServiceMonitor({"enabled": True})
        ready, reason = monitor._check_action_readiness({"service_name": "nginx"})

        assert ready is False
        assert reason == "Service is restarting"

    def test_should_allow_action_when_no_systemd_target(self):
        """Test readiness passes when no systemd info provided."""
        monitor = ServiceMonitor({"enabled": True})
        ready, reason = monitor._check_action_readiness({"name": "custom"})

        assert ready is True
        assert reason == "Action allowed"

    def test_should_block_action_when_service_restarting_with_mock(self, mocker):
        """Test readiness fails when _check_systemd_state reports restarting."""
        monitor = ServiceMonitor({"enabled": True})
        mocker.patch.object(
            ServiceMonitor, "_check_systemd_state", return_value=(True, True)
        )

        ready, reason = monitor._check_action_readiness({"service_name": "nginx"})

        assert ready is False
        assert reason == "Service is restarting"


class TestServiceMonitorActionCooldown:
    """Tests for action cooldown handling."""

    def test_should_allow_action_when_cooldown_not_configured(self):
        """Test action cooldown returns True when not configured."""
        monitor = ServiceMonitor({"enabled": True})

        assert monitor._check_action_cooldown("nginx", {}) is True


class TestServiceMonitorSystemdState:
    """Tests for systemd state checks."""

    def test_should_return_false_when_pattern_command_fails(self, mocker):
        """Test systemd state returns False when list-units fails."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        monitor = ServiceMonitor({"enabled": True})

        assert monitor._check_systemd_state(None, "nginx") == (False, False)

    def test_should_detect_restarting_when_pattern_active_state(self, mocker):
        """Test systemd pattern detects restarting based on active state."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="invalid\nnginx.service loaded activating start Nginx\n",
        )

        monitor = ServiceMonitor({"enabled": True})

        assert monitor._check_systemd_state(None, "nginx\\.service") == (True, True)

    def test_should_detect_restarting_when_pattern_sub_state(self, mocker):
        """Test systemd pattern detects restarting based on sub state."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="nginx.service loaded active auto-restart Nginx\n",
        )

        monitor = ServiceMonitor({"enabled": True})

        assert monitor._check_systemd_state(None, "nginx\\.service") == (True, True)

    def test_should_return_false_when_pattern_has_no_match(self, mocker):
        """Test systemd pattern returns False when no units match."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="other.service loaded active running Other\n",
        )

        monitor = ServiceMonitor({"enabled": True})

        assert monitor._check_systemd_state(None, "nginx") == (False, False)

    def test_should_return_false_when_service_name_missing(self):
        """Test systemd state returns False when no service name is provided."""
        monitor = ServiceMonitor({"enabled": True})

        assert monitor._check_systemd_state(None, None) == (False, False)

    def test_should_return_false_when_show_command_fails(self, mocker):
        """Test systemd state returns False when show command fails."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        monitor = ServiceMonitor({"enabled": True})

        assert monitor._check_systemd_state("nginx", None) == (False, False)

    def test_should_parse_show_output_states(self, mocker):
        """Test systemd show output parsing for restarting services."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "LoadState=loaded\n"
                "ActiveState=activating\n"
                "SubState=auto-restart\n"
            ),
        )

        monitor = ServiceMonitor({"enabled": True})

        assert monitor._check_systemd_state("nginx", None) == (True, True)

    def test_should_handle_systemd_state_exception(self, mocker):
        """Test systemd state handles unexpected exceptions."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = OSError("boom")

        monitor = ServiceMonitor({"enabled": True})

        assert monitor._check_systemd_state("nginx", None) == (False, False)


class TestServiceMonitorNotifications:
    """Tests for pre-action notifications."""

    def test_should_send_pre_action_notification(self, mocker):
        """Test pre-action notification is sent when manager is available."""
        notification_manager = mocker.Mock()
        notification_manager.notify_event.return_value = True

        monitor = ServiceMonitor({"enabled": True}, notification_manager=notification_manager)
        service_config = {
            "name": "nginx",
            "restart_command": "systemctl restart nginx",
        }
        status = {"check_method": "systemctl", "message": "Inactive"}

        monitor._notify_pre_action(service_config, status)

        notification_manager.notify_event.assert_called_once()


class TestServiceMonitorRestartLogic:
    """Tests for service restart logic."""

    def test_should_restart_service_on_failure(self, mocker):
        """Test that service is restarted when it fails."""
        mock_systemctl_check = mocker.patch.object(ServiceMonitor, "_check_systemctl")
        mock_systemctl_check.return_value = False

        mocker.patch.object(
            ServiceMonitor, "_check_action_readiness", return_value=(True, "Action allowed")
        )

        mock_restart = mocker.patch.object(ServiceMonitor, "_restart_service")
        mock_restart.return_value = True

        config = {
            "enabled": True,
            "action_on_failure": "restart_and_notify",
            "services": [
                {
                    "name": "nginx",
                    "enabled": True,
                    "check_method": "systemctl",
                    "service_name": "nginx",
                }
            ],
        }

        monitor = ServiceMonitor(config)
        results = monitor.check_all_services()

        assert len(results) == 1
        assert results[0]["running"] is False
        mock_restart.assert_called_once()

    def test_should_not_restart_when_action_is_notify_only(self, mocker):
        """Test that service is not restarted when action is notify only."""
        mock_systemctl_check = mocker.patch.object(ServiceMonitor, "_check_systemctl")
        mock_systemctl_check.return_value = False

        mocker.patch.object(
            ServiceMonitor, "_check_action_readiness", return_value=(True, "Action allowed")
        )

        mock_restart = mocker.patch.object(ServiceMonitor, "_restart_service")

        config = {
            "enabled": True,
            "action_on_failure": "notify_only",
            "services": [
                {
                    "name": "nginx",
                    "enabled": True,
                    "check_method": "systemctl",
                    "service_name": "nginx",
                }
            ],
        }

        monitor = ServiceMonitor(config)
        monitor.check_all_services()

        mock_restart.assert_not_called()

    def test_should_respect_cooldown_period(self, mocker, freezer):
        """Test that cooldown period is respected between restarts."""
        mock_restart = mocker.patch.object(ServiceMonitor, "_restart_service")
        mock_restart.return_value = True

        mocker.patch.object(
            ServiceMonitor, "_check_action_readiness", return_value=(True, "Action allowed")
        )

        config = {
            "enabled": True,
            "action_on_failure": "restart_and_notify",
            "restart_cooldown": 300,  # 5 minutes
        }

        monitor = ServiceMonitor(config)
        service_config = {"name": "nginx", "service_name": "nginx"}

        # First restart
        monitor._handle_service_failure(service_config, {"running": False})
        assert mock_restart.call_count == 1

        # Immediate second attempt - should be blocked by cooldown
        monitor._handle_service_failure(service_config, {"running": False})
        assert mock_restart.call_count == 1  # Still 1, not increased

        # Manually adjust cooldown to simulate time passing
        monitor.cooldown_tracker["nginx"] = time.time() - 301

        # Third attempt - should succeed
        monitor._handle_service_failure(service_config, {"running": False})
        assert mock_restart.call_count == 2

    def test_should_respect_action_cooldown(self, mocker):
        """Test action cooldown prevents rapid recovery actions."""
        mock_restart = mocker.patch.object(ServiceMonitor, "_restart_service")
        mock_restart.return_value = True

        mocker.patch.object(
            ServiceMonitor, "_check_action_readiness", return_value=(True, "Action allowed")
        )

        config = {
            "enabled": True,
            "action_on_failure": "restart_and_notify",
            "action_cooldown": {"value": 5, "unit": "minutes"},
        }

        monitor = ServiceMonitor(config)
        service_config = {"name": "nginx", "service_name": "nginx"}
        monitor.action_cooldown_tracker["nginx"] = time.time()

        result = monitor._handle_service_failure(service_config, {"running": False})

        assert result["action"] == "recovery_skipped"
        mock_restart.assert_not_called()

    def test_should_increment_restart_attempts(self):
        """Test restart attempt counter increments correctly."""
        monitor = ServiceMonitor({"enabled": True})

        monitor._increment_restart_attempts("nginx")
        monitor._increment_restart_attempts("nginx")

        assert monitor.restart_history["nginx"]["count"] == 2

    def test_should_track_restart_history(self, mocker):
        """Test that restart attempts are tracked in history."""
        mock_restart = mocker.patch.object(ServiceMonitor, "_restart_service")
        mock_restart.return_value = True

        mocker.patch.object(
            ServiceMonitor, "_check_action_readiness", return_value=(True, "Action allowed")
        )

        config = {
            "enabled": True,
            "action_on_failure": "restart_and_notify",
            "restart_cooldown": 0,  # No cooldown for this test
        }

        monitor = ServiceMonitor(config)
        service_config = {"name": "nginx", "service_name": "nginx"}

        # Perform multiple restarts
        for _ in range(3):
            monitor._handle_service_failure(service_config, {"running": False})
            time.sleep(0.1)  # Small delay to ensure different timestamps

        # Check history
        assert "nginx" in monitor.restart_history
        assert len(monitor.restart_history["nginx"]) >= 1

    def test_should_limit_max_restart_attempts(self, mocker):
        """Test that maximum restart attempts are enforced."""
        mock_restart = mocker.patch.object(ServiceMonitor, "_restart_service")
        mock_restart.return_value = False  # Restart fails

        mocker.patch.object(
            ServiceMonitor, "_check_action_readiness", return_value=(True, "Action allowed")
        )

        config = {
            "enabled": True,
            "action_on_failure": "restart_and_notify",
            "max_restart_attempts": 3,
            "restart_cooldown": 0,
        }

        monitor = ServiceMonitor(config)
        service_config = {"name": "nginx", "service_name": "nginx"}

        # Attempt restarts up to the limit
        for i in range(5):
            monitor._handle_service_failure(service_config, {"running": False})

        # Should not exceed max attempts
        assert mock_restart.call_count <= 3

    def test_should_reset_restart_attempts_after_window(self, mocker):
        """Test restart attempts reset after window passes."""
        monitor = ServiceMonitor({"enabled": True, "max_restart_attempts": 1})

        now = time.time()
        monitor.restart_history["nginx"] = {"count": 2, "first_attempt": now - 4000}

        assert monitor._check_restart_attempts("nginx") is True
        assert monitor.restart_history["nginx"]["count"] == 0

    def test_should_restart_service_with_hooks(self, mocker):
        """Test restart service executes hooks and verifies status."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="active\n")
        mocker.patch("time.sleep")

        monitor = ServiceMonitor({"enabled": True, "restart_wait_time": 0})

        service_config = {
            "name": "nginx",
            "restart_command": "systemctl restart nginx",
            "pre_restart_hook": "echo pre",
            "post_restart_hook": "echo post",
            "check_method": "systemctl",
            "service_name": "nginx",
        }

        mocker.patch.object(monitor, "_check_service", return_value={"running": True})

        assert monitor._restart_service(service_config) is True

        assert mock_run.call_count >= 2

    def test_should_execute_restart_command_sequence(self, mocker):
        """Test restart executes a list of commands sequentially."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        mocker.patch("time.sleep")

        monitor = ServiceMonitor({"enabled": True, "restart_wait_time": 0})
        service_config = {
            "name": "nginx",
            "restart_command": [
                "systemctl restart nginx",
                "bash /opt/xnetvn_monitord/scripts/custom-restart.sh",
            ],
            "check_method": "systemctl",
            "service_name": "nginx",
        }

        mocker.patch.object(monitor, "_check_service", return_value={"running": True})

        assert monitor._restart_service(service_config) is True

        mock_run.assert_has_calls(
            [
                call(
                    "systemctl restart nginx",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                ),
                call(
                    "bash /opt/xnetvn_monitord/scripts/custom-restart.sh",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                ),
            ],
            any_order=False,
        )

    def test_should_execute_post_restart_hook_and_check_status(self, mocker):
        """Test post-restart hook execution and status verification."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="active\n")
        mocker.patch("time.sleep")

        monitor = ServiceMonitor({"enabled": True, "restart_wait_time": 0})

        service_config = {
            "name": "nginx",
            "restart_command": "systemctl restart nginx",
            "post_restart_hook": "echo post",
            "check_method": "systemctl",
            "service_name": "nginx",
        }

        mocker.patch.object(monitor, "_check_service", return_value={"running": True})

        assert monitor._restart_service(service_config) is True
        assert mock_run.call_count >= 2


class TestServiceMonitorFailureHandling:
    """Tests for service failure handling paths."""

    def test_should_return_recovery_blocked_when_action_not_ready(self, mocker):
        """Test failure handling returns recovery_blocked when not ready."""
        monitor = ServiceMonitor({"enabled": True, "action_on_failure": "restart"})
        mocker.patch.object(ServiceMonitor, "_check_action_cooldown", return_value=True)
        mocker.patch.object(
            ServiceMonitor, "_check_action_readiness", return_value=(False, "Service not found")
        )

        result = monitor._handle_service_failure({"name": "nginx"}, {"message": "down"})

        assert result["action"] == "recovery_blocked"
        assert result["message"] == "Service not found"

    def test_should_return_action_result_when_restart_succeeds(self, mocker):
        """Test failure handling returns action result on restart success."""
        monitor = ServiceMonitor({"enabled": True, "action_on_failure": "restart"})
        mocker.patch.object(ServiceMonitor, "_check_action_cooldown", return_value=True)
        mocker.patch.object(
            ServiceMonitor, "_check_action_readiness", return_value=(True, "Action allowed")
        )
        mocker.patch.object(ServiceMonitor, "_check_restart_attempts", return_value=True)
        mocker.patch.object(ServiceMonitor, "_check_cooldown", return_value=True)
        mocker.patch.object(ServiceMonitor, "_restart_service", return_value=True)
        mocker.patch.object(ServiceMonitor, "_update_cooldown")
        mocker.patch.object(ServiceMonitor, "_update_action_cooldown")
        mocker.patch.object(ServiceMonitor, "_notify_pre_action")

        status = {"message": "down"}
        service_config = {"name": "nginx", "restart_command": "systemctl restart nginx"}

        result = monitor._handle_service_failure(service_config, status)

        assert result["action"] == "restart_service"
        assert result["success"] is True
        assert status["action_taken"] == "restart_attempted"


class TestServiceMonitorErrorHandling:
    """Tests for error handling scenarios."""

    def test_should_handle_restart_command_failure(self, mocker):
        """Test handling when restart command fails."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl")

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        service_config = {"service_name": "nginx", "restart_method": "systemctl"}

        result = monitor._restart_service(service_config)

        assert result is False

    def test_should_handle_permission_denied_restart(self, mocker):
        """Test handling when restart is denied due to permissions."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = PermissionError("Permission denied")

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        service_config = {"service_name": "nginx", "restart_method": "systemctl"}

        result = monitor._restart_service(service_config)

        assert result is False

    def test_should_return_false_when_restart_command_missing(self):
        """Test restart returns False when restart command is missing."""
        monitor = ServiceMonitor({"enabled": True})

        assert monitor._restart_service({"name": "nginx"}) is False

    def test_should_handle_restart_timeout(self, mocker):
        """Test restart timeout handling."""
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="systemctl", timeout=60),
        )

        monitor = ServiceMonitor({"enabled": True})
        service_config = {"name": "nginx", "restart_command": "systemctl restart nginx"}

        assert monitor._restart_service(service_config) is False

    def test_should_handle_restart_unexpected_exception(self, mocker):
        """Test restart handles unexpected exceptions."""
        mocker.patch("subprocess.run", side_effect=RuntimeError("boom"))

        monitor = ServiceMonitor({"enabled": True})
        service_config = {"name": "nginx", "restart_command": "systemctl restart nginx"}

        assert monitor._restart_service(service_config) is False

    def test_should_handle_service_name_special_chars(self, mocker):
        """Test handling service names with special characters."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="active\n")

        config = {"enabled": True}
        monitor = ServiceMonitor(config)

        # Service name with special characters
        service_config = {
            "name": "my-service@instance.service",
            "check_method": "systemctl",
            "service_name": "my-service@instance.service",
        }

        result = monitor._check_systemctl(service_config)

        assert result is True
        # Verify the exact service name was used
        call_args = mock_run.call_args[0][0]
        assert "my-service@instance.service" in call_args


class TestServiceMonitorMaintenance:
    """Tests for maintenance helpers."""

    def test_should_reset_restart_history(self):
        """Test reset of restart tracking structures."""
        monitor = ServiceMonitor({"enabled": True})
        monitor.restart_history["nginx"] = {"count": 1, "first_attempt": time.time()}
        monitor.cooldown_tracker["nginx"] = time.time()

        monitor.reset_restart_history()

        assert monitor.restart_history == {}
        assert monitor.cooldown_tracker == {}
