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

"""Service manager detection and command abstraction.

This module provides a small abstraction layer over Linux service managers
to ensure monitoring and recovery actions work across common distributions.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlatformInfo:
    """Platform metadata derived from /etc/os-release."""

    distro_id: str
    distro_name: str
    distro_like: str
    version_id: str

    @staticmethod
    def _parse_os_release(contents: str) -> Dict[str, str]:
        """Parse /etc/os-release contents into a dictionary.

        Args:
            contents: Raw /etc/os-release file contents.

        Returns:
            Parsed key/value data.
        """
        data: Dict[str, str] = {}
        for line in contents.splitlines():
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"')
        return data

    @classmethod
    def load(cls) -> "PlatformInfo":
        """Load platform information from /etc/os-release.

        Returns:
            PlatformInfo instance with detected metadata.
        """
        os_release_path = "/etc/os-release"
        data: Dict[str, str] = {}
        try:
            if os.path.exists(os_release_path):
                with open(os_release_path, "r", encoding="utf-8") as handle:
                    data = cls._parse_os_release(handle.read())
        except Exception as exc:
            try:
                logger.warning("Failed to read /etc/os-release: %s", exc)
            except Exception:
                pass

        return cls(
            distro_id=data.get("ID", "unknown").lower(),
            distro_name=data.get("NAME", "unknown"),
            distro_like=data.get("ID_LIKE", "").lower(),
            version_id=data.get("VERSION_ID", "unknown"),
        )


class ServiceManager:
    """Detect and execute service manager commands across Linux distributions."""

    @staticmethod
    def _safe_which(command: str) -> Optional[str]:
        """Safely resolve a command path.

        Args:
            command: Command name.

        Returns:
            Resolved path or None on error.
        """
        try:
            return shutil.which(command)
        except Exception:
            return None

    def __init__(self, manager_type: Optional[str] = None, platform_info: Optional[PlatformInfo] = None):
        """Initialize service manager detection.

        Args:
            manager_type: Optional manager override (systemd, sysv, openrc).
            platform_info: Optional platform info override.
        """
        self.platform_info = platform_info or PlatformInfo.load()
        self.manager_type = manager_type or self._detect_manager()

    @property
    def is_systemd(self) -> bool:
        """Return True when systemd is active."""
        return self.manager_type == "systemd"

    @property
    def is_openrc(self) -> bool:
        """Return True when OpenRC is active."""
        return self.manager_type == "openrc"

    @property
    def is_sysv(self) -> bool:
        """Return True when SysV init is active."""
        return self.manager_type == "sysv"

    def supports_patterns(self) -> bool:
        """Return True if service manager supports listing units by pattern."""
        return self.is_systemd

    def build_status_command(self, service_name: str, manager_type: Optional[str] = None) -> Optional[List[str]]:
        """Build a status command for the detected service manager.

        Args:
            service_name: Name of the service to query.
            manager_type: Optional manager override.

        Returns:
            Command list or None if unsupported.
        """
        manager = manager_type or self.manager_type
        if manager == "systemd":
            return ["systemctl", "is-active", service_name]
        if manager == "openrc":
            return ["rc-service", service_name, "status"]
        if manager == "sysv":
            return ["service", service_name, "status"]
        return None

    def build_restart_command(self, service_name: str, manager_type: Optional[str] = None) -> Optional[List[str]]:
        """Build a restart command for the detected service manager.

        Args:
            service_name: Name of the service to restart.
            manager_type: Optional manager override.

        Returns:
            Command list or None if unsupported.
        """
        manager = manager_type or self.manager_type
        if manager == "systemd":
            return ["systemctl", "restart", service_name]
        if manager == "openrc":
            return ["rc-service", service_name, "restart"]
        if manager == "sysv":
            return ["service", service_name, "restart"]
        return None

    def check_service(
        self,
        service_name: str,
        timeout: int = 10,
        manager_type: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[int]]:
        """Check service status using the detected manager.

        Args:
            service_name: Name of the service to query.
            timeout: Command timeout in seconds.
            manager_type: Optional manager override.

        Returns:
            Tuple of (is_running, message, return_code).
        """
        command = self.build_status_command(service_name, manager_type)
        if not command:
            return False, "Unsupported service manager", None

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            stdout = result.stdout.strip()
            if (manager_type or self.manager_type) == "systemd":
                is_running = result.returncode == 0 and stdout == "active"
                message = stdout or "inactive"
            else:
                is_running = result.returncode == 0
                message = stdout or result.stderr.strip()
            return is_running, message, result.returncode
        except subprocess.TimeoutExpired:
            return False, "Status command timeout", None
        except FileNotFoundError:
            return False, "Service manager command not found", None
        except Exception as exc:
            logger.error("Service status check error: %s", exc)
            return False, str(exc), None

    def restart_service(
        self,
        service_name: str,
        timeout: int = 60,
        manager_type: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        """Restart a service using the detected manager.

        Args:
            service_name: Name of the service to restart.
            timeout: Command timeout in seconds.
            manager_type: Optional manager override.

        Returns:
            Dictionary with command, stdout, stderr, returncode, and success.
        """
        command = self.build_restart_command(service_name, manager_type)
        if not command:
            return {
                "command": None,
                "stdout": "",
                "stderr": "Unsupported service manager",
                "returncode": None,
                "success": False,
            }

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "command": " ".join(command),
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {
                "command": " ".join(command),
                "stdout": "",
                "stderr": "Timeout",
                "returncode": None,
                "success": False,
            }
        except FileNotFoundError:
            return {
                "command": " ".join(command),
                "stdout": "",
                "stderr": "Service manager command not found",
                "returncode": None,
                "success": False,
            }
        except Exception as exc:
            logger.error("Service restart error: %s", exc)
            return {
                "command": " ".join(command),
                "stdout": "",
                "stderr": str(exc),
                "returncode": None,
                "success": False,
            }

    def _detect_manager(self) -> str:
        """Detect the active service manager.

        Returns:
            Manager type string (systemd, openrc, sysv, unknown).
        """
        override = os.environ.get("XNETVN_SERVICE_MANAGER")
        if override:
            normalized = override.strip().lower()
            if normalized in {"systemd", "openrc", "sysv"}:
                return normalized

        distro_id = self.platform_info.distro_id
        distro_like = self.platform_info.distro_like

        if distro_id == "alpine":
            if self._safe_which("rc-service"):
                return "openrc"

        systemd_families = {"debian", "ubuntu", "rhel", "fedora", "suse", "arch"}
        if distro_id in systemd_families or any(item in distro_like for item in systemd_families):
            if self._safe_which("systemctl"):
                return "systemd"

        if self._safe_which("systemctl"):
            return "systemd"

        if self._safe_which("rc-service"):
            return "openrc"

        if self._safe_which("service"):
            return "sysv"

        return "unknown"
