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

"""Unit tests for ServiceManager."""

from xnetvn_monitord.utils import service_manager
from xnetvn_monitord.utils.service_manager import PlatformInfo, ServiceManager


def test_should_use_env_override(monkeypatch) -> None:
    monkeypatch.setenv("XNETVN_SERVICE_MANAGER", "openrc")
    platform_info = PlatformInfo(
        distro_id="ubuntu",
        distro_name="Ubuntu",
        distro_like="debian",
        version_id="22.04",
    )

    manager = ServiceManager(platform_info=platform_info)

    assert manager.manager_type == "openrc"


def test_should_detect_systemd_for_debian_family(monkeypatch) -> None:
    platform_info = PlatformInfo(
        distro_id="debian",
        distro_name="Debian",
        distro_like="debian",
        version_id="12",
    )

    def fake_which(command: str):
        if command == "systemctl":
            return "/bin/systemctl"
        return None

    monkeypatch.setattr(service_manager.shutil, "which", fake_which)

    manager = ServiceManager(platform_info=platform_info)

    assert manager.manager_type == "systemd"


def test_should_detect_openrc_for_alpine(monkeypatch) -> None:
    platform_info = PlatformInfo(
        distro_id="alpine",
        distro_name="Alpine",
        distro_like="",
        version_id="3.19",
    )

    def fake_which(command: str):
        if command == "rc-service":
            return "/sbin/rc-service"
        return None

    monkeypatch.setattr(service_manager.shutil, "which", fake_which)

    manager = ServiceManager(platform_info=platform_info)

    assert manager.manager_type == "openrc"


def test_should_build_sysv_commands() -> None:
    platform_info = PlatformInfo(
        distro_id="ubuntu",
        distro_name="Ubuntu",
        distro_like="debian",
        version_id="22.04",
    )

    manager = ServiceManager(manager_type="sysv", platform_info=platform_info)

    assert manager.build_status_command("nginx") == ["service", "nginx", "status"]
    assert manager.build_restart_command("nginx") == ["service", "nginx", "restart"]
