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

## [1.7.0] - 2026-04-06

### Changed

- Tích hợp systemd: bổ sung watchdog, ưu tiên tài nguyên runtime, và cập nhật unit service cho bản phát hành.
- Phát hành: nâng gói lên v1.7.0 và làm mới metadata phát hành cho quy trình tag-driven publication.

## [1.6.0] - 2026-03-31

### Changed

- Phát hành: nâng gói lên v1.6.0 và làm mới metadata phát hành cho quy trình tag-driven publication.

## [1.5.0] - 2026-03-26

### Changed

- Phát hành: nâng gói lên v1.5.0 và làm mới metadata phát hành cho quy trình tag-driven publication.

## [1.4.0] - 2026-03-25

### Changed

- Báo cáo notification giờ kèm chẩn đoán an toàn top 5 tiến trình cho CPU %, CPU core load, RAM, disk I/O và network theo tiến trình ở chế độ best-effort khi kênh bật `include_system_stats`.

### Fixed

- Chẩn đoán tiến trình chỉ gửi executable name, user và PID, đồng thời ghi rõ khi metric network theo tiến trình không khả dụng do thiếu collector tùy chọn, thiếu quyền hoặc output không hợp lệ.

## [1.0.0] - 2026-01-31

### Added

- Daemon giám sát dịch vụ và tài nguyên hệ thống.
- Hành động khôi phục tự động (restart service hoặc recovery command).
- Cảnh báo Email/Telegram/Slack/Discord/Webhook với rate limit và content filter.
- Logging với rotation và PID file.
- Bộ test unit/integration/security.