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

"""Debug observability helpers for DEBUG and deep-debug modes."""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .network import mask_proxy_uri, redact_url_for_logs

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
_DEFAULT_REDACT_PATTERNS = [
    r"(?i)(authorization|x-api-key|api[_-]?key)[:=]\s*[^\s,;]+",
    r"(?i)(token|password|secret|webhook_url)[:=]\s*[^\s,;]+",
    r"(?i)bearer\s+[a-z0-9._\-]+",
]
_LOG_LIKE_FILENAMES = {"syslog", "messages", "auth.log", "kern.log", "audit.log", "journal"}
_PROC_SNAPSHOT_FILES = [
    "/proc/loadavg",
    "/proc/meminfo",
    "/proc/pressure/cpu",
    "/proc/pressure/memory",
    "/proc/pressure/io",
    "/proc/diskstats",
    "/proc/net/dev",
]
_SYSTEM_LOG_RELATIVE_PATHS = {
    "alternatives.log",
    "auth.log",
    "audit/audit.log",
    "cloud-init-output.log",
    "cloud-init.log",
    "kern.log",
    "messages",
    "syslog",
}
_TEXT_SAMPLE_BYTES = 2048
_MAX_PREVIEW_READ_BYTES = 8192
_HOST_COMMANDS = [
    ["journalctl", "-n", "200", "--no-pager", "-o", "short-iso"],
    ["ps", "aux"],
    ["df", "-h"],
    ["ss", "-tunap"],
    ["ip", "-brief", "addr"],
    ["ip", "route"],
    ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--no-legend"],
]


@dataclass(frozen=True)
class ObservabilitySettings:
    """Resolved runtime settings for debug observability."""

    enabled: bool
    deep_debug: bool
    deep_debug_source: str
    deep_debug_file: Optional[str]
    log_format: str
    max_size_mb: int
    backup_count: int
    preview_chars: int
    redact_patterns: List[str] = field(default_factory=list)
    redact_replacement: str = "[REDACTED]"
    root_paths: List[str] = field(default_factory=lambda: ["/var/log"])


class NullDebugObservability:
    """No-op observability implementation for non-DEBUG runs."""

    def __init__(self, settings: Optional[ObservabilitySettings] = None) -> None:
        self.settings = settings

    def is_deep_debug_enabled(self) -> bool:
        return False

    def emit_event(self, event_type: str, **fields: Any) -> None:
        return None

    def emit_command_result(self, **fields: Any) -> None:
        return None

    def emit_http_exchange(self, **fields: Any) -> None:
        return None

    def emit_decision(self, **fields: Any) -> None:
        return None

    def emit_snapshot(self, **fields: Any) -> None:
        return None

    def capture_startup_host_state(self, **fields: Any) -> None:
        return None

    def shutdown(self) -> None:
        return None


