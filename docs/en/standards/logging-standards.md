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
- Separate log levels: DEBUG, INFO, WARNING, ERROR.

## 2. Storage

- Use size-based log rotation.
- Default log file: `/var/log/xnetvn_monitord/monitor.log`.

## 3. Recommended content

- Timestamp, module, log level, message.
- On errors, set `exc_info=True` to include stack traces.
