---
post_title: "Logging standards"
author1: "xNetVN Inc."
post_slug: "docs-en-logging-standards"
microsoft_alias: ""
featured_image: ""
categories:
	- standards
tags:
	- logging
ai_note: "AI-assisted"
summary: "Logging standards for the daemon and operations."
post_date: "2026-02-03"
---

## Logging standards

## 1. Principles

- Logs must include enough context to debug.
- Never log sensitive data (passwords, tokens).
- Separate log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL.

## 1.1 Log level policy

`general.logging.level` is the runtime gate for daemon log verbosity.

| Level | Meaning | Recommended use |
|------|---------|-----------------|
| `DEBUG` | Detailed execution flow and diagnostics | Temporary investigation, development, or targeted incident analysis |
| `INFO` | Normal lifecycle and operational events | Default production setting |
| `WARNING` | Unexpected but recoverable conditions | Low-noise environments with separate health dashboards |
| `ERROR` | Failed checks, failed actions, or operational errors | Short-term focus on active failures |
| `CRITICAL` | Severe failures threatening service continuity | Emergency triage only |

Allowed values are validated during config loading and normalized to uppercase internally.

## 2. Storage

- Use size-based log rotation.
- Default log file: `/var/log/xnetvn_monitord/monitor.log`.

## 3. Recommended content

- Timestamp, module, log level, message.
- On errors, set `exc_info=True` to include stack traces.
