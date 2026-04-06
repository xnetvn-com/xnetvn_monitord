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

"""Regression tests for the shipped systemd unit."""

from pathlib import Path


def _read_service_directives() -> dict[str, str]:
    service_path = Path(__file__).resolve().parents[2] / "systemd" / "xnetvn_monitord.service"
    directives: dict[str, str] = {}

    for line in service_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("["):
            continue
        key, value = stripped.split("=", 1)
        directives[key] = value

    return directives


def test_should_configure_watchdog_and_resource_protection() -> None:
    """Keep the installed systemd unit hardened for recovery under host pressure."""
    directives = _read_service_directives()

    assert directives["Type"] == "notify"
    assert directives["WatchdogSec"] == "5min"
    assert directives["NotifyAccess"] == "main"
    assert directives["Nice"] == "-20"
    assert directives["OOMScoreAdjust"] == "-1000"
    assert directives["CPUWeight"] == "10000"
    assert directives["IOWeight"] == "10000"
    assert directives["MemoryLow"] == "64M"
    assert directives["MemoryMin"] == "32M"
