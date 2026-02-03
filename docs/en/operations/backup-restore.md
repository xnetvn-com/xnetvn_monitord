---
post_title: "Backup & restore"
author1: "xNetVN Inc."
post_slug: "docs-en-backup-restore"
microsoft_alias: ""
featured_image: ""
categories:
	- operations
tags:
	- backup
	- restore
ai_note: "AI-assisted"
summary: "Backup and restore workflow for configuration."
post_date: "2026-02-03"
---

## Backup & restore

## 1. Backup scope

- Configuration file: `/opt/xnetvn_monitord/config/main.yaml`.
- Critical logs if audit is required.

## 2. Backup

```
sudo cp /opt/xnetvn_monitord/config/main.yaml /opt/xnetvn_monitord/config/main.yaml.bak
```

## 3. Restore

```
sudo cp /opt/xnetvn_monitord/config/main.yaml.bak /opt/xnetvn_monitord/config/main.yaml
sudo systemctl restart xnetvn_monitord
```
