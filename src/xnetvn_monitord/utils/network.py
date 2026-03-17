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

import logging
import socket
import ssl
from contextlib import contextmanager
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import unquote, urlparse
from urllib.request import HTTPSHandler, OpenerDirector, ProxyHandler, Request, build_opener, urlopen

socks: Optional[ModuleType] = None
try:
    import socks  # type: ignore

    _SOCKS_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    socks = None
    _SOCKS_AVAILABLE = False


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


logger = logging.getLogger(__name__)

_ALLOWED_PROXY_SCHEMES = {"http", "https", "socks5", "socks5h"}


@dataclass(frozen=True)
class ProxyInfo:
    """Parsed proxy information."""

    scheme: str
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None


class ProxyConfigurationError(ValueError):
    """Raised when proxy configuration is invalid or unsupported."""


def _normalize_proxy_uri(proxy_uri: Optional[str]) -> Optional[str]:
    """Normalize proxy URI values coming from config or environment.

    Args:
        proxy_uri: Raw proxy URI string.

    Returns:
        Normalized proxy URI or None when empty/disabled.
    """
    if not proxy_uri:
        return None
    normalized = str(proxy_uri).strip()
    if not normalized or normalized.lower() in {"null", "none"}:
        return None
    return normalized


def _parse_proxy_uri(proxy_uri: str) -> ProxyInfo:
    """Parse and validate a proxy URI.

    Args:
        proxy_uri: Proxy URI string.

    Returns:
        Parsed proxy info.

    Raises:
        ProxyConfigurationError: When proxy URI is invalid or unsupported.
    """
    parsed = urlparse(proxy_uri)
    scheme = parsed.scheme.lower()
    if scheme not in _ALLOWED_PROXY_SCHEMES:
        raise ProxyConfigurationError(f"Unsupported proxy scheme: {scheme}")
    if not parsed.hostname or parsed.port is None:
        raise ProxyConfigurationError("Proxy URI must include host and port")
    username = unquote(parsed.username) if parsed.username else None
    password = unquote(parsed.password) if parsed.password else None
    return ProxyInfo(
        scheme=scheme,
        host=parsed.hostname,
        port=int(parsed.port),
        username=username,
        password=password,
    )


def mask_proxy_uri(proxy_uri: str) -> str:
    """Mask credentials in a proxy URI for safe logging.

    Args:
        proxy_uri: Proxy URI string.

    Returns:
        Masked proxy URI string.
    """
    try:
        parsed = urlparse(proxy_uri)
        if parsed.username or parsed.password:
            host = parsed.hostname or ""
            port = f":{parsed.port}" if parsed.port else ""
            return f"{parsed.scheme}://***:***@{host}{port}"
        return proxy_uri
    except Exception:
        return "[invalid proxy uri]"


def redact_url_for_logs(url: str, include_path: bool = False) -> str:
    """Redact credentials and query strings from URLs before logging.

    Args:
        url: Raw URL string.
        include_path: Include the path component without query parameters.

    Returns:
        Sanitized URL label.
    """
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.hostname:
            return "[invalid url]"

        netloc = parsed.hostname
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"

        path = parsed.path if include_path else ""
        return f"{parsed.scheme}://{netloc}{path}"
    except Exception:
        return "[invalid url]"


def read_response_preview(response: Any, limit: int = 256) -> str:
    """Read and sanitize a short response payload preview for logs.

    Args:
        response: Response-like object exposing read().
        limit: Maximum bytes to read.

    Returns:
        A single-line preview string.
    """
    if response is None or not hasattr(response, "read"):
        return ""

    try:
        payload = response.read(limit)
    except Exception:
        return ""

    if isinstance(payload, bytes):
        text = payload.decode("utf-8", errors="replace")
    else:
        text = str(payload)

    return " ".join(text.split())[:limit]


def resolve_proxy_uri(proxy_config: Optional[Dict]) -> Optional[str]:
    """Resolve proxy URI from a configuration dictionary.

    Args:
        proxy_config: Proxy configuration dictionary.

    Returns:
        Proxy URI string or None when disabled.
    """
    if not proxy_config:
        return None

    if isinstance(proxy_config, str):
        return _normalize_proxy_uri(proxy_config)

    enabled = proxy_config.get("enabled")
    if enabled is False:
        return None

    return _normalize_proxy_uri(proxy_config.get("uri"))


