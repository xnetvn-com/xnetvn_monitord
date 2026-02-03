---
post_title: "xnetvn_monitord"
author1: "xNetVN Inc."
post_slug: "docs-vi-readme"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- daemon
	- linux
	- monitoring
ai_note: "AI-assisted"
summary: "Tổng quan, tính năng và hướng dẫn nhanh cho xnetvn_monitord."
post_date: "2026-02-03"
---

## xnetvn_monitord

**xnetvn_monitord** là daemon giám sát máy chủ Linux, theo dõi dịch vụ và tài
nguyên hệ thống. Khi phát hiện sự cố hoặc vượt ngưỡng, daemon tự động thực hiện
hành động khôi phục và gửi thông báo qua Email, Telegram, Slack, Discord hoặc
Webhook.

## Mục tiêu

- Giám sát liên tục dịch vụ và tài nguyên quan trọng.
- Tự động khôi phục để giảm thời gian gián đoạn.
- Cảnh báo kịp thời với kiểm soát tần suất và lọc nội dung nhạy cảm.

## Tính năng chính

- Giám sát dịch vụ qua `systemctl`, `service`, `openrc`, tiến trình, regex,
	lệnh tùy chỉnh, HTTP/HTTPS health check.
- Hỗ trợ `restart_command` dạng danh sách để chạy nhiều lệnh theo thứ tự.
- Giám sát CPU/RAM/Disk theo ngưỡng cấu hình, hỗ trợ mount point riêng lẻ.
- Hành động khôi phục với cooldown, `pre_restart_hook`/`post_restart_hook`.
- Tần suất kiểm tra dịch vụ theo giây/phút/giờ.
- Thông báo trước/sau khi khôi phục, có min severity và rate limit.
- Hỗ trợ Email, Telegram, Slack, Discord, Webhook.
- Update checker qua GitHub Releases, tùy chọn auto update.
- Logging có rotation và PID file.

## Dịch vụ phổ biến (Ubuntu Web Server & HestiaCP)

Danh sách mẫu đầy đủ được cấu hình sẵn trong config/main.example.yaml (tắt mặc
định), bao gồm:

- Web stack: Nginx, Apache2, PHP-FPM, MariaDB/MySQL, PostgreSQL.
- Cache và nền tảng: Redis, Memcached, Docker.
- Bảo mật và hệ thống: SSH, Cron, Fail2Ban, UFW, iptables.
- HestiaCP stack: dịch vụ Hestia, Exim/Postfix, Dovecot, Bind9/Named, FTP.
- Anti-malware: ClamAV (daemon/freshclam), SpamAssassin (spamd).
- HTTP/HTTPS health checks (public hoặc localhost), bao gồm Roundcube,
  SnappyMail, phpMyAdmin, phpPgAdmin.

## Yêu cầu hệ thống

- Linux phổ biến: Ubuntu/Debian/RHEL/CentOS/Rocky/Alma/Fedora/Arch/openSUSE,
	Alpine.
- Python 3.8+ (khuyến nghị 3.10+).
- Quyền hệ thống để kiểm tra dịch vụ và ghi log.

## Tương thích service manager

- systemd
- OpenRC
- SysV init (fallback)

Có thể override cơ chế auto-detect bằng biến môi trường XNETVN_SERVICE_MANAGER
(systemd, openrc, hoặc sysv).

## Cài đặt nhanh

- Cài đặt production bằng script (Debian/Ubuntu do script dùng apt-get):
	- sudo bash scripts/install.sh
- Cài đặt dev/test xem chi tiết tại docs/vi/INSTALL.md.
- Hệ điều hành khác: cài đặt thủ công theo hướng dẫn trong INSTALL.md.

## Cấu hình

- Tệp cấu hình mặc định: config/main.yaml (tham khảo config/main.example.yaml).
- Hỗ trợ biến môi trường dạng $VAR hoặc ${VAR}.

Các khối cấu hình chính:

- general: thông tin ứng dụng, logging, PID.
- update_checker: kiểm tra cập nhật và tùy chọn auto update.
- service_monitor: dịch vụ, tần suất, phương thức kiểm tra, hành động khôi phục.
- resource_monitor: ngưỡng CPU/RAM/Disk, recovery command, restart services.
- notifications: Email/Telegram/Slack/Discord/Webhook, rate limit, content
	filter, min severity.

Ví dụ restart_command dạng danh sách:

```yaml
service_monitor:
	services:
		- name: "nginx"
			restart_command:
				- "systemctl restart nginx"
				- "bash /opt/xnetvn_monitord/scripts/custom-restart.sh"
```

## Biến môi trường (.env + systemd)

Daemon sẽ nạp tệp .env tại:

```
/opt/xnetvn_monitord/config/.env
```

Dùng /opt/xnetvn_monitord/config/.env.example làm mẫu và copy sang .env (không
commit secrets). Script cài đặt và auto update sẽ làm mới main.example.yaml và
.env.example, nhưng không ghi đè main.yaml hoặc .env.

Khai báo biến môi trường qua systemd EnvironmentFile:

```
/etc/xnetvn_monitord/xnetvn_monitord.env
```

Ví dụ biến thường dùng:

- EMAIL_PASSWORD
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID_1
- SLACK_WEBHOOK_URL
- DISCORD_WEBHOOK_URL
- WEBHOOK_URL_1
- GITHUB_TOKEN
- XNETVN_SERVICE_MANAGER

Sau khi cập nhật:

```
sudo systemctl daemon-reload
sudo systemctl restart xnetvn_monitord
```

Lưu ý vận hành:

- restart_command hỗ trợ danh sách lệnh (chạy tuần tự).
- Cooldown và rate limit giúp tránh lặp lại hành động và spam cảnh báo.
- test_on_startup cho từng kênh giúp kiểm tra cấu hình khi daemon khởi động.

## Vận hành nhanh

- sudo systemctl start xnetvn_monitord
- sudo systemctl status xnetvn_monitord
- sudo journalctl -u xnetvn_monitord -f

## Tài liệu

- Mục lục: docs/vi/index.md.
- Kiến trúc: docs/vi/ARCHITECTURE.md.
- Cài đặt: docs/vi/INSTALL.md.
- Vận hành: docs/vi/guides/operation-guide.md.

## Liên hệ

- Website: https://xnetvn.com/
- Email: license@xnetvn.net
- Repository: https://github.com/xnetvn-com/xnetvn_monitord