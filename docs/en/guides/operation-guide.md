---
post_title: "Operation guide"
author1: "xNetVN Inc."
post_slug: "docs-en-operation-guide"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- operations
	- systemd
ai_note: "AI-assisted"
summary: "Operating xnetvn_monitord on systemd."
post_date: "2026-02-03"
---

## Operation guide

## 1. Start and stop the service

```
sudo systemctl start xnetvn_monitord
sudo systemctl stop xnetvn_monitord
sudo systemctl restart xnetvn_monitord
```

## 2. Follow logs

- `sudo journalctl -u xnetvn_monitord -f`
- Log file: `/var/log/xnetvn_monitord/monitor.log`

## 3. Reload configuration

```
sudo systemctl reload xnetvn_monitord
```

## 4. Check status

```
sudo systemctl status xnetvn_monitord
```
