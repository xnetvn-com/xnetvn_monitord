---
post_title: "Threat modeling"
author1: "xNetVN Inc."
post_slug: "docs-en-threat-modeling"
microsoft_alias: ""
featured_image: ""
categories:
	- security
tags:
	- threat-modeling
ai_note: "AI-assisted"
summary: "Threat model for the daemon."
post_date: "2026-02-03"
---

## Threat modeling

## 1. Assets to protect

- Configuration files containing secrets.
- systemd permissions and restart capability.
- System logs.

## 2. Primary threats

- Unauthorized configuration changes.
- Abuse of `recovery_command` to execute arbitrary commands.
- Token/email password leakage via logs or configuration.

## 3. Mitigations

- Restrict access to configuration files.
- Do not run the daemon as root unless required.
- Filter sensitive content in notifications.