class DebugObservability:
    """Structured debug observability sink for daemon diagnostics."""

    def __init__(self, settings: ObservabilitySettings) -> None:
        self.settings = settings
        self.logger = logging.getLogger("xnetvn_monitord.observability")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = not self.settings.deep_debug
        self._deep_debug_handler: Optional[logging.Handler] = None
        if self.settings.deep_debug and self.settings.deep_debug_file:
            self._configure_deep_debug_handler()

    def _configure_deep_debug_handler(self) -> None:
        deep_debug_path = Path(self.settings.deep_debug_file or "")
        deep_debug_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            str(deep_debug_path),
            maxBytes=max(1, self.settings.max_size_mb) * 1024 * 1024,
            backupCount=max(1, self.settings.backup_count),
        )
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(self.settings.log_format))
        self.logger.addHandler(handler)
        self._deep_debug_handler = handler

    def is_deep_debug_enabled(self) -> bool:
        return self.settings.deep_debug

    def emit_event(self, event_type: str, **fields: Any) -> None:
        if not self.settings.enabled:
            return

        payload = {
            "event_type": event_type,
            "timestamp": time.time(),
            **sanitize_observability_value(
                fields,
                patterns=self.settings.redact_patterns,
                redact_replacement=self.settings.redact_replacement,
            ),
        }
        self.logger.debug("observability=%s", json.dumps(payload, sort_keys=True, default=str))

    def emit_command_result(self, **fields: Any) -> None:
        payload = dict(fields)
        if "stdout" in payload:
            payload["stdout_preview"] = _preview_text(payload.pop("stdout"), self.settings.preview_chars)
        if "stderr" in payload:
            payload["stderr_preview"] = _preview_text(payload.pop("stderr"), self.settings.preview_chars)
        self.emit_event("command_result", **payload)

    def emit_http_exchange(self, **fields: Any) -> None:
        payload = dict(fields)
        if "response_preview" in payload:
            payload["response_preview"] = _preview_text(payload["response_preview"], self.settings.preview_chars)
        self.emit_event("http_exchange", **payload)

    def emit_decision(self, **fields: Any) -> None:
        self.emit_event("decision", **fields)

    def emit_snapshot(self, **fields: Any) -> None:
        self.emit_event("snapshot", **fields)

    def capture_startup_host_state(
        self,
        work_dir: Optional[str] = None,
        resource_monitor: Optional[Any] = None,
    ) -> None:
        if not self.settings.deep_debug:
            return

        self.emit_event(
            "host_startup_sweep_started",
            work_dir=work_dir,
            deep_debug_source=self.settings.deep_debug_source,
            host_paths=self.settings.root_paths,
        )

        if resource_monitor is not None:
            try:
                self.emit_snapshot(
                    source="resource_monitor.get_current_stats",
                    snapshot=resource_monitor.get_current_stats(),
                )
            except Exception as exc:  # pragma: no cover - defensive logging path
                self.emit_event("host_startup_resource_snapshot_failed", error=str(exc))

        for file_path in _PROC_SNAPSHOT_FILES:
            path = Path(file_path)
            if path.is_file() and os.access(path, os.R_OK):
                self.emit_snapshot(source="host_file", snapshot=build_file_snapshot(path))

        for root_path in self.settings.root_paths:
            root = Path(root_path)
            if root.exists():
                for path in _iter_host_sweep_files(root):
                    self.emit_snapshot(
                        source="host_file",
                        snapshot=build_file_snapshot(
                            path,
                            preview_chars=self.settings.preview_chars,
                        ),
                    )

        if work_dir:
            work_dir_path = Path(work_dir)
            if work_dir_path.exists():
                self.emit_snapshot(source="work_dir", snapshot=build_file_snapshot(work_dir_path))

        for command in _HOST_COMMANDS:
            started_at = time.monotonic()
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.emit_command_result(
                    source="host_command",
                    command=command,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    duration_ms=(time.monotonic() - started_at) * 1000,
                )
            except Exception as exc:  # pragma: no cover - defensive logging path
                self.emit_command_result(
                    source="host_command",
                    command=command,
                    returncode=None,
                    stdout="",
                    stderr=str(exc),
                    duration_ms=(time.monotonic() - started_at) * 1000,
                )

        self.emit_event("host_startup_sweep_completed")

    def shutdown(self) -> None:
        if self._deep_debug_handler is not None:
            self.logger.removeHandler(self._deep_debug_handler)
            self._deep_debug_handler.close()
            self._deep_debug_handler = None


def _parse_bool_env(raw_value: Optional[str]) -> Optional[bool]:
    if raw_value is None:
        return None
    normalized = raw_value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return None


def _preview_text(value: Any, limit: int) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split())
    return text[:limit]


def _iter_readable_files(root: Path) -> Iterable[Path]:
    for current_root, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [name for name in dirnames if not Path(current_root, name).is_symlink()]
        for filename in filenames:
            path = Path(current_root, filename)
            if path.is_symlink() or not path.is_file() or not os.access(path, os.R_OK):
                continue
            yield path


def _iter_host_sweep_files(root: Path) -> Iterable[Path]:
    for path in _iter_readable_files(root):
        if _should_capture_host_file(root, path):
            yield path


def _should_capture_host_file(root: Path, path: Path) -> bool:
    try:
        relative_path = path.relative_to(root).as_posix().lower()
    except ValueError:
        return False

    return relative_path in _SYSTEM_LOG_RELATIVE_PATHS


def _should_capture_content_preview(path: Path) -> bool:
    path_text = path.as_posix().lower()
    return "/var/log/" in path_text or path.name.lower().endswith(".log") or path.name.lower() in _LOG_LIKE_FILENAMES


def _looks_like_text_file(path: Path, sample_size: int = _TEXT_SAMPLE_BYTES) -> bool:
    try:
        with path.open("rb") as handle:
            sample = handle.read(sample_size)
    except OSError:
        return False

    if not sample:
        return True
    if b"\x00" in sample:
        return False

    control_bytes = sum(1 for byte in sample if byte < 32 and byte not in {9, 10, 13})
    return control_bytes / len(sample) < 0.10


def build_file_snapshot(path: Path, preview_lines: int = 20, preview_chars: int = 256) -> Dict[str, Any]:
    path = Path(path)
    snapshot: Dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "is_file": path.is_file(),
    }
    if not path.exists():
        return snapshot

    try:
        stat_result = path.stat()
        snapshot["size_bytes"] = int(stat_result.st_size)
        snapshot["mode"] = oct(stat_result.st_mode & 0o777)
        snapshot["mtime_epoch"] = float(stat_result.st_mtime)
    except OSError:
        return snapshot

    if path.is_file() and _should_capture_content_preview(path) and _looks_like_text_file(path):
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                lines = []
                remaining_bytes = _MAX_PREVIEW_READ_BYTES
                for _ in range(preview_lines):
                    if remaining_bytes <= 0:
                        break

                    line = handle.readline(remaining_bytes + 1)
                    if not line:
                        break

                    remaining_bytes -= len(line.encode("utf-8", errors="ignore"))
                    stripped = line.rstrip("\n")
                    if stripped:
                        lines.append(_preview_text(stripped, preview_chars))

                if lines:
                    snapshot["content_preview"] = lines
        except OSError:
            pass

    return snapshot


