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

"""Minimal systemd notification helpers."""

from __future__ import annotations

import logging
import os
import socket
import time
from typing import Optional

logger = logging.getLogger(__name__)


class SystemdNotifier:
    """Send readiness, watchdog, and status updates to systemd."""

    def __init__(self, notify_socket: Optional[str] = None):
        """Initialize the notifier.

        Args:
            notify_socket: Optional NOTIFY_SOCKET override.
        """
        self.notify_socket = notify_socket if notify_socket is not None else os.environ.get("NOTIFY_SOCKET")
        self.watchdog_interval_seconds = self._load_watchdog_interval_seconds()
        self._last_watchdog_ping = 0.0

    @property
    def is_available(self) -> bool:
        """Return True when a systemd notification socket is available."""
        return bool(self.notify_socket)

    @property
    def watchdog_enabled(self) -> bool:
        """Return True when systemd watchdog integration is active."""
        return self.is_available and self.watchdog_interval_seconds is not None

    def send_status(self, status: str) -> bool:
        """Send a STATUS update to systemd."""
        return self._send(f"STATUS={status}")

    def send_ready(self, status: Optional[str] = None) -> bool:
        """Send READY=1 and optional STATUS to systemd."""
        payload = ["READY=1"]
        if status:
            payload.append(f"STATUS={status}")
        return self._send("\n".join(payload))

    def send_stopping(self, status: Optional[str] = None) -> bool:
        """Send STOPPING=1 and optional STATUS to systemd."""
        payload = ["STOPPING=1"]
        if status:
            payload.append(f"STATUS={status}")
        return self._send("\n".join(payload))

    def should_ping_watchdog(self, now: Optional[float] = None) -> bool:
        """Return True when a watchdog keepalive is due."""
        if not self.watchdog_enabled:
            return False

        current_time = time.monotonic() if now is None else now
        if self._last_watchdog_ping <= 0.0:
            return True

        assert self.watchdog_interval_seconds is not None
        return (current_time - self._last_watchdog_ping) >= (self.watchdog_interval_seconds / 2.0)

    def send_watchdog(self, status: Optional[str] = None, now: Optional[float] = None) -> bool:
        """Send a WATCHDOG keepalive and optional STATUS update."""
        if not self.watchdog_enabled:
            return False

        payload = ["WATCHDOG=1"]
        if status:
            payload.append(f"STATUS={status}")

        if not self._send("\n".join(payload)):
            return False

        self._last_watchdog_ping = time.monotonic() if now is None else now
        return True

    def _send(self, payload: str) -> bool:
        """Send a raw payload to the systemd notification socket."""
        if not self.is_available:
            return False

        client = None
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            client.sendto(payload.encode("utf-8"), self._get_socket_address())
            return True
        except OSError as exc:
            logger.debug("Failed to publish systemd status: %s", exc)
            return False
        finally:
            if client is not None:
                try:
                    client.close()
                except OSError:
                    pass

    def _get_socket_address(self) -> str:
        """Return the Unix domain socket address used by systemd."""
        assert self.notify_socket is not None
        if self.notify_socket.startswith("@"):
            return f"\0{self.notify_socket[1:]}"
        return self.notify_socket

    def _load_watchdog_interval_seconds(self) -> Optional[float]:
        """Read the configured watchdog interval from the systemd environment."""
        watchdog_usec = os.environ.get("WATCHDOG_USEC")
        if not watchdog_usec:
            return None

        watchdog_pid = os.environ.get("WATCHDOG_PID")
        if watchdog_pid:
            try:
                if int(watchdog_pid) != os.getpid():
                    return None
            except ValueError:
                return None

        try:
            interval_usec = int(watchdog_usec)
        except ValueError:
            return None

        if interval_usec <= 0:
            return None

        return interval_usec / 1_000_000.0
