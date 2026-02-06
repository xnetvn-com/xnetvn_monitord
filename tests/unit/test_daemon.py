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

"""Unit tests for MonitorDaemon."""

import logging
import sys

import pytest

from xnetvn_monitord.daemon import MonitorDaemon, main


def _build_minimal_config(tmp_path):
    return {
        "general": {
            "app_version": "1.0.0",
            "check_interval": 1,
            "pid_file": str(tmp_path / "xnetvn.pid"),
            "logging": {"enabled": False},
        },
        "service_monitor": {"enabled": True},
        "resource_monitor": {"enabled": True},
        "notifications": {"enabled": False},
    }


class TestMonitorDaemonInitialization:
    """Tests for daemon initialization."""

    def test_should_initialize_components(self, mocker, tmp_path):
        """Test initialization of monitors and notification manager."""
        config = _build_minimal_config(tmp_path)

        mocker.patch("xnetvn_monitord.daemon.ConfigLoader.load", return_value=config)
        mocker.patch("xnetvn_monitord.daemon.ServiceMonitor")
        mocker.patch("xnetvn_monitord.daemon.ResourceMonitor")
        manager_mock = mocker.patch("xnetvn_monitord.daemon.NotificationManager")

        manager_instance = manager_mock.return_value
        manager_instance.get_enabled_channels.return_value = []

        daemon = MonitorDaemon("/tmp/config.yaml")
        mocker.patch.object(daemon, "_create_pid_file")

        daemon.initialize()

        assert daemon.config == config
        manager_instance.get_enabled_channels.assert_called_once()
        daemon._create_pid_file.assert_called_once()

    def test_should_test_channels_when_enabled(self, mocker, tmp_path):
        """Test notification channel testing when enabled."""
        config = _build_minimal_config(tmp_path)

        mocker.patch("xnetvn_monitord.daemon.ConfigLoader.load", return_value=config)
        mocker.patch("xnetvn_monitord.daemon.ServiceMonitor")
        mocker.patch("xnetvn_monitord.daemon.ResourceMonitor")
        manager_mock = mocker.patch("xnetvn_monitord.daemon.NotificationManager")

        manager_instance = manager_mock.return_value
        manager_instance.get_enabled_channels.return_value = ["email"]
        manager_instance.test_all_channels.return_value = {"email": True}

        daemon = MonitorDaemon("/tmp/config.yaml")
        mocker.patch.object(daemon, "_create_pid_file")

        daemon.initialize()

        manager_instance.test_all_channels.assert_called_once()


class TestMonitorDaemonLogging:
    """Tests for logging configuration."""

    def test_should_configure_logging_handlers(self, mocker, tmp_path):
        """Test logging setup adds handlers when enabled."""
        config = _build_minimal_config(tmp_path)
        config["general"]["logging"] = {
            "enabled": True,
            "level": "INFO",
            "file": str(tmp_path / "monitor.log"),
        }

        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.config = config

        mocker.patch("xnetvn_monitord.daemon.logging.handlers.RotatingFileHandler")
        mocker.patch("xnetvn_monitord.daemon.logging.StreamHandler")
        mocker.patch("os.makedirs")

        root_logger = logging.getLogger()
        original_handlers = list(root_logger.handlers)

        try:
            daemon._setup_logging()
            assert len(root_logger.handlers) >= len(original_handlers)
        finally:
            for handler in list(root_logger.handlers):
                if handler not in original_handlers:
                    root_logger.removeHandler(handler)

    def test_should_skip_logging_setup_when_disabled(self, mocker, tmp_path):
        """Test logging setup returns when disabled."""
        config = _build_minimal_config(tmp_path)
        config["general"]["logging"]["enabled"] = False

        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.config = config

        makedirs_mock = mocker.patch("os.makedirs")

        daemon._setup_logging()

        makedirs_mock.assert_not_called()


