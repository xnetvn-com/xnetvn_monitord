---
post_title: "FAQ"
author1: "xNetVN Inc."
post_slug: "docs-en-faq"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- faq
ai_note: "AI-assisted"
summary: "Frequently asked questions about xnetvn_monitord."
post_date: "2026-02-03"
---

## Frequently asked questions

## 1. What is this project for?

xnetvn_monitord monitors services and system resources, automatically recovers, and
sends alerts.

## 2. Does it support other operating systems?

The project targets Linux. systemd is the default; OpenRC and SysV are supported via
ServiceManager when the system is compatible.

## 3. Does it support Slack?

Yes. Slack, Discord, and Webhook are implemented in the codebase.

## 4. Is there an API/HTTP endpoint?

There is no HTTP API/metrics endpoint in the current codebase.

## 5. Can I run the daemon as a non-root user?

Yes, but you must update the systemd unit and grant access to required monitoring
resources.
