---
post_title: "FAQ"
author1: "xNetVN Inc."
post_slug: "docs-vi-faq"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- faq
ai_note: "AI-assisted"
summary: "Câu hỏi thường gặp về xnetvn_monitord."
post_date: "2026-02-03"
---

## Câu hỏi thường gặp

## 1. Dự án này dùng để làm gì?

xnetvn_monitord giám sát dịch vụ và tài nguyên hệ thống, tự động khôi phục và gửi cảnh báo.

## 2. Có hỗ trợ hệ điều hành khác không?

Dự án nhắm đến Linux. Systemd là mặc định; OpenRC và SysV được hỗ trợ thông qua
ServiceManager nếu hệ thống phù hợp.

## 3. Có hỗ trợ Slack không?

Có. Slack, Discord và Webhook đã được triển khai trong mã nguồn.

## 4. Có API/HTTP endpoint không?

Chưa có HTTP API/metrics endpoint trong mã nguồn hiện tại.

## 5. Tôi có thể chạy daemon với user không phải root không?

Có thể, nhưng cần cập nhật unit systemd và quyền truy cập vào các tài nguyên cần giám sát.