@contextmanager
def _use_socks_proxy(proxy_info: ProxyInfo) -> Iterator[None]:
    """Temporarily route sockets through a SOCKS proxy.

    Args:
        proxy_info: Parsed proxy info.
    """
    if not _SOCKS_AVAILABLE:
        raise ProxyConfigurationError("SOCKS proxy requested but PySocks is not installed")

    # Help type checkers understand that `socks` is available here and allow
    # attribute access. Use a local Any-typed reference to avoid ModuleType
    # attribute limitations.
    assert socks is not None
    socks_mod: Any = socks

    proxy_type = socks_mod.SOCKS5
    socks_mod.set_default_proxy(
        proxy_type,
        proxy_info.host,
        proxy_info.port,
        True,
        proxy_info.username,
        proxy_info.password,
    )
    original_socket = socket.socket
    setattr(socket, "socket", socks_mod.socksocket)
    try:
        yield
    finally:
        setattr(socket, "socket", original_socket)


def build_proxy_opener(proxy_uri: str, ssl_context: Optional[ssl.SSLContext]) -> OpenerDirector:
    """Build a urllib opener using the given proxy URI.

    Args:
        proxy_uri: Proxy URI string.
        ssl_context: Optional SSL context for HTTPS.

    Returns:
        urllib opener director.
    """
    proxy_info = _parse_proxy_uri(proxy_uri)
    if proxy_info.scheme.startswith("socks"):
        raise ProxyConfigurationError("SOCKS proxies require socket-level handling")

    handler_map = {"http": proxy_uri, "https": proxy_uri}
    handlers: List[Any] = [ProxyHandler(handler_map)]
    if ssl_context is not None:
        handlers.append(HTTPSHandler(context=ssl_context))
    return build_opener(*handlers)


def open_url(
    request_obj: Request,
    timeout: int,
    ssl_context: Optional[ssl.SSLContext],
    proxy_config: Optional[Dict],
    only_ipv4: bool,
):
    """Open a URL with optional proxy and IPv4 enforcement.

    Args:
        request_obj: urllib Request object.
        timeout: Timeout seconds.
        ssl_context: Optional SSL context.
        proxy_config: Proxy configuration dictionary.
        only_ipv4: Whether to force IPv4 resolution.

    Returns:
        urllib response handle.
    """
    # Validate request URL scheme to avoid allowing file:/ or other unexpected schemes
    url = request_obj.full_url if hasattr(request_obj, "full_url") else request_obj.get_full_url()
    if not is_http_url(url):
        raise ValueError(f"Unsupported URL scheme: {urlparse(url).scheme}")

    proxy_uri = resolve_proxy_uri(proxy_config)
    if not proxy_uri:
        with force_ipv4(only_ipv4):
            if ssl_context is not None:
                return urlopen(request_obj, timeout=timeout, context=ssl_context)
            return urlopen(request_obj, timeout=timeout)

    try:
        proxy_info = _parse_proxy_uri(proxy_uri)
    except ProxyConfigurationError as exc:
        logger.error("Invalid proxy configuration: %s", exc)
        raise

    if proxy_info.scheme.startswith("socks"):
        with _use_socks_proxy(proxy_info):
            with force_ipv4(only_ipv4):
                if ssl_context is not None:
                    return urlopen(request_obj, timeout=timeout, context=ssl_context)
                return urlopen(request_obj, timeout=timeout)

    opener = build_proxy_opener(proxy_uri, ssl_context)
    with force_ipv4(only_ipv4):
        return opener.open(request_obj, timeout=timeout)


def download_url_to_file(
    url: str,
    target_path: str,
    timeout: int,
    proxy_config: Optional[Dict],
    only_ipv4: bool,
) -> None:
    """Download a URL to a file path with optional proxy support.

    Args:
        url: URL to download.
        target_path: Local file path.
        timeout: Timeout seconds.
        proxy_config: Proxy configuration dictionary.
        only_ipv4: Whether to force IPv4 resolution.
    """
    request_obj = Request(url, method="GET")
    with open_url(request_obj, timeout, None, proxy_config, only_ipv4) as response:
        with open(target_path, "wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
