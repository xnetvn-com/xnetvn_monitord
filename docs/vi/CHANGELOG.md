---
post_title: "Changelog"
author1: "xNetVN Inc."
post_slug: "docs-vi-changelog"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- changelog
ai_note: "AI-assisted"
summary: "Lịch sử thay đổi theo Keep a Changelog."
post_date: "2026-02-03"
---

## Changelog

Tất cả các thay đổi quan trọng của dự án sẽ được ghi ở đây.

Định dạng tuân theo Keep a Changelog và phiên bản theo Semantic Versioning.

## [Unreleased]

### Added

- Cập nhật tài liệu tiếng Việt (README, index, kiến trúc, cấu hình, cài đặt).

### Changed

- Chưa có.

### Fixed

- Sua loi nhan dien phien ban trong script update va lam moi updater tai
	/opt/xnetvn_monitord/scripts.

## [1.0.0] - 2026-01-31

### Added

- Daemon giám sát dịch vụ và tài nguyên hệ thống.
- Hành động khôi phục tự động (restart service hoặc recovery command).
- Cảnh báo Email/Telegram/Slack/Discord/Webhook với rate limit và content filter.
- Logging với rotation và PID file.
- Bộ test unit/integration/security.