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

    assert notifier.send_ready("Running version 1.2.2") is True
    socket_factory.assert_called_once()
    socket_instance.sendto.assert_called_once_with(
        b"READY=1\nSTATUS=Running version 1.2.2",
        "\0xnetvn-notify",
    )
