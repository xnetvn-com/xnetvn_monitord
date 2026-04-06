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

"""Unit tests for systemd notification helpers."""

import os

from xnetvn_monitord.utils.systemd_notify import SystemdNotifier


def test_should_be_disabled_without_notify_socket(monkeypatch) -> None:
    """Disable notifier when systemd notify socket is unavailable."""
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)

    notifier = SystemdNotifier()

    assert notifier.is_available is False


def test_should_send_ready_and_status_messages(mocker, monkeypatch) -> None:
    """Send READY and STATUS payloads to the systemd notify socket."""
    monkeypatch.setenv("NOTIFY_SOCKET", "@xnetvn-notify")
    socket_instance = mocker.Mock()
    socket_factory = mocker.patch("socket.socket", return_value=socket_instance)

    notifier = SystemdNotifier()

    assert notifier.send_ready("Running version 1.2.3") is True
    socket_factory.assert_called_once()
    socket_instance.sendto.assert_called_once_with(
        b"READY=1\nSTATUS=Running version 1.2.3",
        "\0xnetvn-notify",
    )


def test_should_expose_watchdog_interval_from_environment(monkeypatch) -> None:
    """Read watchdog interval from the systemd environment."""
    monkeypatch.setenv("NOTIFY_SOCKET", "@xnetvn-notify")
    monkeypatch.setenv("WATCHDOG_USEC", "10000000")
    monkeypatch.setenv("WATCHDOG_PID", str(os.getpid()))

    notifier = SystemdNotifier()

    assert notifier.watchdog_interval_seconds == 10.0
    assert notifier.should_ping_watchdog(now=0.0) is True


def test_should_send_watchdog_messages(mocker, monkeypatch) -> None:
    """Send WATCHDOG payloads when systemd watchdog is configured."""
    monkeypatch.setenv("NOTIFY_SOCKET", "@xnetvn-notify")
    monkeypatch.setenv("WATCHDOG_USEC", "10000000")
    monkeypatch.setenv("WATCHDOG_PID", str(os.getpid()))
    socket_instance = mocker.Mock()
    socket_factory = mocker.patch("socket.socket", return_value=socket_instance)
    mocker.patch("xnetvn_monitord.utils.systemd_notify.time.monotonic", return_value=123.0)

    notifier = SystemdNotifier()

    assert notifier.send_watchdog("monitor loop healthy") is True
    socket_factory.assert_called_once()
    socket_instance.sendto.assert_called_once_with(
        b"WATCHDOG=1\nSTATUS=monitor loop healthy",
        "\0xnetvn-notify",
    )
