---
post_title: "Scaling guide"
author1: "xNetVN Inc."
post_slug: "docs-en-scaling-guide"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- scaling
ai_note: "AI-assisted"
summary: "Recommendations for scaling to multiple servers."
post_date: "2026-02-03"
---

## Scaling guide

## 1. Scaling model

The daemon is deployed in a **one instance per server** model. Scaling primarily
means deploying additional daemons to new servers.

## 2. Scaling considerations

- Sync configuration across servers.
- Standardize logs and alerts to avoid duplication.
- Consider centralized alerting (SIEM/monitoring stack) as the fleet grows.
