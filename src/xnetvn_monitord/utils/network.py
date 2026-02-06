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

"""Network utilities for connection behavior tuning."""

from __future__ import annotations

import socket
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def force_ipv4(enabled: bool) -> Iterator[None]:
    """Force IPv4 DNS resolution for the duration of the context.

    Args:
        enabled: When True, only IPv4 addresses are resolved.

    Yields:
        None.
    """
    if not enabled:
        yield
        return

    original_getaddrinfo = socket.getaddrinfo

    def _getaddrinfo_ipv4(
        host: str,
        port: int,
        family: int = 0,
        type: int = 0,
        proto: int = 0,
        flags: int = 0,
    ):
        return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = _getaddrinfo_ipv4
    try:
        yield
    finally:
        socket.getaddrinfo = original_getaddrinfo
