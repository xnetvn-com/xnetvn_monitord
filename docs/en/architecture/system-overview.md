---
post_title: "System architecture overview"
author1: "xNetVN Inc."
post_slug: "docs-en-architecture-system-overview"
microsoft_alias: ""
featured_image: ""
categories:
	- architecture
tags:
	- architecture
ai_note: "AI-assisted"
summary: "Core components and primary processing flow."
post_date: "2026-02-03"
---

## System architecture overview

## 1. System objectives

Monitor services and system resources on a schedule, recover automatically, and send
timely alerts.

## 2. Core components

- **Daemon runtime:** `MonitorDaemon`.
- **Service monitor:** checks services and restarts on failure.
- **Resource monitor:** CPU/RAM/Disk thresholds and recovery actions.
- **Update checker:** polls GitHub Releases periodically.
- **Notifiers:** Email/Telegram/Slack/Discord/Webhook.
- **Config loader:** YAML with environment expansion.

## 3. Control flow

1. Load config → initialize modules.
2. Loop on `check_interval`.
3. Log and send alerts when needed.

## 4. Integration points

- SMTP server.
- Telegram Bot API.
- Slack/Discord/Webhook endpoints.
- systemd/OpenRC/SysV.
