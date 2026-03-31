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

"""Unit tests for debug observability helpers."""

from __future__ import annotations

import json
from pathlib import Path

from xnetvn_monitord.utils.debug_observability import (
    build_file_snapshot,
    resolve_observability_settings,
    sanitize_observability_value,
)


def test_should_enable_deep_debug_from_env_override(monkeypatch, tmp_path) -> None:
    """Env override must force deep debug on when level=DEBUG."""
    monkeypatch.setenv("XNETVN_MONITORD_DEEP_DEBUG", "1")

    settings = resolve_observability_settings(
        {
            "enabled": True,
            "level": "DEBUG",
            "deep_debug": False,
            "deep_debug_file": str(tmp_path / "deep-debug.log"),
        }
    )

    assert settings.enabled is True
    assert settings.deep_debug is True
    assert settings.deep_debug_source == "env:XNETVN_MONITORD_DEEP_DEBUG"


def test_should_disable_deep_debug_when_level_not_debug(monkeypatch, tmp_path) -> None:
    """Deep debug must stay off unless the daemon log level is DEBUG."""
    monkeypatch.setenv("XNETVN_MONITORD_DEEP_DEBUG", "1")

    settings = resolve_observability_settings(
        {
            "enabled": True,
            "level": "INFO",
            "deep_debug": True,
            "deep_debug_file": str(tmp_path / "deep-debug.log"),
        }
    )

    assert settings.enabled is False
    assert settings.deep_debug is False
    assert settings.deep_debug_source == "disabled:log-level"


def test_should_redact_sensitive_metadata_values() -> None:
    """Sensitive fields must be redacted before diagnostic logging."""
    payload = {
        "url": "https://user:pass@example.com/api/health?token=secret-token",
        "proxy_uri": "http://user:pass@127.0.0.1:8080",
        "headers": {
            "Authorization": "Bearer super-secret-token",
            "X-Api-Key": "sensitive-key",
        },
        "stderr": "password=super-secret token=other-secret webhook_url=https://hooks.example.com/abc",
    }

    sanitized = sanitize_observability_value(payload)
    rendered = json.dumps(sanitized, sort_keys=True)

    assert "super-secret-token" not in rendered
    assert "other-secret" not in rendered
    assert "sensitive-key" not in rendered
    assert "user:pass" not in rendered
    assert "https://example.com/api/health" in rendered
    assert "http://***:***@127.0.0.1:8080" in rendered
    assert "[REDACTED]" in rendered


def test_should_only_include_content_preview_for_log_like_paths(tmp_path) -> None:
    """Host sweep should capture content only from telemetry-like files."""
    log_file = tmp_path / "var" / "log" / "syslog"
    log_file.parent.mkdir(parents=True)
    log_file.write_text("first line\nsecond line\n", encoding="utf-8")

    secret_file = tmp_path / "etc" / "shadow"
    secret_file.parent.mkdir(parents=True)
    secret_file.write_text("root:$6$secret-hash\n", encoding="utf-8")

    log_snapshot = build_file_snapshot(log_file)
    secret_snapshot = build_file_snapshot(secret_file)

    assert log_snapshot["content_preview"] == ["first line", "second line"]
    assert "content_preview" not in secret_snapshot
    assert secret_snapshot["path"].endswith(str(Path("etc") / "shadow"))
