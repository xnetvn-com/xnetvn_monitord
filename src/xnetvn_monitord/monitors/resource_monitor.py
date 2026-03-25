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
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

import psutil

from xnetvn_monitord.monitors.disk_cleanup import (
    normalize_cleanup_config,
    quarantine_cleanup_candidates,
    scan_cleanup_candidates,
)
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
        self._process_disk_baseline: Dict[int, Dict[str, float]] = {}
        self._prime_process_counters()

    def check_resources(self) -> Dict:
        """Check all configured resources.

        Returns:
            Dictionary containing resource status and actions taken.
        """
        if not self.enabled:
            logger.debug("Resource monitoring is disabled")
            return {"enabled": False}

        results: Dict[str, Any] = {
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
                    action_result = self._handle_low_disk(disk_result)
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
        result: Dict[str, Any] = {
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
        result: Dict[str, Any] = {
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
        result: Dict[str, Any] = {
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

                mp_result: Dict[str, Any] = {
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
        action_details: Dict[str, Any] = {
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
                parse_error = False
                if isinstance(recovery_command, str):
                    command_args = shlex.split(recovery_command.strip())
                elif isinstance(recovery_command, list):
                    command_args = [str(item) for item in recovery_command if str(item).strip()]
                else:
                    command_args = []
                    parse_error = True
                    action_details["recovery_command_success"] = False
                    logger.error(
                        "CPU recovery command has unsupported type: %s",
                        type(recovery_command).__name__,
                    )
                if not command_args:
                    if not parse_error:
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

    def _handle_low_disk(self, disk_result: Optional[Dict] = None) -> Optional[Dict]:
        """Handle low disk space with optional cleanup and service recovery."""
        if not self._check_action_cooldown("low_disk"):
            logger.info("Low disk recovery is in cooldown period")
            return None

        logger.info("Executing low disk recovery actions")
        disk_config = self.config.get("disk", {})
        action_on_threshold = str(disk_config.get("action_on_threshold", "notify")).lower()
        recovery_config = self.config.get("recovery_actions", {})
        service_results: List[Dict[str, Any]] = []
        cleanup_result: Optional[Dict[str, Any]] = None

        if action_on_threshold in {"cleanup", "both"}:
            cleanup_result = self._execute_disk_cleanup(disk_result or {"mount_points": []})

        if action_on_threshold in {"notify", "both"}:
            services = recovery_config.get("low_disk_services", [])
            service_results = self._restart_services(services, recovery_config)

        self._update_action_cooldown("low_disk")
        success = True
        if cleanup_result is not None:
            success = success and cleanup_result.get("success", False)
        if service_results:
            success = success and all(result.get("success", False) for result in service_results)

        return {
            "action": "low_disk_recovery",
            "timestamp": time.time(),
            "success": success,
            "details": {
                "cleanup": cleanup_result,
                "services": service_results,
            },
        }

    def _execute_disk_cleanup(self, disk_result: Dict[str, Any]) -> Dict[str, Any]:
        """Execute disk cleanup for mount points that exceeded configured thresholds."""
        disk_config = self.config.get("disk", {})
        cleanup_config = disk_config.get("cleanup", {})
        if not cleanup_config.get("enabled", False):
            return {
                "success": False,
                "mounts": [],
                "errors": ["Disk cleanup is not enabled"],
            }

        normalized_cleanup_config = normalize_cleanup_config(cleanup_config)
        mount_results: List[Dict[str, Any]] = []
        errors: List[str] = []
        current_time = time.time()

        for index, mount_point in enumerate(disk_result.get("mount_points", []), start=1):
            if not mount_point.get("threshold_exceeded"):
                continue

            mount_path = mount_point.get("path")
            if not mount_path:
                continue

            try:
                candidates = scan_cleanup_candidates(
                    mount_path,
                    normalized_cleanup_config,
                    current_time=current_time,
                )
                quarantine_result = quarantine_cleanup_candidates(
                    candidates,
                    normalized_cleanup_config,
                    mount_point=mount_path,
                    run_id=f"disk-cleanup-{int(current_time)}-{index}",
                    current_time=current_time,
                )
                mount_results.append(
                    {
                        "path": mount_path,
                        "candidates_found": len(candidates),
                        "quarantined_count": len(quarantine_result.get("quarantined", [])),
                        "errors": quarantine_result.get("errors", []),
                        "manifest_path": quarantine_result.get("manifest_path"),
                    }
                )
            except Exception as exc:
                logger.error("Error executing disk cleanup for %s: %s", mount_path, str(exc))
                errors.append(f"{mount_path}: {str(exc)}")

        success = not errors and all(not item.get("errors") for item in mount_results)
        return {"success": success, "mounts": mount_results, "errors": errors}

    def _restart_services(self, services: List[str], config: Dict) -> List[Dict]:
        """Restart a list of services.

        Args:
            services: List of service names to restart.
            config: Recovery configuration dictionary.
        """
        restart_interval = config.get("restart_interval", 5)
        results: List[Dict[str, Any]] = []

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

    def _evaluate_action_success(self, action_details: Dict[str, Any]) -> bool:
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

    def _prime_process_counters(self) -> None:
        """Prime process-level counters so later snapshots can compute deltas."""
        current_time = time.time()

        try:
            for proc in psutil.process_iter(["pid"]):
                try:
                    proc.cpu_percent(interval=None)
                    io_counters = proc.io_counters()
                    if io_counters is None:
                        continue
                    self._process_disk_baseline[proc.pid] = {
                        "timestamp": current_time,
                        "read_bytes": float(io_counters.read_bytes),
                        "write_bytes": float(io_counters.write_bytes),
                    }
                except (psutil.Error, OSError, PermissionError, ValueError):
                    continue
        except Exception as e:
            logger.debug("Failed to prime process counters: %s", str(e))

    def _collect_top_process_stats(self) -> Dict[str, Any]:
        """Collect ranked process snapshots for diagnostics in notifications."""
        snapshots = self._collect_process_snapshots()

        return {
            "cpu_percent": self._build_ranked_process_list(
                snapshots,
                "cpu_percent",
                ["user", "pid", "command", "cpu_percent", "cpu_core_load"],
            ),
            "cpu_load": self._build_ranked_process_list(
                snapshots,
                "cpu_core_load",
                ["user", "pid", "command", "cpu_core_load", "cpu_percent"],
            ),
            "memory": self._build_ranked_process_list(
                snapshots,
                "memory_mb",
                ["user", "pid", "command", "memory_mb", "memory_percent"],
            ),
            "disk_io": self._build_ranked_process_list(
                snapshots,
                "total_disk_io_mb_per_sec",
                [
                    "user",
                    "pid",
                    "command",
                    "read_mb_per_sec",
                    "write_mb_per_sec",
                    "total_disk_io_mb_per_sec",
                ],
            ),
            "network": self._collect_top_network_processes(),
        }

    def _collect_process_snapshots(self) -> List[Dict[str, Any]]:
        """Collect per-process CPU, memory, and disk I/O snapshots."""
        snapshots: List[Dict[str, Any]] = []
        current_time = time.time()
        active_pids = set()

        for proc in psutil.process_iter(["pid", "name", "username"]):
            try:
                with proc.oneshot():
                    pid = proc.info.get("pid", proc.pid)
                    if not isinstance(pid, int):
                        continue
                    active_pids.add(pid)

                    command = self._sanitize_process_name(proc.info.get("name") or proc.name())
                    user = str(proc.info.get("username") or "unknown")
                    cpu_percent = max(float(proc.cpu_percent(interval=None)), 0.0)
                    memory_info = proc.memory_info()
                    memory_mb = max(float(memory_info.rss) / (1024 * 1024), 0.0)
                    memory_percent = max(float(proc.memory_percent()), 0.0)

                disk_metrics = self._calculate_process_disk_io(proc, current_time)
            except (psutil.Error, OSError, PermissionError, ValueError):
                continue

            snapshots.append(
                {
                    "user": user,
                    "pid": pid,
                    "command": command,
                    "cpu_percent": cpu_percent,
                    "cpu_core_load": cpu_percent / 100.0,
                    "memory_mb": memory_mb,
                    "memory_percent": memory_percent,
                    **disk_metrics,
                }
            )

        self._process_disk_baseline = {
            pid: sample for pid, sample in self._process_disk_baseline.items() if pid in active_pids
        }

        return snapshots

    def _calculate_process_disk_io(self, proc: psutil.Process, current_time: float) -> Dict[str, float]:
        """Calculate per-process disk I/O throughput in MB/s using sampled deltas."""
        metrics = {
            "read_mb_per_sec": 0.0,
            "write_mb_per_sec": 0.0,
            "total_disk_io_mb_per_sec": 0.0,
        }

        try:
            io_counters = proc.io_counters()
        except (psutil.Error, OSError, PermissionError, ValueError, AttributeError):
            return metrics

        if io_counters is None:
            return metrics

        baseline = self._process_disk_baseline.get(proc.pid)
        self._process_disk_baseline[proc.pid] = {
            "timestamp": current_time,
            "read_bytes": float(io_counters.read_bytes),
            "write_bytes": float(io_counters.write_bytes),
        }

        if not baseline:
            return metrics

        elapsed = max(current_time - float(baseline.get("timestamp", current_time)), 0.001)
        read_delta = max(float(io_counters.read_bytes) - float(baseline.get("read_bytes", 0.0)), 0.0)
        write_delta = max(float(io_counters.write_bytes) - float(baseline.get("write_bytes", 0.0)), 0.0)

        metrics["read_mb_per_sec"] = read_delta / (1024 * 1024) / elapsed
        metrics["write_mb_per_sec"] = write_delta / (1024 * 1024) / elapsed
        metrics["total_disk_io_mb_per_sec"] = metrics["read_mb_per_sec"] + metrics["write_mb_per_sec"]
        return metrics

    def _build_ranked_process_list(
        self,
        snapshots: List[Dict[str, Any]],
        sort_key: str,
        fields: List[str],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Build a top-N ranking from collected process snapshots."""
        ranked = sorted(
            snapshots,
            key=lambda item: (float(item.get(sort_key, 0.0)), float(item.get("memory_percent", 0.0))),
            reverse=True,
        )

        process_list: List[Dict[str, Any]] = []
        for snapshot in ranked[:limit]:
            process_list.append({field: snapshot.get(field) for field in fields if field in snapshot})

        return process_list

    def _collect_top_network_processes(self) -> Dict[str, Any]:
        """Collect per-process network throughput when an optional collector is available."""
        unavailable = {
            "available": False,
            "reason": "Process-level network throughput is unavailable without an optional collector.",
            "top": [],
        }
        collector_path = shutil.which("nethogs")

        if not collector_path:
            return unavailable

        if hasattr(os, "geteuid") and os.geteuid() != 0:
            return unavailable

        try:
            result = subprocess.run(
                [collector_path, "-t", "-c", "1"],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (subprocess.TimeoutExpired, OSError, ValueError) as e:
            logger.warning("Failed to collect per-process network throughput: %s", str(e))
            return unavailable

        process_entries: List[Dict[str, Any]] = []
        for line in result.stdout.splitlines():
            entry = self._parse_nethogs_process_line(line)
            if entry:
                process_entries.append(entry)

        if not process_entries:
            return unavailable

        return {
            "available": True,
            "reason": "",
            "top": sorted(process_entries, key=lambda item: float(item.get("total_mbps", 0.0)), reverse=True)[:5],
        }

    def _parse_nethogs_process_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a nethogs text-mode line into a process throughput entry."""
        parts = [part.strip() for part in line.split("\t") if part.strip()]
        if len(parts) < 3:
            return None

        identifier = parts[0]
        try:
            sent_kbytes_per_sec = float(parts[1])
            recv_kbytes_per_sec = float(parts[2])
        except ValueError:
            return None

        command = identifier
        user = "unknown"
        pid = 0
        identifier_parts = identifier.rsplit("/", 2)
        if len(identifier_parts) == 3:
            command, pid_value, user = identifier_parts
            try:
                pid = int(pid_value)
            except ValueError:
                pid = 0
        elif len(identifier_parts) == 2:
            command, pid_value = identifier_parts
            try:
                pid = int(pid_value)
            except ValueError:
                pid = 0

        sent_mbps = (sent_kbytes_per_sec * 8.0) / 1000.0
        recv_mbps = (recv_kbytes_per_sec * 8.0) / 1000.0
        return {
            "user": user or "unknown",
            "pid": pid,
            "command": self._sanitize_process_name(command),
            "sent_mbps": sent_mbps,
            "recv_mbps": recv_mbps,
            "total_mbps": sent_mbps + recv_mbps,
        }

    @staticmethod
    def _sanitize_process_name(command: Any) -> str:
        """Return a safe process display name without exposing full command lines."""
        sanitized = os.path.basename(str(command or "").strip())
        return sanitized or "unknown"

    def get_current_stats(self) -> Dict:
        """Get current system resource statistics without threshold checks.

        Returns:
            Dictionary containing current resource statistics.
        """
        stats: Dict[str, Any] = {
            "timestamp": time.time(),
            "cpu": {},
            "memory": {},
            "disk": {},
            "network": {},
            "top_processes": {},
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

            stats["top_processes"] = self._collect_top_process_stats()

        except Exception as e:
            logger.error(f"Error getting resource stats: {str(e)}")
            stats["error"] = str(e)

        return stats
