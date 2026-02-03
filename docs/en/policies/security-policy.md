---
post_title: "Security policy"
author1: "xNetVN Inc."
post_slug: "docs-en-security-policy"
microsoft_alias: ""
featured_image: ""
categories:
	- policies
tags:
	- security
ai_note: "AI-assisted"
summary: "Security policy for daemon configuration and operations."
post_date: "2026-02-03"
---

## Security policy

## 1. Objective

Ensure the daemon operates safely, avoids sensitive data exposure, and reduces risks
from misconfiguration.

## 2. Principles

- Principle of Least Privilege.
- Do not hardcode secrets.
- Control access to configuration and log files.

## 3. Secret management

- Use environment variables (`EMAIL_PASSWORD`, `TELEGRAM_BOT_TOKEN`).
- Secret files must have `0600` permissions.

## 4. systemd hardening

- Consider running as a non-root user.
- Enable `NoNewPrivileges=true`, `ProtectHome=true` when appropriate.

## 5. Security scanning

- Use `bandit` and `safety` in the CI/CD pipeline.
