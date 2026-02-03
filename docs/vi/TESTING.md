---
post_title: "Kiểm thử"
author1: "xNetVN Inc."
post_slug: "docs-vi-testing"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- testing
	- pytest
ai_note: "AI-assisted"
summary: "Hướng dẫn chạy bộ kiểm thử và coverage cho xnetvn_monitord."
post_date: "2026-02-03"
---

## Kiểm thử

## 1. Tổng quan

Dự án sử dụng pytest với các marker unit, integration, security. Bộ test nằm
trong tests/.

## 2. Cài dependency test

```
pip install -r requirements-dev.txt
```

## 3. Chạy toàn bộ test

```
bash scripts/run_tests.sh
```

Script sẽ:

- Cài dependency test.
- Chạy unit, integration, security tests.
- Tạo coverage report (htmlcov/index.html).

## 4. Chạy theo marker

```
pytest -m unit -v
pytest -m integration -v
pytest -m security -v
```

## 5. Ghi chú

- Có thể tắt integration tests bằng SKIP_INTEGRATION=1.
- Khi thêm tính năng mới, cần bổ sung unit test tương ứng.