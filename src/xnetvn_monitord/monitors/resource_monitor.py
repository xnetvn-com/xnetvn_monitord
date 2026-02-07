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

"""Resource monitoring module.

This module monitors system resources (CPU, memory, disk) and triggers
recovery actions when thresholds are exceeded.
"""

import logging
import os
import shlex
import subprocess
import time
from typing import Dict, List, Optional

import psutil

from xnetvn_monitord.utils.service_manager import ServiceManager

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """Monitor system resources and trigger recovery actions."""

    def __init__(self, config: Dict, service_manager: Optional[ServiceManager] = None):
        """Initialize the resource monitor.

        Args:
            config: Resource monitoring configuration dictionary.
        """
        self.config = config
        self.enabled = config.get("enabled", True)
        self.last_action_time: Dict[str, float] = {}
        self.service_manager = service_manager or ServiceManager()

    def check_resources(self) -> Dict:
        """Check all configured resources.

        Returns:
            Dictionary containing resource status and actions taken.
        """
        if not self.enabled:
            logger.debug("Resource monitoring is disabled")
            return {"enabled": False}

        results = {
            "timestamp": time.time(),
            "cpu_load": None,
            "memory": None,
            "disk": None,
            "actions_taken": [],
            "action_results": [],
        }

        try:
            # Check CPU load
            cpu_config = self.config.get("cpu_load", {})
            if cpu_config.get("enabled", False):
                cpu_result = self._check_cpu_load(cpu_config)
                results["cpu_load"] = cpu_result
                if cpu_result.get("threshold_exceeded"):
                    action_result = self._handle_high_cpu()
                    results["actions_taken"].append("high_cpu_recovery")
                    if action_result:
                        results["action_results"].append(action_result)

            # Check memory
            memory_config = self.config.get("memory", {})
            if memory_config.get("enabled", False):
                memory_result = self._check_memory(memory_config)
                results["memory"] = memory_result
                if memory_result.get("threshold_exceeded"):
                    action_result = self._handle_low_memory()
                    results["actions_taken"].append("low_memory_recovery")
                    if action_result:
                        results["action_results"].append(action_result)

            # Check disk space
            disk_config = self.config.get("disk", {})
            if disk_config.get("enabled", False):
                disk_result = self._check_disk(disk_config)
                results["disk"] = disk_result
                if disk_result.get("threshold_exceeded"):
                    action_result = self._handle_low_disk()
                    results["actions_taken"].append("low_disk_recovery")
                    if action_result:
                        results["action_results"].append(action_result)

        except Exception as e:
            logger.error(f"Error checking resources: {str(e)}", exc_info=True)
            results["error"] = str(e)

        return results

    def _check_cpu_load(self, config: Dict) -> Dict:
        """Check CPU load averages.

        Args:
            config: CPU load configuration dictionary.

        Returns:
            Dictionary containing CPU load status.
        """
        result = {
            "load_1min": None,
            "load_5min": None,
            "load_15min": None,
            "threshold_exceeded": False,
            "exceeded_type": None,
        }

        try:
            # Get load averages
            load_avg = os.getloadavg()
            result["load_1min"] = load_avg[0]
            result["load_5min"] = load_avg[1]
            result["load_15min"] = load_avg[2]

            # Check 1-minute load
            if config.get("check_1min", False):
                threshold = config.get("threshold_1min", 99.0)
                if load_avg[0] > threshold:
                    result["threshold_exceeded"] = True
                    result["exceeded_type"] = "1min"
                    logger.warning(f"CPU load (1min) exceeded threshold: {load_avg[0]:.2f} > {threshold}")

            # Check 5-minute load
            if not result["threshold_exceeded"] and config.get("check_5min", False):
                threshold = config.get("threshold_5min", 80.0)
                if load_avg[1] > threshold:
                    result["threshold_exceeded"] = True
                    result["exceeded_type"] = "5min"
                    logger.warning(f"CPU load (5min) exceeded threshold: {load_avg[1]:.2f} > {threshold}")

            # Check 15-minute load
            if not result["threshold_exceeded"] and config.get("check_15min", False):
                threshold = config.get("threshold_15min", 60.0)
                if load_avg[2] > threshold:
                    result["threshold_exceeded"] = True
                    result["exceeded_type"] = "15min"
                    logger.warning(f"CPU load (15min) exceeded threshold: {load_avg[2]:.2f} > {threshold}")

        except Exception as e:
            logger.error(f"Error checking CPU load: {str(e)}")
            result["error"] = str(e)

        return result

    def _check_memory(self, config: Dict) -> Dict:
        """Check available memory.

        Args:
            config: Memory configuration dictionary.

        Returns:
            Dictionary containing memory status.
        """
        result = {
            "total_mb": None,
            "available_mb": None,
            "available_percent": None,
            "threshold_exceeded": False,
            "exceeded_type": None,
        }

        try:
            # Get memory info
            mem = psutil.virtual_memory()
            result["total_mb"] = mem.total / (1024 * 1024)
            result["available_mb"] = mem.available / (1024 * 1024)
            result["available_percent"] = mem.percent

            # Calculate free percentage
            free_percent = (mem.available / mem.total) * 100

            # Check thresholds
            free_percent_threshold = config.get("free_percent_threshold", 5.0)
            free_mb_threshold = config.get("free_mb_threshold", 512)
            condition = config.get("condition", "or").lower()

            percent_exceeded = free_percent < free_percent_threshold
            mb_exceeded = result["available_mb"] < free_mb_threshold

            if condition == "and":
                result["threshold_exceeded"] = percent_exceeded and mb_exceeded
            else:  # "or"
                result["threshold_exceeded"] = percent_exceeded or mb_exceeded

            if result["threshold_exceeded"]:
                # Set exceeded_type based on which condition triggered first
                if percent_exceeded and not mb_exceeded:
                    result["exceeded_type"] = "percent"
                    logger.warning(
                        f"Free memory percentage below threshold: {free_percent:.2f}% < {free_percent_threshold}%"
                    )
                elif mb_exceeded and not percent_exceeded:
                    result["exceeded_type"] = "mb"
                    logger.warning(
                        f"Free memory below threshold: {result['available_mb']:.2f} MB < {free_mb_threshold} MB"
                    )
                else:
                    # Both conditions exceeded
                    result["exceeded_type"] = "both"
                    logger.warning(
                        f"Free memory percentage below threshold: {free_percent:.2f}% < {free_percent_threshold}%"
                    )
                    logger.warning(
                        f"Free memory below threshold: {result['available_mb']:.2f} MB < {free_mb_threshold} MB"
                    )

        except Exception as e:
            logger.error(f"Error checking memory: {str(e)}")
            result["error"] = str(e)

        return result

    def _check_disk(self, config: Dict) -> Dict:
        """Check disk space for configured mount points.

        Args:
            config: Disk configuration dictionary.

        Returns:
            Dictionary containing disk space status.
        """
        result = {
            "mount_points": [],
            "threshold_exceeded": False,
        }

        try:
            # Support both 'paths' and 'mount_points' for backward compatibility
            mount_points = config.get("paths", config.get("mount_points", []))
            normalized_mount_points: List[Dict] = []
            default_free_percent_threshold = config.get("free_percent_threshold", 10.0)
            default_free_gb_threshold = config.get("free_gb_threshold", 5.0)
            default_free_mb_threshold = config.get("free_mb_threshold")

            for mp_config in mount_points:
                if isinstance(mp_config, str):
                    if mp_config.strip():
                        normalized_mount_points.append({"path": mp_config})
                    continue
                if isinstance(mp_config, dict):
                    normalized_mount_points.append(mp_config)
                    continue
                logger.warning("Invalid mount point configuration: %s", mp_config)

            for mp_config in normalized_mount_points:
                path = mp_config.get("path")
                if not path or not os.path.exists(path):
                    continue

                mp_result = {
                    "path": path,
                    "total_gb": None,
                    "free_gb": None,
                    "free_percent": None,
                    "threshold_exceeded": False,
                }

                try:
                    # Get disk usage
                    usage = psutil.disk_usage(path)
                    mp_result["total_gb"] = usage.total / (1024**3)
                    mp_result["free_gb"] = usage.free / (1024**3)
                    mp_result["free_percent"] = (usage.free / usage.total) * 100

                    # Check thresholds
                    free_percent_threshold = mp_config.get("free_percent_threshold")
                    if free_percent_threshold is None:
                        free_percent_threshold = mp_config.get(
                            "threshold_percent",
                            default_free_percent_threshold,
                        )
                    free_gb_threshold = mp_config.get(
                        "free_gb_threshold",
                        default_free_gb_threshold,
                    )
                    free_mb_threshold = mp_config.get(
                        "free_mb_threshold",
                        default_free_mb_threshold,
                    )

                    if mp_result["free_percent"] < free_percent_threshold:
                        mp_result["threshold_exceeded"] = True
                        result["threshold_exceeded"] = True
                        logger.warning(
                            f"Disk space on {path} below threshold: "
                            f"{mp_result['free_percent']:.2f}% < {free_percent_threshold}%"
                        )

                    if free_gb_threshold is not None and mp_result["free_gb"] < free_gb_threshold:
                        mp_result["threshold_exceeded"] = True
                        result["threshold_exceeded"] = True
                        logger.warning(
                            f"Disk space on {path} below threshold: "
                            f"{mp_result['free_gb']:.2f} GB < {free_gb_threshold} GB"
                        )

                    if free_mb_threshold is not None:
                        free_mb = usage.free / (1024**2)
                        if free_mb < free_mb_threshold:
                            mp_result["threshold_exceeded"] = True
                            result["threshold_exceeded"] = True
                            logger.warning(
                                f"Disk space on {path} below threshold: " f"{free_mb:.2f} MB < {free_mb_threshold} MB"
                            )

                except Exception as e:
                    logger.error(f"Error checking disk {path}: {str(e)}")
                    mp_result["error"] = str(e)

                result["mount_points"].append(mp_result)

        except Exception as e:
            logger.error(f"Error checking disk space: {str(e)}")
            result["error"] = str(e)

        return result

    def _handle_high_cpu(self) -> Optional[Dict]:
        """Handle high CPU load by executing recovery actions."""
        if not self._check_action_cooldown("high_cpu"):
            logger.info("High CPU recovery is in cooldown period")
            return None

        logger.info("Executing high CPU recovery actions")
        action_details: Dict = {
            "services": [],
            "recovery_command": None,
            "recovery_command_success": None,
        }

        # Check for direct recovery command in cpu_load config
        cpu_config = self.config.get("cpu_load", {})
        recovery_command = cpu_config.get("recovery_command")

        if recovery_command:
            action_details["recovery_command"] = recovery_command
            # Execute recovery command directly
            try:
                if isinstance(recovery_command, str):
                    command_args = shlex.split(recovery_command.strip())
                else:
                    command_args = [str(item) for item in recovery_command if str(item).strip()]
                if not command_args:
                    action_details["recovery_command_success"] = False
                    logger.error("CPU recovery command is empty after parsing")
                else:
                    result = subprocess.run(
                        command_args,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    action_details["recovery_command_success"] = result.returncode == 0
                    if result.returncode == 0:
                        logger.info(
                            "Successfully executed CPU recovery command: %s",
                            recovery_command,
                        )
                    else:
                        logger.error("CPU recovery command failed: %s", result.stderr)
            except subprocess.TimeoutExpired:
                action_details["recovery_command_success"] = False
                logger.error("Timeout executing CPU recovery command: %s", recovery_command)
            except Exception as e:
                action_details["recovery_command_success"] = False
                logger.error("Error executing CPU recovery command: %s", str(e))

        # Also restart configured services
        recovery_config = self.config.get("recovery_actions", {})
        services = recovery_config.get("high_cpu_services", [])
        if services:
            action_details["services"] = self._restart_services(services, recovery_config)

        self._update_action_cooldown("high_cpu")
        action_details["success"] = self._evaluate_action_success(action_details)

        return {
            "action": "high_cpu_recovery",
            "timestamp": time.time(),
            "success": action_details["success"],
            "details": action_details,
        }

    def _handle_low_memory(self) -> Optional[Dict]:
        """Handle low memory by restarting configured services."""
        if not self._check_action_cooldown("low_memory"):
            logger.info("Low memory recovery is in cooldown period")
            return None

        logger.info("Executing low memory recovery actions")
        recovery_config = self.config.get("recovery_actions", {})
        services = recovery_config.get("low_memory_services", [])
        service_results = self._restart_services(services, recovery_config)
        self._update_action_cooldown("low_memory")
        success = all(result.get("success", False) for result in service_results) if service_results else True

        return {
            "action": "low_memory_recovery",
            "timestamp": time.time(),
            "success": success,
            "details": {
                "services": service_results,
            },
        }

    def _handle_low_disk(self) -> Optional[Dict]:
        """Handle low disk space by restarting configured services."""
        if not self._check_action_cooldown("low_disk"):
            logger.info("Low disk recovery is in cooldown period")
            return None

        logger.info("Executing low disk recovery actions")
        recovery_config = self.config.get("recovery_actions", {})
        services = recovery_config.get("low_disk_services", [])
        service_results = self._restart_services(services, recovery_config)
        self._update_action_cooldown("low_disk")
        success = all(result.get("success", False) for result in service_results) if service_results else True

        return {
            "action": "low_disk_recovery",
            "timestamp": time.time(),
            "success": success,
            "details": {
                "services": service_results,
            },
        }

    def _restart_services(self, services: List[str], config: Dict) -> List[Dict]:
        """Restart a list of services.

        Args:
            services: List of service names to restart.
            config: Recovery configuration dictionary.
        """
        restart_interval = config.get("restart_interval", 5)
        results: List[Dict] = []

        for service_name in services:
            try:
                logger.info(f"Restarting service for resource recovery: {service_name}")
                action_result = self.service_manager.restart_service(service_name)
                service_result = {
                    "service": service_name,
                    "success": action_result.get("success", False),
                    "stdout": action_result.get("stdout", ""),
                    "stderr": action_result.get("stderr", ""),
                }
                results.append(service_result)

                if action_result.get("success"):
                    logger.info(f"Successfully restarted {service_name}")
                else:
                    logger.error(f"Failed to restart {service_name}: {service_result['stderr']}")

                # Wait between restarts
                if service_name != services[-1]:
                    time.sleep(restart_interval)

            except Exception as e:
                logger.error(f"Error restarting {service_name}: {str(e)}")
                results.append(
                    {
                        "service": service_name,
                        "success": False,
                        "stdout": "",
                        "stderr": str(e),
                    }
                )

        return results

    def _check_action_cooldown(self, action_type: str) -> bool:
        """Check if action is in cooldown period.

        Args:
            action_type: Type of action (high_cpu, low_memory, low_disk).

        Returns:
            True if action is allowed, False if in cooldown.
        """
        cooldown = self.config.get("recovery_actions", {}).get("cooldown_period", 1800)
        last_action = self.last_action_time.get(action_type, 0)
        current_time = time.time()

        return (current_time - last_action) >= cooldown

    def _update_action_cooldown(self, action_type: str) -> None:
        """Update action cooldown tracker.

        Args:
            action_type: Type of action (high_cpu, low_memory, low_disk).
        """
        self.last_action_time[action_type] = time.time()

    def _evaluate_action_success(self, action_details: Dict) -> bool:
        """Evaluate overall success for resource recovery actions.

        Args:
            action_details: Action details dictionary.

        Returns:
            True if action is considered successful, False otherwise.
        """
        command_success = action_details.get("recovery_command_success")
        service_results = action_details.get("services", [])

        if command_success is False:
            return False

        if service_results:
            return all(result.get("success", False) for result in service_results)

        return command_success is not False

    def get_current_stats(self) -> Dict:
        """Get current system resource statistics without threshold checks.

        Returns:
            Dictionary containing current resource statistics.
        """
        stats = {
            "timestamp": time.time(),
            "cpu": {},
            "memory": {},
            "disk": {},
            "network": {},
        }

        try:
            # CPU stats
            load_avg = os.getloadavg()
            stats["cpu"]["load_1min"] = load_avg[0]
            stats["cpu"]["load_5min"] = load_avg[1]
            stats["cpu"]["load_15min"] = load_avg[2]
            stats["cpu"]["percent"] = psutil.cpu_percent(interval=1)

            # Memory stats
            mem = psutil.virtual_memory()
            stats["memory"]["total_mb"] = mem.total / (1024 * 1024)
            stats["memory"]["available_mb"] = mem.available / (1024 * 1024)
            stats["memory"]["used_mb"] = mem.used / (1024 * 1024)
            stats["memory"]["percent_used"] = mem.percent

            # Disk stats
            disk_config = self.config.get("disk", {})
            mount_points = disk_config.get("mount_points", [{"path": "/"}])
            stats["disk"]["mount_points"] = []

            for mp in mount_points:
                path = mp.get("path", "/")
                if os.path.exists(path):
                    usage = psutil.disk_usage(path)
                    stats["disk"]["mount_points"].append(
                        {
                            "path": path,
                            "total_gb": usage.total / (1024**3),
                            "used_gb": usage.used / (1024**3),
                            "free_gb": usage.free / (1024**3),
                            "percent_used": usage.percent,
                        }
                    )

            # Network stats
            net_totals = psutil.net_io_counters()
            stats["network"]["total"] = {
                "bytes_sent": net_totals.bytes_sent,
                "bytes_recv": net_totals.bytes_recv,
                "packets_sent": net_totals.packets_sent,
                "packets_recv": net_totals.packets_recv,
                "errin": net_totals.errin,
                "errout": net_totals.errout,
                "dropin": net_totals.dropin,
                "dropout": net_totals.dropout,
            }

            per_nic = psutil.net_io_counters(pernic=True)
            stats["network"]["interfaces"] = {}
            for iface, counters in per_nic.items():
                stats["network"]["interfaces"][iface] = {
                    "bytes_sent": counters.bytes_sent,
                    "bytes_recv": counters.bytes_recv,
                    "packets_sent": counters.packets_sent,
                    "packets_recv": counters.packets_recv,
                    "errin": counters.errin,
                    "errout": counters.errout,
                    "dropin": counters.dropin,
                    "dropout": counters.dropout,
                }

        except Exception as e:
            logger.error(f"Error getting resource stats: {str(e)}")
            stats["error"] = str(e)

        return stats
