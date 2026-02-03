---
post_title: "Monitoring guide"
author1: "xNetVN Inc."
post_slug: "docs-en-monitoring-guide"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- monitoring
	- alerts
ai_note: "AI-assisted"
summary: "Monitor daemon health and alerts."
post_date: "2026-02-03"
---

## Monitoring guide

## 1. Monitor daemon health

- Use `systemctl status xnetvn_monitord`.
- Follow logs with `journalctl`.

## 2. Logs and alerts

- Log file: /var/log/xnetvn_monitord/monitor.log.
- Alerts via Email/Telegram/Slack/Discord/Webhook if enabled in configuration.

## 3. Metrics/health endpoints

There is no HTTP API/metrics endpoint in the current codebase.
