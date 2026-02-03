---
post_title: "Cấu hình môi trường"
author1: "xNetVN Inc."
post_slug: "docs-vi-environment"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- environment
	- secrets
ai_note: "AI-assisted"
summary: "Hướng dẫn sử dụng biến môi trường cho xnetvn_monitord."
post_date: "2026-02-03"
---

## Cấu hình môi trường

## 1. Tổng quan

Daemon sử dụng config/main.yaml và hỗ trợ biến môi trường theo dạng $VAR hoặc
${VAR}. Khi biến môi trường không tồn tại, giá trị sẽ được thay bằng null.

Tệp mẫu /opt/xnetvn_monitord/config/.env.example được làm mới mỗi lần cài đặt
hoặc nâng cấp để tham khảo các biến môi trường mới nhất.

## 2. Biến môi trường bắt buộc/khuyến nghị

| Biến | Mục đích | Bắt buộc | Ghi chú |
|---|---|---|---|
| EMAIL_PASSWORD | Mật khẩu SMTP | Tùy cấu hình | Khi bật email notification |
| TELEGRAM_BOT_TOKEN | Token bot Telegram | Tùy cấu hình | Khi bật Telegram notification |
| SLACK_WEBHOOK_URL | Webhook Slack | Tùy cấu hình | Khi bật Slack notification |
| DISCORD_WEBHOOK_URL | Webhook Discord | Tùy cấu hình | Khi bật Discord notification |
| WEBHOOK_URL | Webhook chung | Tùy cấu hình | Khi bật Webhook notification |
| GITHUB_TOKEN | GitHub API token | Tùy cấu hình | Dùng cho update_checker |
| XNETVN_SERVICE_MANAGER | Override service manager | Không | systemd, openrc, sysv |

## 3. Cách thiết lập biến môi trường

### 3.1. Thiết lập tạm thời trong shell

```
export EMAIL_PASSWORD="<your_password>"
export TELEGRAM_BOT_TOKEN="<your_token>"
```

### 3.2. Thiết lập qua systemd (khuyến nghị)

- Khai báo trong EnvironmentFile hoặc Environment của unit systemd.
- File chứa secret cần quyền truy cập tối thiểu (0600).

#### Ví dụ triển khai thực tế (EnvironmentFile)

1) Tạo file môi trường:

```
sudo mkdir -p /etc/xnetvn_monitord
sudo tee /etc/xnetvn_monitord/xnetvn_monitord.env > /dev/null <<'EOF'
EMAIL_PASSWORD=your_smtp_password
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
SLACK_WEBHOOK_URL=your_slack_webhook_url
DISCORD_WEBHOOK_URL=your_discord_webhook_url
WEBHOOK_URL=your_webhook_url
GITHUB_TOKEN=your_github_token
EOF
sudo chmod 600 /etc/xnetvn_monitord/xnetvn_monitord.env
```

2) Đảm bảo unit systemd có dòng:

```
EnvironmentFile=-/etc/xnetvn_monitord/xnetvn_monitord.env
```

3) Reload và khởi động lại dịch vụ:

```
sudo systemctl daemon-reload
sudo systemctl restart xnetvn_monitord
sudo systemctl status xnetvn_monitord
```

## 4. Lưu ý bảo mật

- Không commit secret vào repo.
- Ưu tiên quản lý secret qua biến môi trường hoặc secret manager.
- Kiểm tra log để tránh lộ thông tin nhạy cảm.