class TestMonitorDaemonRunLoop:
    """Tests for monitoring loop."""

    def test_should_process_service_and_resource_results(self, mocker, tmp_path):
        """Test monitoring loop processes results once."""
        config = _build_minimal_config(tmp_path)

        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.config = config

        daemon.service_monitor = mocker.Mock()
        daemon.service_monitor.enabled = True
        daemon.service_monitor.check_all_services.return_value = [{"name": "nginx"}]

        daemon.resource_monitor = mocker.Mock()
        daemon.resource_monitor.enabled = True
        daemon.resource_monitor.check_resources.return_value = {"actions_taken": []}

        mocker.patch.object(daemon, "_process_service_results")
        mocker.patch.object(daemon, "_process_resource_results")

        def stop_after_sleep(_):
            daemon.running = False

        mocker.patch("time.sleep", side_effect=stop_after_sleep)
        mocker.patch("time.time", return_value=0.0)

        daemon.run()

        daemon._process_service_results.assert_called_once()
        daemon._process_resource_results.assert_called_once()

    def test_should_log_warning_when_cycle_exceeds_interval(self, mocker, tmp_path):
        """Test warning logged when cycle exceeds interval."""
        config = _build_minimal_config(tmp_path)
        config["general"]["check_interval"] = 1

        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.config = config

        daemon.service_monitor = mocker.Mock()
        daemon.service_monitor.enabled = True
        daemon.service_monitor.check_all_services.return_value = []

        daemon.resource_monitor = mocker.Mock()
        daemon.resource_monitor.enabled = False

        def stop_after_process(_):
            daemon.running = False

        mocker.patch.object(daemon, "_process_service_results", side_effect=stop_after_process)
        mocker.patch("xnetvn_monitord.daemon.logger.info")
        mocker.patch("xnetvn_monitord.daemon.logger.debug")
        warning_mock = mocker.patch("xnetvn_monitord.daemon.logger.warning")

        times = iter([0.0, 5.0])
        mocker.patch("xnetvn_monitord.daemon.time.time", side_effect=times)

        daemon.run()

        warning_mock.assert_called()

    def test_should_return_empty_stats_when_no_resource_monitor(self):
        """Test system stats returns empty dict when monitor missing."""
        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.resource_monitor = None

        assert daemon._get_system_stats() == {}

    def test_should_handle_system_stats_exception(self, mocker):
        """Test system stats handles monitor exceptions."""
        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.resource_monitor = mocker.Mock()
        daemon.resource_monitor.get_current_stats.side_effect = RuntimeError("boom")

        assert daemon._get_system_stats() == {}

    def test_should_log_debug_when_actions_taken_without_results(self, mocker):
        """Test resource results log debug when actions lack details."""
        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.notification_manager = None
        debug_mock = mocker.patch("xnetvn_monitord.daemon.logger.debug")

        results = {"actions_taken": ["low_memory_recovery"], "action_results": []}

        daemon._process_resource_results(results)
        debug_mock.assert_called()

    def test_should_handle_service_monitor_exception(self, mocker, tmp_path):
        """Test run loop handles service monitor exceptions."""
        config = _build_minimal_config(tmp_path)

        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.config = config

        daemon.service_monitor = mocker.Mock()
        daemon.service_monitor.enabled = True
        daemon.service_monitor.check_all_services.side_effect = RuntimeError("boom")

        daemon.resource_monitor = mocker.Mock()
        daemon.resource_monitor.enabled = True
        daemon.resource_monitor.check_resources.return_value = {"actions_taken": []}

        def stop_after_sleep(_):
            daemon.running = False

        mocker.patch("time.sleep", side_effect=stop_after_sleep)
        mocker.patch("xnetvn_monitord.daemon.time.time", return_value=0.0)

        daemon.run()

    def test_should_handle_resource_monitor_exception(self, mocker, tmp_path):
        """Test run loop handles resource monitor exceptions."""
        config = _build_minimal_config(tmp_path)

        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.config = config

        daemon.service_monitor = mocker.Mock()
        daemon.service_monitor.enabled = False

        daemon.resource_monitor = mocker.Mock()
        daemon.resource_monitor.enabled = True
        daemon.resource_monitor.check_resources.side_effect = RuntimeError("boom")

        error_mock = mocker.patch("xnetvn_monitord.daemon.logger.error")

        def stop_after_sleep(_):
            daemon.running = False

        mocker.patch("time.sleep", side_effect=stop_after_sleep)
        mocker.patch("xnetvn_monitord.daemon.time.time", return_value=0.0)

        daemon.run()

        error_mock.assert_called()

    def test_should_handle_keyboard_interrupt(self, mocker, tmp_path):
        """Test run loop handles KeyboardInterrupt."""
        config = _build_minimal_config(tmp_path)

        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.config = config

        daemon.service_monitor = mocker.Mock()
        daemon.service_monitor.enabled = False

        daemon.resource_monitor = mocker.Mock()
        daemon.resource_monitor.enabled = False

        mocker.patch("time.sleep", side_effect=KeyboardInterrupt)
        mocker.patch("xnetvn_monitord.daemon.time.time", return_value=0.0)
        shutdown_mock = mocker.patch.object(daemon, "shutdown")

        daemon.run()

        shutdown_mock.assert_called_once()


