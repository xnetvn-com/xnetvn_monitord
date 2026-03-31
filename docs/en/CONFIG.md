---
post_title: "Configuration"
author1: "xNetVN Inc."
post_slug: "docs-en-config"
microsoft_alias: ""
featured_image: ""
categories:
  - monitoring
tags:
  - configuration
  - yaml
ai_note: "AI-assisted"
summary: "Configuration guide for xnetvn_monitord based on main.example.yaml."
post_date: "2026-02-03"
---

## Configuration

This document describes the main configuration blocks in config/main.yaml.

## Overview

Primary sections:

- general: application metadata, logging, PID.
- network: outbound networking defaults.
- update_checker: GitHub Releases update checks.
- service_monitor: service configuration (check method, interval, restart).
- resource_monitor: CPU/Memory/Disk monitoring and recovery.
- notifications: Email/Telegram/Slack/Discord/Webhook configuration.

## general

- app_name: display metadata.
- Legacy `general.app_version` values from older configs are ignored; update
  decisions use the running package version.
- check_interval: main loop interval (seconds).
- logging: level, file, rotation.
- pid_file, work_dir: PID and runtime directory.


### general.logging.level

`general.logging.level` controls the minimum severity emitted by the daemon's
root logger, the rotating file handler, and the stdout console handler. In
practice, this means the setting affects nearly all module logs that propagate
through Python's standard logging hierarchy.

- Default value: `INFO`.
- Supported values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
- Input is case-insensitive: `info` and `INFO` are treated the same.
- Invalid values are rejected during configuration loading with a clear
  `ValueError` on `general.logging.level`.

Recommended usage:

| Level | Use when | Operational tradeoff |
|------|---------|----------------------|
| `DEBUG` | Investigating bugs, startup issues, or unexpected monitor behavior | Highest log volume; use temporarily |
| `INFO` | Normal day-to-day production monitoring | Best default balance of visibility and noise |
| `WARNING` | You only want anomalous or degraded-but-recoverable events | Hides routine success and lifecycle logs |
| `ERROR` | You want to focus on failed checks or failed recovery actions only | Can hide early warning signals before incidents escalate |
| `CRITICAL` | Emergency-only logging during severe incident triage | Too narrow for normal operation |

- The same level is applied to both `/var/log/xnetvn_monitord/monitor.log` and stdout.

### general.logging.deep_debug and related keys

`general.logging.deep_debug` is only effective when both of these conditions are true:

- `general.logging.enabled: true`
- `general.logging.level: DEBUG`

Behavior by mode:

- `DEBUG` with `deep_debug: false`: the daemon emits expanded internal observability events into the normal log handlers. These events cover daemon decision paths, retry timing, command stdout/stderr previews, redacted HTTP request/response previews, and resource snapshots gathered directly by `xnetvn_monitord`.
- `DEBUG` with `deep_debug: true`: observability traffic moves into the dedicated deep debug log instead of the normal handlers and adds a curated startup host sweep written to that same file.

Supported keys:

- `general.logging.deep_debug`: enables the startup host sweep layer.
- `general.logging.deep_debug_file`: optional dedicated file for deep debug output. If omitted, the daemon derives a sibling `deep-debug.log` path from `general.logging.file`.
- `general.logging.deep_debug_max_size_mb`: rotation size for the deep debug file.
- `general.logging.deep_debug_backup_count`: number of rotated deep debug files to retain.
- `general.logging.preview_chars`: truncation limit for command and HTTP previews.

Environment override:

- `XNETVN_MONITORD_DEEP_DEBUG=1`, `true`, `yes`, or `on` forces deep debug on.
- `XNETVN_MONITORD_DEEP_DEBUG=0`, `false`, `no`, or `off` forces deep debug off.
- The environment variable takes precedence over YAML, but deep debug is still disabled unless the main logging level is `DEBUG`.

Current deep debug startup sweep sources:

- readable `/proc` telemetry snapshots such as load, memory, PSI, disk, and network counters
- selected core text logs under `/var/log`, currently limited to `syslog`, `messages`, `auth.log`, `kern.log`, `cloud-init.log`, `cloud-init-output.log`, `alternatives.log`, and `audit/audit.log`
- metadata snapshot for `general.work_dir`
- best-effort command output from `journalctl`, `ps aux`, `df -h`, `ss -tunap`, `ip -brief addr`, `ip route`, and `systemctl list-units`

Safety boundaries:

- Sensitive values are redacted before logging.
- HTTP bodies, command previews, and host-log line previews are truncated to `general.logging.preview_chars`.
- Binary files, `/var/log/journal/*`, and noisy app or web logs outside the curated list are skipped from content capture.
- Non-log-like files are recorded as metadata snapshots only; their content is not copied into the deep debug log.
- The same `notifications.content_filter.redact_patterns` and `redact_replacement` settings are reused for observability redaction.

## network

- only_ipv4: when true, outbound DNS resolution and HTTP calls use IPv4 only.
  This applies to service HTTP checks, notification webhooks, and update checks.

Proxy is configured per-service (update_checker, service_monitor HTTP checks,
and each notification channel) rather than globally.

## update_checker

```yaml
update_checker:
  enabled: true
  proxy:
    enabled: true
    uri: "${PROXY_URI}"
  interval:
    value: 1
    unit: "weeks"
  notify_on_update: false
  auto_update: false
  github_repo: "xnetvn-com/xnetvn_monitord"
  github_api_base_url: "https://api.github.com"
  state_file: "/opt/xnetvn_monitord/.local/tmp/update_check.json"
  service_name: "xnetvn_monitord"
```

