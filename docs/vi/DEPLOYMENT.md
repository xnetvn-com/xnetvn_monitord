---
post_title: "Triển khai"
author1: "xNetVN Inc."
post_slug: "docs-vi-deployment"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- deployment
	- systemd
ai_note: "AI-assisted"
summary: "Hướng dẫn triển khai xnetvn_monitord bằng systemd và vận hành an toàn."
post_date: "2026-02-03"
---

## Triển khai

## 1. Triển khai bằng systemd

Triển khai production nên dùng systemd để đảm bảo tự khởi động và restart khi lỗi.

### 1.1. Cài đặt bằng script

```
sudo bash scripts/install.sh
```

Script sẽ:

- Cài service tại /etc/systemd/system/xnetvn_monitord.service.
- Copy cấu hình vào /opt/xnetvn_monitord/config/main.yaml.
- Tạo EnvironmentFile tại /etc/xnetvn_monitord/xnetvn_monitord.env (nếu có).

### 1.2. Vận hành dịch vụ

```
sudo systemctl start xnetvn_monitord
sudo systemctl status xnetvn_monitord
sudo systemctl restart xnetvn_monitord
```

Theo dõi log:

```
sudo journalctl -u xnetvn_monitord -f
```

## 2. Cập nhật cấu hình

1. Chỉnh sửa file cấu hình.
2. Reload hoặc restart service:

```
sudo systemctl reload xnetvn_monitord
```

Lưu ý: ExecReload gửi SIGHUP để daemon reload cấu hình tại runtime.

## 3. Rollback

- Giữ bản sao cấu hình trước khi cập nhật.
- Nếu có lỗi, khôi phục cấu hình và restart service.

## 4. Lưu ý an toàn

- Unit file hiện chạy với User=root. Cần đánh giá lại nếu muốn giảm quyền.
- Các trường security.run_as_user và security.run_as_group trong cấu hình chưa
	được tự động áp dụng vào systemd unit.
- Cân nhắc hardening systemd (NoNewPrivileges, ProtectHome, CapabilityBoundingSet).