class TestMonitorDaemonProcessing:
    """Tests for result processing methods."""

    def test_should_notify_on_service_failure(self, mocker):
        """Test service failure notification."""
        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.notification_manager = mocker.Mock()
        daemon.resource_monitor = mocker.Mock()
        daemon.resource_monitor.get_current_stats.return_value = {}

        results = [
            {
                "name": "nginx",
                "running": False,
                "action_taken": "restart_attempted",
                "restart_success": True,
                "action_result": {"action": "restart_service", "success": True},
                "event_timestamp": 1700000000.0,
                "critical": True,
                "check_method": "systemctl",
                "message": "Inactive",
            }
        ]

        daemon._process_service_results(results)

        daemon.notification_manager.notify_event.assert_called_once()
        daemon.notification_manager.notify_action_result.assert_called_once()

    def test_should_skip_notifications_when_service_running(self, mocker):
        """Test no notifications when service is running."""
        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.notification_manager = mocker.Mock()

        results = [{"name": "nginx", "running": True}]

        daemon._process_service_results(results)

        daemon.notification_manager.notify_event.assert_not_called()
        daemon.notification_manager.notify_action_result.assert_not_called()

    def test_should_notify_on_resource_actions(self, mocker):
        """Test resource alert notifications."""
        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.notification_manager = mocker.Mock()
        daemon.resource_monitor = mocker.Mock()
        daemon.resource_monitor.get_current_stats.return_value = {}

        results = {
            "actions_taken": [
                "high_cpu_recovery",
                "low_memory_recovery",
                "low_disk_recovery",
            ],
            "action_results": [
                {"action": "high_cpu_recovery", "success": True},
                {"action": "low_memory_recovery", "success": True},
                {"action": "low_disk_recovery", "success": True},
            ],
            "cpu_load": {"threshold_exceeded": True, "load": 10},
            "memory": {"threshold_exceeded": True, "free": 1},
            "disk": {"threshold_exceeded": True, "free": 2},
        }

        daemon._process_resource_results(results)

        assert daemon.notification_manager.notify_event.call_count == 3
        assert daemon.notification_manager.notify_action_result.call_count == 3

    def test_signal_handler_stops_running(self):
        """Test signal handler stops the daemon."""
        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.running = True

        daemon._signal_handler(15, None)

        assert daemon.running is False


class TestMonitorDaemonReload:
    """Tests for configuration reload handling."""

    def test_should_reload_configuration(self, mocker, tmp_path):
        """Test configuration reload updates components."""
        daemon = MonitorDaemon("/tmp/config.yaml")

        daemon.service_monitor = mocker.Mock()
        daemon.resource_monitor = mocker.Mock()

        new_config = _build_minimal_config(tmp_path)
        new_config["service_monitor"]["enabled"] = False
        new_config["resource_monitor"]["enabled"] = False

        mocker.patch.object(daemon.config_loader, "reload", return_value=new_config)

        daemon._reload_config(None, None)

        assert daemon.config == new_config
        assert daemon.service_monitor.enabled is False
        assert daemon.resource_monitor.enabled is False

    def test_should_handle_reload_failure(self, mocker):
        """Test reload handles exceptions gracefully."""
        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.config = {"general": {"check_interval": 1}}

        mocker.patch.object(daemon.config_loader, "reload", side_effect=RuntimeError("boom"))
        error_mock = mocker.patch("xnetvn_monitord.daemon.logger.error")

        daemon._reload_config(None, None)

        error_mock.assert_called()


