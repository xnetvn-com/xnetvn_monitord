---
post_title: "Hướng dẫn đóng góp"
author1: "xNetVN Inc."
post_slug: "docs-vi-contributing"
microsoft_alias: ""
featured_image: ""
categories:
	- governance
tags:
	- contributing
ai_note: "AI-assisted"
summary: "Quy trình đóng góp và chuẩn chất lượng."
post_date: "2026-02-03"
---

## Hướng dẫn đóng góp

## 1. Nguyên tắc chung

- Đảm bảo mọi thay đổi có mục đích rõ ràng và được kiểm thử.
- Không commit thông tin nhạy cảm.
- Tuân thủ coding standards và quy trình review.

## 2. Quy trình đóng góp

1. Fork repo và tạo nhánh mới.
2. Thực hiện thay đổi và cập nhật tài liệu liên quan.
3. Chạy test trước khi gửi PR.
4. Tạo Pull Request theo template.

## 3. Quy tắc đặt tên nhánh

- feature/<issue-id>-short-description
- bugfix/<issue-id>-short-description
- hotfix/<issue-id>-short-description
- chore/<issue-id>-short-description

## 4. Commit message

Tuân thủ Conventional Commits (tiếng Anh):

- `feat(scope): add ...`
- `fix(scope): resolve ...`
- `chore(scope): update ...`

## 5. Tiêu chuẩn code

- Python: PEP 8.
- Sử dụng formatter/linter (black, flake8, isort, mypy nếu có).

## 6. Kiểm thử

- Chạy bash scripts/run_tests.sh.
- Đảm bảo unit/integration/security tests pass.

## 7. Pull Request checklist

- [ ] Đã chạy test
- [ ] Đã cập nhật tài liệu
- [ ] Không chứa secret
- [ ] Có mô tả rõ ràng về thay đổi