def sanitize_observability_value(
    value: Any,
    *,
    key: Optional[str] = None,
    patterns: Optional[List[str]] = None,
    redact_replacement: str = "[REDACTED]",
) -> Any:
    redact_patterns = patterns or list(_DEFAULT_REDACT_PATTERNS)

    if isinstance(value, dict):
        return {
            str(sub_key): sanitize_observability_value(
                sub_value,
                key=str(sub_key),
                patterns=redact_patterns,
                redact_replacement=redact_replacement,
            )
            for sub_key, sub_value in value.items()
        }

    if isinstance(value, list):
        return [
            sanitize_observability_value(item, key=key, patterns=redact_patterns, redact_replacement=redact_replacement)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            sanitize_observability_value(item, key=key, patterns=redact_patterns, redact_replacement=redact_replacement)
            for item in value
        ]

    if key:
        normalized_key = key.lower()
        if normalized_key in {"url", "target", "release_url", "tarball_url"}:
            return redact_url_for_logs(str(value), include_path=True)
        if normalized_key in {"proxy_uri", "proxy"}:
            return mask_proxy_uri(str(value))
        if normalized_key in {"authorization", "x-api-key", "api-key", "token", "password", "secret"}:
            return redact_replacement

    if isinstance(value, str):
        sanitized = value
        for pattern in redact_patterns:
            sanitized = re.sub(pattern, redact_replacement, sanitized)
        return sanitized

    return value


def resolve_observability_settings(
    logging_config: Dict[str, Any],
    notifications_config: Optional[Dict[str, Any]] = None,
) -> ObservabilitySettings:
    notifications_config = notifications_config or {}
    content_filter_config = notifications_config.get("content_filter", {})
    logging_enabled = bool(logging_config.get("enabled", True))
    log_level = str(logging_config.get("level", "INFO") or "INFO").upper()
    debug_level_enabled = logging_enabled and log_level == "DEBUG"

    env_override = _parse_bool_env(os.environ.get("XNETVN_MONITORD_DEEP_DEBUG"))
    if env_override is None:
        requested_deep_debug = bool(logging_config.get("deep_debug", False))
        deep_debug_source = "config:general.logging.deep_debug" if requested_deep_debug else "config:default:false"
    else:
        requested_deep_debug = env_override
        deep_debug_source = "env:XNETVN_MONITORD_DEEP_DEBUG"

    if not logging_enabled:
        enabled = False
        deep_debug = False
        deep_debug_source = "disabled:logging"
    elif not debug_level_enabled:
        enabled = False
        deep_debug = False
        deep_debug_source = "disabled:log-level"
    else:
        enabled = True
        deep_debug = requested_deep_debug

    default_log_file = str(logging_config.get("file", "/var/log/xnetvn_monitord/monitor.log"))
    deep_debug_file = logging_config.get("deep_debug_file")
    if not deep_debug_file:
        deep_debug_file = str(Path(default_log_file).with_name("deep-debug.log"))

    return ObservabilitySettings(
        enabled=enabled,
        deep_debug=deep_debug,
        deep_debug_source=deep_debug_source,
        deep_debug_file=str(deep_debug_file) if deep_debug_file else None,
        log_format=str(logging_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")),
        max_size_mb=int(logging_config.get("deep_debug_max_size_mb", logging_config.get("max_size_mb", 100))),
        backup_count=int(logging_config.get("deep_debug_backup_count", logging_config.get("backup_count", 10))),
        preview_chars=int(logging_config.get("preview_chars", 256)),
        redact_patterns=list(content_filter_config.get("redact_patterns", [])) or list(_DEFAULT_REDACT_PATTERNS),
        redact_replacement=str(content_filter_config.get("redact_replacement", "[REDACTED]")),
    )


_ACTIVE_OBSERVABILITY: DebugObservability | NullDebugObservability = NullDebugObservability()


def configure_debug_observability(
    logging_config: Dict[str, Any],
    notifications_config: Optional[Dict[str, Any]] = None,
) -> DebugObservability | NullDebugObservability:
    global _ACTIVE_OBSERVABILITY
    _ACTIVE_OBSERVABILITY.shutdown()
    settings = resolve_observability_settings(logging_config, notifications_config)
    if settings.enabled:
        _ACTIVE_OBSERVABILITY = DebugObservability(settings)
    else:
        _ACTIVE_OBSERVABILITY = NullDebugObservability(settings)
    return _ACTIVE_OBSERVABILITY


def get_debug_observability() -> DebugObservability | NullDebugObservability:
    return _ACTIVE_OBSERVABILITY