class TestMonitorDaemonShutdown:
    """Tests for daemon shutdown."""

    def test_should_remove_pid_file_on_shutdown(self, mocker):
        """Test PID file removal on shutdown."""
        daemon = MonitorDaemon("/tmp/config.yaml")
        mocker.patch.object(daemon, "_remove_pid_file")

        daemon.shutdown()

        daemon._remove_pid_file.assert_called_once()


class TestMonitorDaemonPidFile:
    """Tests for PID file management."""

    def test_should_handle_pid_file_creation_error(self, mocker, tmp_path, caplog):
        """Test PID file creation error handling."""
        daemon = MonitorDaemon("/tmp/config.yaml")

        mocker.patch("builtins.open", side_effect=OSError("fail"))

        daemon._create_pid_file(str(tmp_path / "xnetvn.pid"))

        assert any("Failed to create PID file" in record.message for record in caplog.records)

    def test_should_remove_existing_pid_file(self, tmp_path):
        """Test PID file removal when file exists."""
        pid_path = tmp_path / "xnetvn.pid"
        pid_path.write_text("1234")

        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.config = {"general": {"pid_file": str(pid_path)}}

        daemon._remove_pid_file()

    def test_should_handle_pid_file_remove_error(self, mocker, tmp_path):
        """Test PID file removal handles errors."""
        pid_path = tmp_path / "xnetvn.pid"
        pid_path.write_text("1234")

        daemon = MonitorDaemon("/tmp/config.yaml")
        daemon.config = {"general": {"pid_file": str(pid_path)}}

        mocker.patch("os.remove", side_effect=OSError("fail"))
        warning_mock = mocker.patch("xnetvn_monitord.daemon.logger.warning")

        daemon._remove_pid_file()

        warning_mock.assert_called()


class TestMonitorDaemonMain:
    """Tests for daemon main entrypoint."""

    def test_should_exit_when_missing_arguments(self, monkeypatch, capsys):
        """Test main exits when config path missing."""
        monkeypatch.setattr(sys, "argv", ["xnetvn_monitord"])

        with pytest.raises(SystemExit):
            main()

        assert "Usage: xnetvn_monitord" in capsys.readouterr().out

    def test_should_exit_when_config_missing(self, monkeypatch, capsys):
        """Test main exits when config file does not exist."""
        monkeypatch.setattr(sys, "argv", ["xnetvn_monitord", "/missing.yaml"])
        monkeypatch.setattr("os.path.exists", lambda _: False)

        with pytest.raises(SystemExit):
            main()

        assert "Configuration file not found" in capsys.readouterr().out

    def test_should_exit_on_fatal_error(self, monkeypatch, capsys, mocker):
        """Test main exits on fatal errors during startup."""
        monkeypatch.setattr(sys, "argv", ["xnetvn_monitord", "/config.yaml"])
        monkeypatch.setattr("os.path.exists", lambda _: True)
        mocker.patch("xnetvn_monitord.daemon.MonitorDaemon", side_effect=RuntimeError("boom"))

        with pytest.raises(SystemExit):
            main()

        assert "Fatal error" in capsys.readouterr().out

    def test_should_run_daemon_when_config_exists(self, monkeypatch, mocker):
        """Test main initializes and runs daemon."""
        monkeypatch.setattr(sys, "argv", ["xnetvn_monitord", "/config.yaml"])
        monkeypatch.setattr("os.path.exists", lambda _: True)

        daemon_mock = mocker.patch("xnetvn_monitord.daemon.MonitorDaemon")
        daemon_instance = daemon_mock.return_value

        main()

        daemon_instance.initialize.assert_called_once()
        daemon_instance.run.assert_called_once()
