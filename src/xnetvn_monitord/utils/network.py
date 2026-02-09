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
from typing import Iterator, Tuple
from urllib.parse import urlparse


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

    from typing import Any

    original_getaddrinfo = socket.getaddrinfo

    def _getaddrinfo_ipv4(*args: Any, **kwargs: Any) -> Any:
        # Ensure IPv4 family is used while preserving the original signature
        # We pass through args and kwargs but override the family to AF_INET.
        # This avoids strict typing mismatches with socket.getaddrinfo stubs.
        if len(args) >= 3:
            # (host, port, family, ...)
            args_list = list(args)
            args_list[2] = socket.AF_INET
            return original_getaddrinfo(*args_list, **kwargs)
        else:
            # Fallback: call with explicit family
            host = args[0] if len(args) > 0 else kwargs.get("host")
            port = args[1] if len(args) > 1 else kwargs.get("port")
            return original_getaddrinfo(host, port, socket.AF_INET, *args[2:], **kwargs)

    socket.getaddrinfo = _getaddrinfo_ipv4
    try:
        yield
    finally:
        socket.getaddrinfo = original_getaddrinfo


def is_http_url(url: str, allowed_schemes: Tuple[str, ...] = ("http", "https")) -> bool:
    """Return True when URL uses an allowed HTTP scheme and has a host."""
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in allowed_schemes and bool(parsed.netloc)