- GITHUB_TOKEN can be set in the environment to avoid rate limits.
- auto_update is best-effort, refreshes the installed `scripts/update.sh` plus
  example config files, and restarts the service after updating.

## service_monitor

Supported check_method values:

- systemctl, auto, service, openrc
- process, process_regex
- custom_command
- iptables
- http, https

Key fields:

- check_interval: number or {value, unit}.
- action_cooldown, max_restart_attempts, restart_wait_time, restart_cooldown.
- service_name, service_name_pattern (systemd).
- process_name, process_pattern, process_patterns, multi_instance.
- url, http_method, headers, expected_status_codes, max_response_time_ms,
  verify_tls.
- restart_command: string or list of commands.
- pre_restart_hook, post_restart_hook.
- check_command/check_timeout can also be used with iptables to override the
  default command.

Iptables check example:

```yaml
service_monitor:
  services:
    - name: "iptables"
      enabled: false
      check_method: "iptables"
      check_timeout: 10
      # check_command: "iptables -L -n"
      restart_command:
        - "systemctl restart netfilter-persistent"
        - "systemctl restart iptables"
```

List-based restart_command example:

```yaml
service_monitor:
  services:
    - name: "nginx"
      restart_command:
        - "systemctl restart nginx"
        - "bash /opt/xnetvn_monitord/scripts/custom-restart.sh"

Per-service proxy example (HTTP/HTTPS checks only):

```yaml
service_monitor:
  services:
    - name: "web_homepage"
      check_method: "https"
      url: "https://example.com/health"
      proxy:
        enabled: true
        uri: "${PROXY_URI}"
```

## resource_monitor

### cpu_load

```yaml
resource_monitor:
  cpu_load:
    enabled: true
    check_1min: true
    threshold_1min: 95.0
    check_5min: true
    threshold_5min: 80.0
    check_15min: false
    threshold_15min: 60.0
    recovery_command: "systemctl restart heavy-worker"
```

- recovery_command is executed by the shell with a 60s timeout.

### memory

```yaml
resource_monitor:
  memory:
    enabled: true
    free_percent_threshold: 5.0
    free_mb_threshold: 512
    condition: "or"
```

### disk

```yaml
resource_monitor:
  disk:
    enabled: true
    mount_points:
      - path: "/"
        free_percent_threshold: 10.0
        free_gb_threshold: 5.0
```

- Both paths (string) and mount_points (dict) are supported for backward
  compatibility.
- action_on_threshold is active and supports three values:
  - notify: preserve the existing low-disk recovery flow without filesystem cleanup.
  - cleanup: execute quarantine-based cleanup only.
  - both: execute quarantine-based cleanup first, then restart low_disk_services.
- disk.cleanup enables quarantine-first cleanup with exact/regex/glob selectors,
  minimum age/size rules, protected path enforcement, same-filesystem quarantine
  validation, and bounded scan limits for low server overhead.
- Quarantined items are recorded in JSON manifests under the quarantine
  directory so operators can restore one manifest or the full quarantine set
  before any later purge step.

## recovery_actions

```yaml
resource_monitor:
  recovery_actions:
    cooldown_period: 1800
    restart_interval: 5
    high_cpu_services:
      - "nginx"
    low_memory_services: []
    low_disk_services: []
```

- cooldown_period applies per action_type.
- ResourceMonitor restarts services from these lists when thresholds are exceeded.
- low_disk_services are executed for disk alerts in notify mode and after
  cleanup in both mode.

## notifications

Global settings:

- notifications.enabled, min_severity.
- rate_limit: min_interval, max_per_hour.
- content_filter: redact_patterns, redact_replacement.
- Notification bodies include the local hostname at the top of each message.

Each channel (email/telegram/slack/discord/webhook) has:

- enabled, test_on_startup (if supported).
- min_severity override.
- rate_limit override (optional).
- Telegram chat IDs support topic routing with the format -100XXXX_YYY,
  where YYY is the topic (message_thread_id).
- When `include_system_stats` is enabled for a channel, event reports also
  include top-5 process diagnostics for CPU %, CPU core load, RAM MB/RAM %,
  disk I/O, and best-effort network Mbps.
- Process diagnostics only expose the executable name, user, PID, and
  resource counters; full command lines are never included in outbound
  notifications.
- Process-level network throughput requires an optional collector such as
  `nethogs` and sufficient privileges. If unavailable, reports explicitly
  mark network process throughput as unavailable instead of fabricating data.
- Telegram, Slack, and Discord reports hide `system_stats.network.interfaces`
  to keep chat messages concise while preserving the rest of `System Stats`.
- On startup, the daemon sends a shared startup summary to every enabled channel
  with hostname, version, startup time, check_interval, enabled channels, CPU,
  RAM, and Disk.

Slack example:

```yaml
notifications:
  slack:
    enabled: true
    webhook_url: "${SLACK_WEBHOOK_URL}"
    channel: "#server-alerts"
    username: "xNetVN Monitor"
    test_on_startup: false

Telegram proxy example:

```yaml
notifications:
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_ids: ["-100123456"]
    proxy:
      enabled: true
      uri: "${PROXY_URI}"
```
```
