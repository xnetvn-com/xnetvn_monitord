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
import logging
from io import StringIO
from pathlib import Path

import xnetvn_monitord.utils.debug_observability as debug_observability_module
from xnetvn_monitord.utils.debug_observability import (
    DebugObservability,
    ObservabilitySettings,
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


def test_should_skip_content_preview_for_binary_log_files(tmp_path) -> None:
    """Binary log-like files must not add unreadable preview noise."""
    binary_file = tmp_path / "var" / "log" / "faillog"
    binary_file.parent.mkdir(parents=True)
    binary_file.write_bytes(b"\x00\x01\x02\x03binary-data\n")

    snapshot = build_file_snapshot(binary_file)

    assert "content_preview" not in snapshot


def test_should_write_deep_debug_events_only_to_dedicated_file(tmp_path) -> None:
    """Deep debug should isolate observability traffic from the root logger."""
    deep_debug_file = tmp_path / "deep-debug.log"
    settings = ObservabilitySettings(
        enabled=True,
        deep_debug=True,
        deep_debug_source="test",
        deep_debug_file=str(deep_debug_file),
        log_format="%(message)s",
        max_size_mb=1,
        backup_count=1,
        preview_chars=256,
        root_paths=[],
    )

    observability = None
    root_logger = logging.getLogger()
    root_level = root_logger.level
    root_stream = StringIO()
    root_handler = logging.StreamHandler(root_stream)
    root_handler.setLevel(logging.DEBUG)
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(root_handler)

    try:
        observability = DebugObservability(settings)

        observability.emit_event("example", message="hello")
        root_handler.flush()
        assert observability._deep_debug_handler is not None
        observability._deep_debug_handler.flush()

        assert "observability=" not in root_stream.getvalue()
        assert "observability=" in deep_debug_file.read_text(encoding="utf-8")
    finally:
        if observability is not None:
            observability.shutdown()
        root_logger.removeHandler(root_handler)
        root_logger.setLevel(root_level)


def test_should_limit_startup_host_sweep_to_useful_system_logs(monkeypatch, tmp_path) -> None:
    """Startup host sweep should skip noisy app logs and binary system artifacts."""
    host_log_root = tmp_path / "var" / "log"
    (host_log_root / "audit").mkdir(parents=True)
    (host_log_root / "nginx").mkdir(parents=True)

    (host_log_root / "syslog").write_text("syslog line\n", encoding="utf-8")
    (host_log_root / "audit" / "audit.log").write_text("audit line\n", encoding="utf-8")
    (host_log_root / "nginx" / "access.log").write_text("GET /health\n", encoding="utf-8")
    (host_log_root / "faillog").write_bytes(b"\x00\x01\x02")

    settings = ObservabilitySettings(
        enabled=True,
        deep_debug=True,
        deep_debug_source="test",
        deep_debug_file=str(tmp_path / "deep-debug.log"),
        log_format="%(message)s",
        max_size_mb=1,
        backup_count=1,
        preview_chars=256,
        root_paths=[str(host_log_root)],
    )
    observability = DebugObservability(settings)
    snapshots = []

    monkeypatch.setattr(debug_observability_module, "_PROC_SNAPSHOT_FILES", [])
    monkeypatch.setattr(debug_observability_module, "_HOST_COMMANDS", [])
    monkeypatch.setattr(observability, "emit_snapshot", lambda **fields: snapshots.append(fields["snapshot"]))

    try:
        observability.capture_startup_host_state()
    finally:
        observability.shutdown()

    relative_paths = {Path(snapshot["path"]).relative_to(host_log_root).as_posix() for snapshot in snapshots}

    assert "syslog" in relative_paths
    assert "audit/audit.log" in relative_paths
    assert "nginx/access.log" not in relative_paths
    assert "faillog" not in relative_paths


def test_should_skip_emit_event_when_observability_disabled(mocker) -> None:
    """Disabled observability must not emit log payloads."""
    settings = ObservabilitySettings(
        enabled=False,
        deep_debug=False,
        deep_debug_source="test",
        deep_debug_file=None,
        log_format="%(message)s",
        max_size_mb=1,
        backup_count=1,
        preview_chars=64,
        root_paths=[],
    )
    observability = DebugObservability(settings)
    debug_mock = mocker.patch.object(observability.logger, "debug")

    observability.emit_event("ignored", message="hello")

    debug_mock.assert_not_called()


def test_should_wrap_command_http_decision_and_snapshot_events() -> None:
    """Wrapper helpers should normalize previews and event names."""
    settings = ObservabilitySettings(
        enabled=True,
        deep_debug=False,
        deep_debug_source="test",
        deep_debug_file=None,
        log_format="%(message)s",
        max_size_mb=1,
        backup_count=1,
        preview_chars=12,
        root_paths=[],
    )
    observability = DebugObservability(settings)
    emitted = []
    original_emit_event = observability.emit_event
    observability.emit_event = lambda event_type, **fields: emitted.append((event_type, fields))

    try:
        observability.emit_command_result(stdout="alpha\n beta", stderr=" gamma ", code=7)
        observability.emit_http_exchange(response_preview="one\n two\n three")
        observability.emit_decision(result="restart")
        observability.emit_snapshot(source="demo", payload={"ok": True})
    finally:
        observability.emit_event = original_emit_event

    assert observability.is_deep_debug_enabled() is False
    assert emitted[0] == (
        "command_result",
        {"code": 7, "stdout_preview": "alpha beta", "stderr_preview": "gamma"},
    )
    assert emitted[1] == ("http_exchange", {"response_preview": "one two thre"})
    assert emitted[2] == ("decision", {"result": "restart"})
    assert emitted[3] == ("snapshot", {"source": "demo", "payload": {"ok": True}})


def test_should_collect_startup_proc_workdir_and_host_command_details(mocker, monkeypatch, tmp_path) -> None:
    """Deep debug startup sweep should capture curated host state and command previews."""
    proc_file = tmp_path / "proc" / "loadavg"
    proc_file.parent.mkdir(parents=True)
    proc_file.write_text("0.10 0.20 0.30 1/100 123\n", encoding="utf-8")

    host_log_root = tmp_path / "var" / "log"
    host_log_root.mkdir(parents=True)
    (host_log_root / "syslog").write_text("syslog line\n", encoding="utf-8")

    work_dir = tmp_path / "work"
    work_dir.mkdir()

    settings = ObservabilitySettings(
        enabled=True,
        deep_debug=True,
        deep_debug_source="test",
        deep_debug_file=str(tmp_path / "deep-debug.log"),
        log_format="%(message)s",
        max_size_mb=1,
        backup_count=1,
        preview_chars=18,
        root_paths=[str(host_log_root)],
    )
    observability = DebugObservability(settings)
    events = []
    snapshots = []
    command_results = []

    monkeypatch.setattr(debug_observability_module, "_PROC_SNAPSHOT_FILES", [str(proc_file)])
    monkeypatch.setattr(debug_observability_module, "_HOST_COMMANDS", [["demo", "command"]])
    monkeypatch.setattr(
        debug_observability_module.subprocess,
        "run",
        lambda *args, **kwargs: mocker.Mock(returncode=0, stdout="row one\nrow two", stderr="warn "),
    )
    monkeypatch.setattr(observability, "emit_event", lambda event_type, **fields: events.append((event_type, fields)))
    monkeypatch.setattr(observability, "emit_snapshot", lambda **fields: snapshots.append(fields))
    monkeypatch.setattr(observability, "emit_command_result", lambda **fields: command_results.append(fields))

    try:
        observability.capture_startup_host_state(work_dir=str(work_dir))
    finally:
        observability.shutdown()

    assert events[0][0] == "host_startup_sweep_started"
    assert events[-1][0] == "host_startup_sweep_completed"
    assert any(item["source"] == "host_file" and item["snapshot"]["path"] == str(proc_file) for item in snapshots)
    assert any(item["source"] == "host_file" and item["snapshot"]["path"].endswith("/syslog") for item in snapshots)
    assert any(item["source"] == "work_dir" and item["snapshot"]["path"] == str(work_dir) for item in snapshots)
    assert command_results == [
        {
            "source": "host_command",
            "command": ["demo", "command"],
            "returncode": 0,
            "stdout": "row one\nrow two",
            "stderr": "warn ",
            "duration_ms": command_results[0]["duration_ms"],
        }
    ]
    assert command_results[0]["duration_ms"] >= 0


def test_should_parse_bool_preview_and_filter_curated_host_files(tmp_path) -> None:
    """Helper functions should normalize bool env values and curated host file selection."""
    host_log_root = tmp_path / "var" / "log"
    host_log_root.mkdir(parents=True)
    (host_log_root / "syslog").write_text("line\n", encoding="utf-8")
    (host_log_root / "nginx.log").write_text("skip\n", encoding="utf-8")
    text_file = tmp_path / "notes.log"
    text_file.write_text("hello\n", encoding="utf-8")

    selected_paths = {
        path.relative_to(host_log_root).as_posix()
        for path in debug_observability_module._iter_host_sweep_files(host_log_root)
    }

    assert debug_observability_module._parse_bool_env(None) is None
    assert debug_observability_module._parse_bool_env("YeS") is True
    assert debug_observability_module._parse_bool_env("off") is False
    assert debug_observability_module._parse_bool_env("maybe") is None
    assert debug_observability_module._preview_text(" alpha\n beta ", 7) == "alpha b"
    assert debug_observability_module._looks_like_text_file(text_file) is True
    assert selected_paths == {"syslog"}
