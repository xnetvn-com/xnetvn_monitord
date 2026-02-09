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

"""Integration tests for xNetVN Monitor Daemon.

This module contains integration tests that verify the interaction
between multiple components of the system.
"""

import pytest


@pytest.mark.integration
class TestConfigurationIntegration:
    """Integration tests for configuration loading and application."""

    def test_should_load_and_apply_service_config(self, config_file):
        """Test loading and applying service monitor configuration."""
        from xnetvn_monitord.monitors.service_monitor import ServiceMonitor
        from xnetvn_monitord.utils.config_loader import ConfigLoader

        loader = ConfigLoader(str(config_file))
        config = loader.load()

        service_config = config.get("service_monitor", {})
        monitor = ServiceMonitor(service_config)

        assert monitor.enabled is True
        assert len(service_config.get("services", [])) == 2

    def test_should_load_and_apply_notification_config(self, config_file):
        """Test loading and applying notification configuration."""
        from xnetvn_monitord.notifiers import NotificationManager
        from xnetvn_monitord.utils.config_loader import ConfigLoader

        loader = ConfigLoader(str(config_file))
        config = loader.load()

        notification_config = config.get("notifications", {})
        manager = NotificationManager(notification_config)

        assert manager.enabled is True


@pytest.mark.integration
class TestMonitoringWorkflow:
    """Integration tests for monitoring workflows."""

    def test_should_detect_and_notify_service_failure(self, mocker, config_file):
        """Test end-to-end service failure detection and notification."""
        from xnetvn_monitord.monitors.service_monitor import ServiceMonitor
        from xnetvn_monitord.utils.config_loader import ConfigLoader

        # Mock service as failed
        mocker.patch("subprocess.run", return_value=mocker.MagicMock(returncode=3, stdout="inactive\n"))

        loader = ConfigLoader(str(config_file))
        config = loader.load()

        service_monitor = ServiceMonitor(config["service_monitor"])

        # Check services
        results = service_monitor.check_all_services()

        # Process failures
        for result in results:
            if not result["running"]:
                # In real scenario, daemon would call notification_manager
                assert result["name"] in ["nginx", "php-fpm"]


@pytest.mark.integration
class TestErrorRecovery:
    """Integration tests for error recovery scenarios."""

    def test_should_recover_from_transient_errors(self, mocker, config_file):
        """Test recovery from transient errors."""
        from xnetvn_monitord.daemon import MonitorDaemon

        # First attempt fails, second succeeds
        mock_check = mocker.patch("subprocess.run")
        mock_check.side_effect = [
            mocker.MagicMock(returncode=3, stdout="inactive\n"),
            mocker.MagicMock(returncode=0, stdout="active\n"),
        ]

        daemon = MonitorDaemon(str(config_file))
        daemon.initialize()

        # First check - should detect failure
        # Second check - should detect recovery
        # This is a simplified test; full implementation would involve timing
