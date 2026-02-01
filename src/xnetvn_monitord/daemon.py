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

"""Main daemon module.

This is the main entry point for the xNetVN Monitor Daemon.
"""

import logging
import logging.handlers
import os
import signal
import sys
import time
from pathlib import Path
from typing import Dict, Optional

from .monitors import ResourceMonitor, ServiceMonitor
from .notifiers import NotificationManager
from .utils import ConfigLoader, UpdateChecker, load_env_file

logger = logging.getLogger(__name__)

UPDATE_CONFIG_DOC_URL = (
    "https://github.com/xnetvn-com/xnetvn_monitord/blob/main/docs/vi/ENVIRONMENT.md"
)


class MonitorDaemon:
    """Main monitoring daemon class."""

    def __init__(self, config_path: str):
        """Initialize the monitor daemon.

        Args:
            config_path: Path to configuration file.
        """
        self.config_path = config_path
        self.config_loader = ConfigLoader(config_path)
        self.config = {}
        self.running = False
        self.service_monitor: Optional[ServiceMonitor] = None
        self.resource_monitor: Optional[ResourceMonitor] = None
        self.notification_manager: Optional[NotificationManager] = None

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGHUP, self._reload_config)

    def initialize(self) -> None:
        """Initialize the daemon components."""
        # Load configuration
        self.config = self.config_loader.load()

        # Setup logging
        self._setup_logging()

        logger.info("=" * 80)
        logger.info("xNetVN Monitor Daemon starting...")
        logger.info(f"Version: {self.config['general']['app_version']}")
        logger.info(f"Config file: {self.config_path}")
        logger.info("=" * 80)

        # Initialize monitors
        service_config = self.config.get("service_monitor", {})
        self.service_monitor = ServiceMonitor(service_config)
        logger.info(f"Service monitor initialized (enabled: {service_config.get('enabled', True)})")

        resource_config = self.config.get("resource_monitor", {})
        self.resource_monitor = ResourceMonitor(resource_config)
        logger.info(f"Resource monitor initialized (enabled: {resource_config.get('enabled', True)})")

        # Initialize notification manager
        notification_config = self.config.get("notifications", {})
        self.notification_manager = NotificationManager(notification_config)
        enabled_channels = self.notification_manager.get_enabled_channels()
        logger.info(f"Notification manager initialized (channels: {', '.join(enabled_channels) if enabled_channels else 'none'})")

        if self.service_monitor:
            self.service_monitor.notification_manager = self.notification_manager

        # Test notification channels
        if enabled_channels:
            logger.info("Testing notification channels...")
            test_results = self.notification_manager.test_all_channels()
            for channel, result in test_results.items():
                status = "OK" if result else "FAILED"
                logger.info(f"  {channel}: {status}")

        # Check for updates if enabled
        self._maybe_check_for_updates()

        # Create PID file
        pid_file = self.config["general"].get("pid_file", "/var/run/xnetvn_monitord.pid")
        self._create_pid_file(pid_file)

        logger.info("Daemon initialization completed")

    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        log_config = self.config["general"]["logging"]

        if not log_config.get("enabled", True):
            return

        # Get log file path
        log_file = log_config.get("file", "/var/log/xnetvn_monitord/monitor.log")
        log_dir = os.path.dirname(log_file)

        # Create log directory if not exists
        os.makedirs(log_dir, exist_ok=True)

        # Configure root logger
        log_level = getattr(logging, log_config.get("level", "INFO").upper())
        log_format = log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        # Setup file handler with rotation
        max_bytes = log_config.get("max_size_mb", 100) * 1024 * 1024
        backup_count = log_config.get("backup_count", 10)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format))

        # Setup console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(logging.Formatter(log_format))

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

    def _create_pid_file(self, pid_file: str) -> None:
        """Create PID file.

        Args:
            pid_file: Path to PID file.
        """
        try:
            pid_dir = os.path.dirname(pid_file)
            if pid_dir:
                os.makedirs(pid_dir, exist_ok=True)

            with open(pid_file, "w") as f:
                f.write(str(os.getpid()))
            logger.info(f"PID file created: {pid_file}")
        except Exception as e:
            logger.warning(f"Failed to create PID file: {str(e)}")

    def _remove_pid_file(self) -> None:
        """Remove PID file."""
        try:
            pid_file = self.config["general"].get("pid_file", "/var/run/xnetvn_monitord.pid")
            if os.path.exists(pid_file):
                os.remove(pid_file)
                logger.info(f"PID file removed: {pid_file}")
        except Exception as e:
            logger.warning(f"Failed to remove PID file: {str(e)}")

    def run(self) -> None:
        """Run the main monitoring loop."""
        self.running = True
        check_interval = self.config["general"].get("check_interval", 60)

        logger.info(f"Monitoring loop started (check interval: {check_interval}s)")

        try:
            while self.running:
                cycle_start = time.time()

                # Check services
                if self.service_monitor and self.service_monitor.enabled:
                    try:
                        service_results = self.service_monitor.check_all_services()
                        self._process_service_results(service_results)
                    except Exception as e:
                        logger.error(f"Error in service monitoring cycle: {str(e)}", exc_info=True)

                # Check resources
                if self.resource_monitor and self.resource_monitor.enabled:
                    try:
                        resource_results = self.resource_monitor.check_resources()
                        self._process_resource_results(resource_results)
                    except Exception as e:
                        logger.error(f"Error in resource monitoring cycle: {str(e)}", exc_info=True)

                # Calculate sleep time
                cycle_duration = time.time() - cycle_start
                sleep_time = max(0, check_interval - cycle_duration)

                if sleep_time > 0:
                    logger.debug(f"Monitoring cycle completed in {cycle_duration:.2f}s, sleeping for {sleep_time:.2f}s")
                    time.sleep(sleep_time)
                else:
                    logger.warning(f"Monitoring cycle took {cycle_duration:.2f}s, exceeding interval of {check_interval}s")

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
        except Exception as e:
            logger.error(f"Fatal error in monitoring loop: {str(e)}", exc_info=True)
        finally:
            self.shutdown()

    def _process_service_results(self, results: list) -> None:
        """Process service monitoring results.

        Args:
            results: List of service check results.
        """
        for result in results:
            service_name = result.get("name")
            running = result.get("running", False)
            action_taken = result.get("action_taken")

            if not running:
                system_stats = self._get_system_stats()
                event_payload = {
                    "event_type": "service_down",
                    "timestamp": result.get("event_timestamp", time.time()),
                    "severity": "critical" if result.get("critical") else "high",
                    "service": {
                        "name": service_name,
                        "status": "down",
                        "check_method": result.get("check_method", "unknown"),
                        "message": result.get("message", "N/A"),
                        "description": result.get("description", ""),
                        "critical": result.get("critical", False),
                    },
                    "details": result.get("message", "N/A"),
                    "system_stats": system_stats,
                }

                if self.notification_manager:
                    self.notification_manager.notify_event(event_payload)

                if action_taken:
                    action_result = result.get("action_result", {})
                    restart_success = result.get("restart_success", False)
                    status = "restarted" if restart_success else "failed"
                    action_payload = {
                        "event_type": "service_recovery",
                        "timestamp": action_result.get("timestamp", time.time()),
                        "severity": "info" if restart_success else "high",
                        "service": {
                            "name": service_name,
                            "status": status,
                            "check_method": result.get("check_method", "unknown"),
                            "message": result.get("message", "N/A"),
                        },
                        "action": action_result,
                        "details": action_result.get("message", ""),
                        "system_stats": self._get_system_stats(),
                    }

                    if self.notification_manager:
                        self.notification_manager.notify_action_result(action_payload)

    def _process_resource_results(self, results: dict) -> None:
        """Process resource monitoring results.

        Args:
            results: Resource check results dictionary.
        """
        actions_taken = results.get("actions_taken", [])
        action_results = results.get("action_results", [])

        if results.get("cpu_load") and results["cpu_load"].get("threshold_exceeded"):
            cpu_event = {
                "event_type": "resource_threshold",
                "timestamp": results.get("timestamp", time.time()),
                "severity": "high",
                "resource": {"type": "cpu", "details": results.get("cpu_load", {})},
                "details": "CPU load threshold exceeded",
                "system_stats": self._get_system_stats(),
            }
            if self.notification_manager:
                self.notification_manager.notify_event(cpu_event)

        if results.get("memory") and results["memory"].get("threshold_exceeded"):
            memory_event = {
                "event_type": "resource_threshold",
                "timestamp": results.get("timestamp", time.time()),
                "severity": "high",
                "resource": {"type": "memory", "details": results.get("memory", {})},
                "details": "Memory threshold exceeded",
                "system_stats": self._get_system_stats(),
            }
            if self.notification_manager:
                self.notification_manager.notify_event(memory_event)

        if results.get("disk") and results["disk"].get("threshold_exceeded"):
            disk_event = {
                "event_type": "resource_threshold",
                "timestamp": results.get("timestamp", time.time()),
                "severity": "high",
                "resource": {"type": "disk", "details": results.get("disk", {})},
                "details": "Disk threshold exceeded",
                "system_stats": self._get_system_stats(),
            }
            if self.notification_manager:
                self.notification_manager.notify_event(disk_event)

        if action_results:
            for action_result in action_results:
                action_payload = {
                    "event_type": "resource_recovery",
                    "timestamp": action_result.get("timestamp", time.time()),
                    "severity": "info" if action_result.get("success") else "high",
                    "action": action_result,
                    "details": action_result.get("action", "resource_recovery"),
                    "system_stats": self._get_system_stats(),
                }
                if self.notification_manager:
                    self.notification_manager.notify_action_result(action_payload)

        if actions_taken and not action_results:
            logger.debug("Resource recovery actions executed without detailed results")

    def _get_system_stats(self) -> Dict:
        """Get current system statistics for reporting.

        Returns:
            Dictionary containing system statistics.
        """
        if not self.resource_monitor:
            return {}

        try:
            return self.resource_monitor.get_current_stats()
        except Exception as e:
            logger.error("Failed to collect system stats: %s", str(e))
            return {}

    def _signal_handler(self, signum, frame) -> None:
        """Handle system signals.

        Args:
            signum: Signal number.
            frame: Current stack frame.
        """
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.running = False

    def _reload_config(self, signum, frame) -> None:
        """Reload configuration on SIGHUP.

        Args:
            signum: Signal number.
            frame: Current stack frame.
        """
        logger.info("Received SIGHUP, reloading configuration...")
        try:
            self.config = self.config_loader.reload()
            logger.info("Configuration reloaded successfully")

            # Reinitialize components
            if self.service_monitor:
                service_config = self.config.get("service_monitor", {})
                self.service_monitor.config = service_config
                self.service_monitor.enabled = service_config.get("enabled", True)

            if self.resource_monitor:
                resource_config = self.config.get("resource_monitor", {})
                self.resource_monitor.config = resource_config
                self.resource_monitor.enabled = resource_config.get("enabled", True)

            if self.notification_manager:
                notification_config = self.config.get("notifications", {})
                self.notification_manager = NotificationManager(notification_config)

            if self.service_monitor:
                self.service_monitor.notification_manager = self.notification_manager

        except Exception as e:
            logger.error(f"Failed to reload configuration: {str(e)}", exc_info=True)

    def _maybe_check_for_updates(self) -> None:
        """Check for updates based on configuration."""
        update_config = self.config.get("update_checker", {})
        if not update_config.get("enabled", True):
            logger.info("Update checker is disabled")
            return

        current_version = self.config.get("general", {}).get("app_version", "0.0.0")
        work_dir = Path(self.config.get("general", {}).get("work_dir", "/opt/xnetvn_monitord"))
        checker = UpdateChecker(update_config, current_version, work_dir)
        result = checker.check_for_updates()

        if not result.checked:
            logger.debug(result.message)
            return

        if result.update_available:
            logger.info(
                "New version available: %s (current: %s)",
                result.latest_version,
                result.current_version,
            )
            if update_config.get("notify_on_update", False) and self.notification_manager:
                message_lines = [
                    f"Current version: {result.current_version}",
                    f"Latest version: {result.latest_version}",
                ]
                if result.release_url:
                    message_lines.append(f"Release notes: {result.release_url}")
                message_lines.append(
                    "Review configuration changes: "
                    f"{UPDATE_CONFIG_DOC_URL}"
                )
                message = "\n".join(message_lines)
                self.notification_manager.notify_custom_message(
                    subject="xnetvn_monitord update available",
                    message=message,
                )

            if update_config.get("auto_update", False) and result.tarball_url:
                logger.warning("Auto update is enabled; applying update...")
                if checker.apply_update(result.tarball_url):
                    service_name = update_config.get(
                        "service_name", "xnetvn_monitord"
                    )
                    checker.restart_service(service_name)
        else:
            logger.info("Update check completed: %s", result.message)

    def shutdown(self) -> None:
        """Shutdown the daemon gracefully."""
        logger.info("Shutting down daemon...")
        self.running = False
        self._remove_pid_file()
        logger.info("Daemon shutdown completed")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: xnetvn_monitord <config_file>")
        sys.exit(1)

    load_env_file("/opt/xnetvn_monitord/config/.env")

    config_path = sys.argv[1]

    if not os.path.exists(config_path):
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)

    try:
        daemon = MonitorDaemon(config_path)
        daemon.initialize()
        daemon.run()
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
