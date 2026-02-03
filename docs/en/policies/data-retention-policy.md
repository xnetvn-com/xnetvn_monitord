---
post_title: "Data retention policy"
author1: "xNetVN Inc."
post_slug: "docs-en-data-retention-policy"
microsoft_alias: ""
featured_image: ""
categories:
	- policies
tags:
	- data-retention
ai_note: "AI-assisted"
summary: "Retention rules for logs and operational data."
post_date: "2026-02-03"
---

## Data retention policy

## 1. Data scope

- Operational logs.
- Audit logs (if enabled in configuration).

## 2. Retention period

- Application logs: follow `backup_count` and `max_size_mb` configuration.
- Audit logs: per internal policy.

## 3. Deletion and cleanup

- Automatic log rotation with `RotatingFileHandler`.
- Periodically review log storage usage.
