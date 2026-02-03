---
post_title: "Disaster recovery plan"
author1: "xNetVN Inc."
post_slug: "docs-en-disaster-recovery"
microsoft_alias: ""
featured_image: ""
categories:
	- operations
tags:
	- disaster-recovery
ai_note: "AI-assisted"
summary: "Recovery plan for severe failures."
post_date: "2026-02-03"
---

## Disaster recovery plan

## 1. Objective

Recover the daemon and configuration quickly when the server suffers severe failures.

## 2. Scenarios

- Server loss.
- Disk failure.

## 3. Recovery process

1. Reinstall the environment (Ubuntu, Python).
2. Restore source code and configuration from backups.
3. Reinstall the systemd service.
4. Verify runtime and logs.
