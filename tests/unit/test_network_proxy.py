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

"""Unit tests for proxy helpers."""

from urllib.request import Request

import pytest

from xnetvn_monitord.utils.network import (
    ProxyConfigurationError,
    mask_proxy_uri,
    open_url,
    read_response_preview,
    redact_url_for_logs,
    resolve_proxy_uri,
)


def test_resolve_proxy_uri_disabled_returns_none() -> None:
    """Return None when proxy is disabled or empty."""
    assert resolve_proxy_uri({"enabled": False, "uri": "http://127.0.0.1:8080"}) is None
    assert resolve_proxy_uri({"enabled": True, "uri": ""}) is None


def test_mask_proxy_uri_hides_credentials() -> None:
    """Mask credentials in proxy URI output."""
    masked = mask_proxy_uri("http://user:pass@127.0.0.1:8080")
    assert "user" not in masked
    assert "pass" not in masked
    assert masked.startswith("http://***:***@")


def test_open_url_rejects_invalid_proxy_scheme() -> None:
    """Raise when proxy scheme is unsupported."""
    request_obj = Request("https://example.com", method="GET")
    with pytest.raises(ProxyConfigurationError):
        open_url(
            request_obj,
            timeout=1,
            ssl_context=None,
            proxy_config={"enabled": True, "uri": "ftp://127.0.0.1:8080"},
            only_ipv4=False,
        )


def test_redact_url_for_logs_hides_query_and_credentials() -> None:
    """Hide sensitive URL components in log labels."""
    assert redact_url_for_logs("https://user:pass@example.com/api?token=secret") == "https://example.com"
    assert (
        redact_url_for_logs("https://user:pass@example.com/health/live?token=secret", include_path=True)
        == "https://example.com/health/live"
    )


def test_read_response_preview_returns_empty_when_attribute_access_raises() -> None:
    """Return an empty preview when response.read cannot be accessed safely."""

    class BrokenResponse:
        def __getattr__(self, name: str):
            if name == "read":
                raise KeyError("file")
            raise AttributeError(name)

    assert read_response_preview(BrokenResponse()) == ""
