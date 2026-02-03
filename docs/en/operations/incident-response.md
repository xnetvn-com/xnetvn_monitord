---
post_title: "Incident response"
author1: "xNetVN Inc."
post_slug: "docs-en-incident-response"
microsoft_alias: ""
featured_image: ""
categories:
	- operations
tags:
	- incident-response
ai_note: "AI-assisted"
summary: "Operational incident response process."
post_date: "2026-02-03"
---

## Incident response

## 1. Detection

- Alerts via Email/Telegram/Slack/Discord/Webhook.
- Error logs in journalctl or monitor.log.

## 2. Classification

- Determine severity per policy `docs/en/policies/incident-policy.md`.

## 3. Mitigation

- Restore the failing service.
- Adjust configuration or thresholds if needed.

## 4. Reporting

- Record timeline, root cause, and mitigation actions.
