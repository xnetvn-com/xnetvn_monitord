---
post_title: "Secure coding guide"
author1: "xNetVN Inc."
post_slug: "docs-en-secure-coding-guide"
microsoft_alias: ""
featured_image: ""
categories:
	- security
tags:
	- secure-coding
ai_note: "AI-assisted"
summary: "Secure coding principles for the project."
post_date: "2026-02-03"
---

## Secure coding guide

## 1. Principles

- Do not hardcode secrets.
- Validate input from configuration.
- Control logging (never leak tokens/passwords).

## 2. System command handling

- Avoid executing arbitrary commands from configuration.
- If necessary, apply allowlists and permission controls.

## 3. Error handling

- Catch exceptions and log clearly.
- Do not leak internal information in outbound notifications.
