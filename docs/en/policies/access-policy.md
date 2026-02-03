---
post_title: "Access control policy"
author1: "xNetVN Inc."
post_slug: "docs-en-access-policy"
microsoft_alias: ""
featured_image: ""
categories:
	- policies
tags:
	- access-control
ai_note: "AI-assisted"
summary: "Access control and permission rules."
post_date: "2026-02-03"
---

## Access control policy

## 1. Principles

- Principle of Least Privilege.
- Role-based access control (RBAC) if an admin system exists.

## 2. File access

- Configuration files containing secrets must use `0600` permissions.
- Logs are readable only by the operations group.

## 3. systemd operations

- Only admin/ops are allowed to `start/stop/restart` the service.
