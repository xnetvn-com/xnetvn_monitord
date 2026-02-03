---
post_title: "Coding standards"
author1: "xNetVN Inc."
post_slug: "docs-en-coding-standards"
microsoft_alias: ""
featured_image: ""
categories:
	- standards
tags:
	- coding
ai_note: "AI-assisted"
summary: "Coding standards for the project codebase."
post_date: "2026-02-03"
---

## Coding standards

## 1. Language and conventions

- Python follows PEP 8.
- Variable/function/class names are in English and descriptive.
- Docstrings are required for public functions and critical logic.

## 2. Quality tools

- Formatter: `black`.
- Lint: `flake8`, `pylint`.
- Type check: `mypy`.
- Import sorting: `isort`.

## 3. General rules

- Do not hardcode secrets.
- Prefer defensive programming.
- Keep functions concise and readable.
