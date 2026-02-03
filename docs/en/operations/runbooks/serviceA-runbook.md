---
post_title: "Runbook: xnetvn_monitord"
author1: "xNetVN Inc."
post_slug: "docs-en-runbook-xnetvn-monitord"
microsoft_alias: ""
featured_image: ""
categories:
	- operations
tags:
	- runbook
ai_note: "AI-assisted"
summary: "Operations runbook for xnetvn_monitord."
post_date: "2026-02-03"
---

## Runbook: xnetvn_monitord

## 1. Objective

Operational runbook for the xnetvn_monitord daemon.

## 2. Quick checks

- `systemctl status xnetvn_monitord`
- `journalctl -u xnetvn_monitord -f`

## 3. Start/Stop

- Start: `systemctl start xnetvn_monitord`
- Stop: `systemctl stop xnetvn_monitord`
- Restart: `systemctl restart xnetvn_monitord`

## 4. Common troubleshooting

- Check configuration and log file permissions.
- Verify environment variables for notifiers.
- Inspect the systemd unit file.
