---
post_title: "Testing"
author1: "xNetVN Inc."
post_slug: "docs-en-testing"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- testing
	- pytest
ai_note: "AI-assisted"
summary: "How to run tests and coverage for xnetvn_monitord."
post_date: "2026-02-03"
---

## Testing

## 1. Overview

The project uses pytest with unit, integration, and security markers. Tests are
located in tests/.

## 2. Install Test Dependencies

```
pip install -r requirements-dev.txt
```

## 3. Run the Full Test Suite

```
bash scripts/run_tests.sh
```

The script will:

- Install test dependencies.
- Run unit, integration, and security tests.
- Generate coverage report (htmlcov/index.html).

## 4. Run by Marker

```
pytest -m unit -v
pytest -m integration -v
pytest -m security -v
```

## 5. Notes

- Integration tests can be skipped with SKIP_INTEGRATION=1.
- Add unit tests for any new feature.
