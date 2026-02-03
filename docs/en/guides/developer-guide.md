---
post_title: "Developer guide"
author1: "xNetVN Inc."
post_slug: "docs-en-developer-guide"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- developer
ai_note: "AI-assisted"
summary: "Environment setup and development workflow."
post_date: "2026-02-03"
---

## Developer guide

## 1. Environment preparation

- Python 3.8+.
- Create a virtualenv and install dependencies.

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

## 2. Run the daemon in dev mode

```
python3 -m xnetvn_monitord.daemon config/main.yaml
```

## 3. Testing

```
bash scripts/run_tests.sh
```

## 4. Contribution rules

- Follow docs/en/CONTRIBUTING.md.
