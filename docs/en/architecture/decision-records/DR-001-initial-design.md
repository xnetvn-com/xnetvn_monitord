---
post_title: "DR-001: Initial design for the monitoring daemon"
author1: "xNetVN Inc."
post_slug: "docs-en-dr-001"
microsoft_alias: ""
featured_image: ""
categories:
	- architecture
tags:
	- adr
ai_note: "AI-assisted"
summary: "Initial architecture decision."
post_date: "2026-02-03"
---

## DR-001: Initial design for the monitoring daemon

## Status

Approved

## Context

A daemon is needed to monitor services and resources on Ubuntu 22 LTS, with automatic
recovery and alerting.

## Decision

- Use Python for development speed and system libraries (`psutil`, `PyYAML`).
- Use systemd to manage the daemon lifecycle.
- Separate modules by monitor/notifier for extensibility.

## Consequences

- Easier to extend with new notifiers and monitors.
- Must control daemon permissions because it performs service restarts.
