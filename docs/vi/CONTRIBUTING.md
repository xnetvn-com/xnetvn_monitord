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

## 7. Tùy biến Copilot theo workspace

Repo này có sẵn các file tùy biến Copilot trong `.github/` để hỗ trợ contributor
và AI agent làm việc đúng quy ước của dự án.

### Instructions

- `.github/instructions/xnetvn_monitord-python.instructions.md`
- `.github/instructions/xnetvn_monitord-ops.instructions.md`
- `.github/instructions/xnetvn_monitord-readme.instructions.md`
- `.github/instructions/xnetvn_monitord-docs.instructions.md`
- `.github/instructions/xnetvn_monitord-github-workflows.instructions.md`

### Prompts

- `.github/prompts/sync-monitor-docs.prompt.md` để đồng bộ tài liệu
- `.github/prompts/release-readiness.prompt.md` để rà soát trước phát hành
- `.github/prompts/review-ops-change.prompt.md` để review rủi ro vận hành
- `.github/prompts/prepare-release-notes.prompt.md` để soạn release notes
- `.github/prompts/prepare-release-tag.prompt.md` để chuẩn bị version/tag phát hành
- `.github/prompts/publish-release-via-tag.prompt.md` để phát hành tự động theo tag
- `.github/prompts/sync-installation-docs.prompt.md` để đồng bộ tài liệu cài đặt/nâng cấp

### Agents

- `.github/agents/ops-safety-review.agent.md` để review an toàn vận hành
- `.github/agents/release-readiness-review.agent.md` để review mức sẵn sàng phát hành

## 8. Pull Request checklist

- [ ] Đã chạy test
- [ ] Đã cập nhật tài liệu
- [ ] Không chứa secret
- [ ] Có mô tả rõ ràng về thay đổi