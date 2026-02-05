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

"""Service monitoring module.

This module provides functionality to monitor system services and automatically
restart them when they are not running properly.
"""

import logging
import re
import socket
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from xnetvn_monitord.notifiers import NotificationManager

from xnetvn_monitord.utils.service_manager import ServiceManager
from xnetvn_monitord.utils.network import force_ipv4


class ServiceMonitor:
    """Monitor and manage system services."""

    def __init__(
        self,
        config: Dict,
        notification_manager: Optional["NotificationManager"] = None,
        service_manager: Optional[ServiceManager] = None,
    ):
        """Initialize the service monitor.

        Args:
            config: Service monitoring configuration dictionary.
            notification_manager: Optional notification manager for pre-action alerts.
        """
        self.config = config
        self.notification_manager = notification_manager
        self.restart_history: Dict[str, Dict] = {}
        self.cooldown_tracker: Dict[str, float] = {}
        self.action_cooldown_tracker: Dict[str, float] = {}
        self.last_check_time: Dict[str, float] = {}
        self._regex_cache: Dict[Tuple[str, ...], List[re.Pattern]] = {}
        self.enabled = config.get("enabled", True)
        self.service_manager = service_manager or ServiceManager()
        self.only_ipv4 = config.get("only_ipv4", False)

    def check_all_services(self) -> List[Dict]:
        """Check all configured services.

        Returns:
            List of dictionaries containing service status and actions taken.
        """
        if not self.enabled:
            logger.debug("Service monitoring is disabled")
            return []

        results = []
        services = self.config.get("services", [])

        for service_config in services:
            if not service_config.get("enabled", True):
                continue

            if not self._should_check_service(service_config):
                continue

            service_name = service_config.get("name")
            logger.debug(f"Checking service: {service_name}")

            try:
                status = self._check_service(service_config)
                status["critical"] = service_config.get("critical", False)
                status["description"] = service_config.get("description", "")
                results.append(status)

                if not status["running"]:
                    status["event_timestamp"] = time.time()
                    logger.warning(
                        f"Service {service_name} is not running: {status['message']}"
                    )
                    action_result = self._handle_service_failure(service_config, status)
                    if action_result:
                        status["action_result"] = action_result
                else:
                    logger.debug(f"Service {service_name} is running normally")

            except Exception as e:
                logger.error(
                    f"Error checking service {service_name}: {str(e)}", exc_info=True
                )
                results.append(
                    {
                        "name": service_name,
                        "running": False,
                        "error": str(e),
                        "action_taken": None,
                    }
                )

        return results

    def _check_service(self, service_config: Dict) -> Dict:
        """Check if a service is running.

        Args:
            service_config: Service configuration dictionary.

        Returns:
            Dictionary containing service status information.
        """
        service_name = service_config.get("name")
        check_method = service_config.get("check_method", "systemctl")

        status = {
            "name": service_name,
            "running": False,
            "message": "",
            "check_method": check_method,
        }

        try:
            if check_method == "systemctl":
                running = self._check_systemctl(service_config)
                status["running"] = running
                status["message"] = (
                    "Active" if running else "Inactive or failed"
                )

            elif check_method in ["auto", "service", "openrc"]:
                running = self._check_service_manager(service_config, check_method)
                status["running"] = running
                status["message"] = "Active" if running else "Inactive or failed"

            elif check_method == "process":
                running = self._check_process(service_config)
                status["running"] = running
                status["message"] = "Process found" if running else "Process not found"

            elif check_method == "process_regex":
                running = self._check_process_regex(service_config)
                status["running"] = running
                status["message"] = (
                    "Process pattern matched" if running else "No matching process"
                )

            elif check_method == "custom_command":
                running = self._check_custom_command(service_config)
                status["running"] = running
                status["message"] = "Check passed" if running else "Check failed"

            elif check_method == "iptables":
                running = self._check_iptables(service_config)
                status["running"] = running
                status["message"] = "Active" if running else "Inactive or failed"

            elif check_method in ["http", "https"]:
                http_status = self._check_http(service_config)
                status["running"] = http_status["running"]
                status["message"] = http_status.get("message", "")
                status["http_status"] = http_status

            else:
                status["message"] = f"Unknown check method: {check_method}"
                logger.warning(status["message"])

        except Exception as e:
            status["message"] = f"Check error: {str(e)}"
            logger.error(f"Error in _check_service for {service_name}: {str(e)}")

        return status

    def _get_service_key(self, service_config: Dict) -> str:
        """Resolve the unique key for a service.

        Args:
            service_config: Service configuration dictionary.

        Returns:
            Unique key representing the service.
        """
        return (
            service_config.get("name")
            or service_config.get("service_name")
            or service_config.get("process_name")
            or service_config.get("url")
            or "unknown_service"
        )

    def _parse_interval_seconds(self, interval_config: Any) -> Optional[int]:
        """Parse interval configuration into seconds.

        Args:
            interval_config: Interval configuration.

        Returns:
            Interval in seconds, or None if not configured.
        """
        if interval_config is None:
            return None

        if isinstance(interval_config, (int, float)):
            return max(0, int(interval_config))

        if isinstance(interval_config, dict):
            value = interval_config.get("value")
            unit = str(interval_config.get("unit", "seconds")).lower()
            if value is None:
                return None

            unit_map = {
                "s": 1,
                "sec": 1,
                "secs": 1,
                "second": 1,
                "seconds": 1,
                "m": 60,
                "min": 60,
                "mins": 60,
                "minute": 60,
                "minutes": 60,
                "h": 3600,
                "hr": 3600,
                "hrs": 3600,
                "hour": 3600,
                "hours": 3600,
            }
            multiplier = unit_map.get(unit)
            if multiplier is None:
                return None
            return max(0, int(float(value) * multiplier))

        return None

    def _should_check_service(self, service_config: Dict) -> bool:
        """Determine whether a service should be checked now.

        Args:
            service_config: Service configuration dictionary.

        Returns:
            True if the service should be checked, False otherwise.
        """
        service_key = self._get_service_key(service_config)
        interval_seconds = self._parse_interval_seconds(
            service_config.get("check_interval", self.config.get("check_interval"))
        )

        if interval_seconds is None or interval_seconds <= 0:
            return True

        last_check = self.last_check_time.get(service_key)
        current_time = time.time()
        if last_check and (current_time - last_check) < interval_seconds:
            return False

        self.last_check_time[service_key] = current_time
        return True

    def _check_systemctl_pattern(self, pattern: str) -> bool:
        """Check systemd services using a regex pattern.

        Args:
            pattern: Regex pattern to match unit names.

        Returns:
            True if any matching unit is active, False otherwise.
        """
        if not self.service_manager.supports_patterns():
            logger.warning("Service manager does not support unit pattern checks")
            return False

        try:
            result = subprocess.run(
                ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--no-legend"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return False

            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) < 4:
                    continue
                unit_name = parts[0]
                active_state = parts[2]
                if re.search(pattern, unit_name) and active_state == "active":
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking systemctl pattern {pattern}: {str(e)}")
            return False

    def _check_systemctl(self, service_config: Dict) -> bool:
        """Check service status using systemctl.

        Args:
            service_config: Service configuration dictionary.

        Returns:
            True if service is active, False otherwise.
        """
        service_name = service_config.get("service_name")
        service_name_pattern = service_config.get("service_name_pattern")
        if service_name_pattern:
            return self._check_systemctl_pattern(service_name_pattern)

        if not service_name:
            return False

        if not self.service_manager.is_systemd:
            running, _, _ = self.service_manager.check_service(service_name)
            return running

        try:
            result = subprocess.run(
                ["systemctl", "is-active", service_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0 and result.stdout.strip() == "active"
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout checking systemctl status for {service_name}")
            return False
        except Exception as e:
            logger.error(f"Error checking systemctl for {service_name}: {str(e)}")
            return False

    def _check_service_manager(self, service_config: Dict, check_method: str) -> bool:
        """Check service using the detected service manager.

        Args:
            service_config: Service configuration dictionary.
            check_method: Requested check method (auto/service/openrc).

        Returns:
            True if service is running, False otherwise.
        """
        service_name = service_config.get("service_name") or service_config.get("name")
        if not service_name:
            return False

        manager_override = None
        if check_method == "service":
            manager_override = "sysv"
        elif check_method == "openrc":
            manager_override = "openrc"

        running, _, _ = self.service_manager.check_service(
            service_name,
            manager_type=manager_override,
        )
        return running

    def _check_process(self, service_config: Dict) -> bool:
        """Check if a process is running by exact name.

        Args:
            service_config: Service configuration dictionary.

        Returns:
            True if process is running, False otherwise.
        """
        process_name = service_config.get("process_name")
        if not process_name:
            return False

        try:
            result = subprocess.run(
                ["pgrep", "-x", process_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0 and len(result.stdout.strip()) > 0
        except Exception as e:
            logger.error(f"Error checking process {process_name}: {str(e)}")
            return False

    def _check_process_regex(self, service_config: Dict) -> bool:
        """Check if a process matching regex pattern is running.

        Args:
            service_config: Service configuration dictionary.

        Returns:
            True if matching process found, False otherwise.
        """
        pattern = service_config.get("process_pattern")
        pattern_list = service_config.get("process_patterns", [])
        patterns: List[str] = []

        if pattern:
            patterns.append(pattern)

        if isinstance(pattern_list, list):
            for item in pattern_list:
                if isinstance(item, dict):
                    item_pattern = item.get("pattern")
                else:
                    item_pattern = item
                if item_pattern:
                    patterns.append(str(item_pattern))

        if not patterns:
            # Check multi-instance services
            if service_config.get("multi_instance"):
                return self._check_multi_instance(service_config)
            return False

        try:
            pattern_key = tuple(patterns)
            compiled_patterns = self._regex_cache.get(pattern_key)
            if compiled_patterns is None:
                compiled_patterns = [re.compile(p) for p in patterns]
                self._regex_cache[pattern_key] = compiled_patterns
            result = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return False

            for line in result.stdout.splitlines():
                if any(compiled.search(line) for compiled in compiled_patterns):
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking process pattern {pattern}: {str(e)}")
            return False

    def _check_multi_instance(self, service_config: Dict) -> bool:
        """Check multiple service instances.

        Args:
            service_config: Service configuration dictionary.

        Returns:
            True if at least one instance is running, False otherwise.
        """
        instances = service_config.get("instances", [])
        any_running = False

        for instance in instances:
            service_name = instance.get("service_name")
            if service_name:
                try:
                    result = subprocess.run(
                        ["systemctl", "is-active", service_name],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0 and result.stdout.strip() == "active":
                        any_running = True
                        logger.debug(f"Instance {service_name} is running")
                    else:
                        logger.debug(f"Instance {service_name} is not running")
                except Exception as e:
                    logger.error(f"Error checking instance {service_name}: {str(e)}")

        return any_running

    def _check_custom_command(self, service_config: Dict) -> bool:
        """Check service using custom command.

        Args:
            service_config: Service configuration dictionary.

        Returns:
            True if custom check passes, False otherwise.
        """
        check_command = service_config.get("check_command")
        if not check_command:
            return False

        timeout_seconds = service_config.get("check_timeout", 30)

        try:
            result = subprocess.run(
                check_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error running custom check command: {str(e)}")
            return False

    def _check_iptables(self, service_config: Dict) -> bool:
        """Check iptables availability and status.

        Args:
            service_config: Service configuration dictionary.

        Returns:
            True if iptables check succeeds, False otherwise.
        """
        if service_config.get("check_command"):
            return self._check_custom_command(service_config)

        timeout_seconds = service_config.get("check_timeout", 10)

        try:
            result = subprocess.run(
                ["iptables", "-L", "-n"],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            return result.returncode == 0
        except FileNotFoundError:
            logger.warning("iptables command not found")
            return False
        except Exception as e:
            logger.error(f"Error running iptables check: {str(e)}")
            return False

    def _check_http(self, service_config: Dict) -> Dict:
        """Check a web endpoint via HTTP/HTTPS.

        Args:
            service_config: Service configuration dictionary.

        Returns:
            Dictionary containing HTTP status and response timing.
        """
        url = service_config.get("url")
        if not url:
            return {"running": False, "message": "Missing URL for HTTP check"}

        timeout_seconds = service_config.get("timeout_seconds", 10)
        expected_codes = service_config.get("expected_status_codes") or [200, 204, 301, 302]
        max_response_time_ms = service_config.get("max_response_time_ms")
        http_method = service_config.get("http_method", "GET").upper()
        headers = service_config.get("headers", {})
        verify_tls = service_config.get("verify_tls", True)

        request = urllib.request.Request(url, method=http_method, headers=headers)
        context = None
        if url.lower().startswith("https") and not verify_tls:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        start_time = time.monotonic()
        try:
            with force_ipv4(self.only_ipv4):
                with urllib.request.urlopen(
                    request,
                    timeout=timeout_seconds,
                    context=context,
                ) as response:
                    status_code = response.getcode()
                    elapsed_ms = (time.monotonic() - start_time) * 1000

                    if max_response_time_ms and elapsed_ms > max_response_time_ms:
                        return {
                            "running": False,
                            "message": f"Slow response: {elapsed_ms:.0f}ms",
                            "status_code": status_code,
                            "response_time_ms": elapsed_ms,
                        }

                    if status_code not in expected_codes:
                        return {
                            "running": False,
                            "message": f"Unexpected HTTP status: {status_code}",
                            "status_code": status_code,
                            "response_time_ms": elapsed_ms,
                        }

                    return {
                        "running": True,
                        "message": f"HTTP {status_code} ({elapsed_ms:.0f}ms)",
                        "status_code": status_code,
                        "response_time_ms": elapsed_ms,
                    }
        except urllib.error.HTTPError as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            return {
                "running": False,
                "message": f"HTTP error: {e.code}",
                "status_code": e.code,
                "response_time_ms": elapsed_ms,
            }
        except (urllib.error.URLError, socket.timeout) as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            return {
                "running": False,
                "message": f"Connection error: {str(e)}",
                "response_time_ms": elapsed_ms,
            }

    def _handle_service_failure(self, service_config: Dict, status: Dict) -> Optional[Dict]:
        """Handle a failed service check.

        Args:
            service_config: Service configuration dictionary.
            status: Service status dictionary.
        """
        service_name = service_config.get("name")
        service_key = self._get_service_key(service_config)
        action = self.config.get("action_on_failure", "restart_and_notify")
        action_result: Optional[Dict] = None

        if action not in ["restart", "restart_and_notify"]:
            return None

        if not self._check_action_cooldown(service_key, service_config):
            logger.info(
                f"Service {service_name} is in action cooldown period, skipping recovery"
            )
            return {
                "action": "recovery_skipped",
                "success": False,
                "timestamp": time.time(),
                "message": "Action cooldown active",
            }

        action_ready, action_reason = self._check_action_readiness(service_config)
        if not action_ready:
            logger.info(
                f"Service {service_name} action blocked: {action_reason}"
            )
            return {
                "action": "recovery_blocked",
                "success": False,
                "timestamp": time.time(),
                "message": action_reason,
            }

        # Check restart attempts BEFORE attempting restart
        if not self._check_restart_attempts(service_key):
            logger.error(
                f"Service {service_name} has exceeded maximum restart attempts"
            )
            return None

        # Check cooldown
        if not self._check_cooldown(service_key):
            logger.info(f"Service {service_name} is in cooldown period, skipping restart")
            return None

        # Increment attempt counter BEFORE restart to prevent race conditions
        self._increment_restart_attempts(service_key)

        # Notify before action
        self._notify_pre_action(service_config, status)

        # Perform action
        if action in ["restart", "restart_and_notify"]:
            success = self._restart_service(service_config)
            status["action_taken"] = "restart_attempted"
            status["restart_success"] = success

            if success:
                logger.info(f"Successfully restarted service: {service_name}")
                self._update_cooldown(service_key)
            else:
                logger.error(f"Failed to restart service: {service_name}")

            self._update_action_cooldown(service_key)

            action_result = {
                "action": "restart_service",
                "command": service_config.get("restart_command"),
                "success": success,
                "timestamp": time.time(),
                "message": status.get("message", ""),
            }

        return action_result

    def _check_cooldown(self, service_name: str) -> bool:
        """Check if service is in cooldown period.

        Args:
            service_name: Name of the service.

        Returns:
            True if not in cooldown, False if in cooldown.
        """
        cooldown = self.config.get("restart_cooldown", 300)
        last_restart = self.cooldown_tracker.get(service_name, 0)
        current_time = time.time()

        return (current_time - last_restart) >= cooldown

    def _check_action_cooldown(self, service_key: str, service_config: Dict) -> bool:
        """Check if recovery action is in cooldown period.

        Args:
            service_key: Unique service key.
            service_config: Service configuration dictionary.

        Returns:
            True if action is allowed, False otherwise.
        """
        interval_config = service_config.get("action_cooldown")
        if interval_config is None:
            interval_config = self.config.get("action_cooldown")

        cooldown_seconds = self._parse_interval_seconds(interval_config)
        if cooldown_seconds is None or cooldown_seconds <= 0:
            return True

        last_action = self.action_cooldown_tracker.get(service_key, 0)
        return (time.time() - last_action) >= cooldown_seconds

    def _update_action_cooldown(self, service_key: str) -> None:
        """Update action cooldown tracker.

        Args:
            service_key: Unique service key.
        """
        self.action_cooldown_tracker[service_key] = time.time()

    def _check_action_readiness(self, service_config: Dict) -> Tuple[bool, str]:
        """Check if service action is safe to execute.

        Args:
            service_config: Service configuration dictionary.

        Returns:
            Tuple of (is_ready, reason).
        """
        service_name = service_config.get("service_name")
        service_pattern = service_config.get("service_name_pattern")

        if (service_name or service_pattern) and self.service_manager.is_systemd:
            exists, restarting = self._check_systemd_state(service_name, service_pattern)
            if not exists:
                return False, "Service not found"
            if restarting:
                return False, "Service is restarting"

        if self.service_manager.manager_type == "systemd":
            return True, "Action allowed"

        return True, "Recovery action is ready"

    def _check_systemd_state(
        self, service_name: Optional[str], service_pattern: Optional[str]
    ) -> Tuple[bool, bool]:
        """Check systemd service existence and restarting state.

        Args:
            service_name: Exact systemd unit name.
            service_pattern: Regex pattern for unit names.

        Returns:
            Tuple of (exists, is_restarting).
        """
        try:
            if service_pattern:
                result = subprocess.run(
                    [
                        "systemctl",
                        "list-units",
                        "--type=service",
                        "--all",
                        "--no-pager",
                        "--no-legend",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    return False, False

                matched = False
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) < 4:
                        continue
                    unit_name = parts[0]
                    active_state = parts[2]
                    sub_state = parts[3]
                    if re.search(service_pattern, unit_name):
                        matched = True
                        if active_state in {"activating", "deactivating", "reloading"}:
                            return True, True
                        if sub_state in {"auto-restart", "start", "stop"}:
                            return True, True
                return matched, False

            if not service_name:
                return False, False

            result = subprocess.run(
                [
                    "systemctl",
                    "show",
                    service_name,
                    "-p",
                    "LoadState",
                    "-p",
                    "ActiveState",
                    "-p",
                    "SubState",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return False, False

            load_state = ""
            active_state = ""
            sub_state = ""
            for line in result.stdout.splitlines():
                if line.startswith("LoadState="):
                    load_state = line.split("=", 1)[1].strip()
                elif line.startswith("ActiveState="):
                    active_state = line.split("=", 1)[1].strip()
                elif line.startswith("SubState="):
                    sub_state = line.split("=", 1)[1].strip()

            exists = load_state != "not-found"
            restarting = active_state in {"activating", "deactivating", "reloading"} or sub_state in {
                "auto-restart",
                "start",
                "stop",
            }
            return exists, restarting
        except Exception as e:
            logger.error(f"Error checking systemd state: {str(e)}")
            return False, False

    def _notify_pre_action(self, service_config: Dict, status: Dict) -> None:
        """Send notification before recovery action.

        Args:
            service_config: Service configuration dictionary.
            status: Service status dictionary.
        """
        if not self.notification_manager:
            return

        service_name = service_config.get("name")
        event_payload = {
            "event_type": "service_recovery_start",
            "timestamp": time.time(),
            "severity": "high",
            "service": {
                "name": service_name,
                "status": "recovery_start",
                "check_method": status.get("check_method", "unknown"),
                "message": status.get("message", "N/A"),
                "description": service_config.get("description", ""),
            },
            "action": {
                "planned_action": "restart_service",
                "command": service_config.get("restart_command"),
            },
            "details": "Recovery action will be executed",
        }

        self.notification_manager.notify_event(event_payload)

    def _update_cooldown(self, service_name: str) -> None:
        """Update cooldown tracker after restart.

        Args:
            service_name: Name of the service.
        """
        self.cooldown_tracker[service_name] = time.time()

    def _check_restart_attempts(self, service_name: str) -> bool:
        """Check if service has exceeded maximum restart attempts.

        Args:
            service_name: Name of the service.

        Returns:
            True if restart is allowed, False if max attempts exceeded.
        """
        max_attempts = self.config.get("max_restart_attempts", 3)
        current_time = time.time()
        reset_window = 3600  # 1 hour

        if service_name not in self.restart_history:
            self.restart_history[service_name] = {"count": 0, "first_attempt": current_time}
            return True

        history = self.restart_history[service_name]

        # Reset counter if window has passed
        if (current_time - history["first_attempt"]) > reset_window:
            self.restart_history[service_name] = {"count": 0, "first_attempt": current_time}
            return True

        # Check if max attempts exceeded
        if history["count"] >= max_attempts:
            return False

        return True

    def _increment_restart_attempts(self, service_name: str) -> None:
        """Increment restart attempt counter.

        Args:
            service_name: Name of the service.
        """
        if service_name not in self.restart_history:
            self.restart_history[service_name] = {
                "count": 1,
                "first_attempt": time.time(),
            }
        else:
            self.restart_history[service_name]["count"] += 1

    def _restart_service(self, service_config: Dict) -> bool:
        """Restart a service.

        Args:
            service_config: Service configuration dictionary.

        Returns:
            True if restart successful, False otherwise.
        """
        service_name = service_config.get("name")
        restart_command = service_config.get("restart_command")

        resolved_command = self._resolve_restart_command(restart_command, service_config)
        if not resolved_command:
            logger.error(f"No restart command defined for service: {service_name}")
            return False

        try:
            # Execute pre-restart hook if defined
            pre_hook = service_config.get("pre_restart_hook")
            if pre_hook:
                logger.info(f"Running pre-restart hook for {service_name}: {pre_hook}")
                subprocess.run(pre_hook, shell=True, timeout=30)

            # Restart the service
            if isinstance(resolved_command, list):
                for command in resolved_command:
                    logger.info(
                        "Executing restart command for %s: %s",
                        service_name,
                        command,
                    )
                    result = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if result.returncode != 0:
                        logger.warning(
                            "Restart command returned non-zero for %s: %s",
                            service_name,
                            (result.stderr or result.stdout or "").strip(),
                        )
            else:
                logger.info(
                    "Executing restart command for %s: %s",
                    service_name,
                    resolved_command,
                )
                result = subprocess.run(
                    resolved_command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

            # Wait between restart attempts
            wait_time = self.config.get("restart_wait_time", 10)
            time.sleep(wait_time)

            # Execute post-restart hook if defined
            post_hook = service_config.get("post_restart_hook")
            if post_hook:
                logger.info(f"Running post-restart hook for {service_name}: {post_hook}")
                subprocess.run(post_hook, shell=True, timeout=30)

            # Verify service is running
            status = self._check_service(service_config)
            return status.get("running", False)

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout while restarting service: {service_name}")
            return False
        except Exception as e:
            logger.error(f"Error restarting service {service_name}: {str(e)}", exc_info=True)
            return False

    def _resolve_restart_command(self, restart_command: Optional[Any], service_config: Dict) -> Optional[Any]:
        """Resolve restart command based on available service manager.

        Args:
            restart_command: Explicit restart command from configuration.
            service_config: Service configuration dictionary.

        Returns:
            Command string, list of commands, or None if not resolvable.
        """
        service_name = service_config.get("service_name") or service_config.get("name")
        if not restart_command:
            if service_name:
                return self.service_manager.build_restart_command(service_name)
            return None

        if isinstance(restart_command, list):
            normalized_commands = [
                str(command).strip()
                for command in restart_command
                if str(command).strip()
            ]
            if not normalized_commands:
                if service_name:
                    return self.service_manager.build_restart_command(service_name)
                return None
            return normalized_commands

        if isinstance(restart_command, str):
            command_value = restart_command.strip()
            if not command_value:
                if service_name:
                    return self.service_manager.build_restart_command(service_name)
                return None
            if command_value.startswith("systemctl") and not self.service_manager.is_systemd:
                if service_name:
                    return self.service_manager.build_restart_command(service_name)
            return command_value

        logger.warning(
            "Unsupported restart_command type for %s: %s",
            service_name,
            type(restart_command).__name__,
        )
        if service_name:
            return self.service_manager.build_restart_command(service_name)
        return None

    def reset_restart_history(self) -> None:
        """Reset all restart history and cooldown trackers."""
        self.restart_history.clear()
        self.cooldown_tracker.clear()
        self.action_cooldown_tracker.clear()
        self.last_check_time.clear()
        logger.info("Reset all service restart history and cooldowns")
