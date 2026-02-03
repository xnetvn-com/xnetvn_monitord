---
post_title: "Kiến trúc hệ thống"
author1: "xNetVN Inc."
post_slug: "docs-vi-architecture"
microsoft_alias: ""
featured_image: ""
categories:
   - documentation
tags:
   - architecture
   - monitoring
ai_note: "AI-assisted"
summary: "Mô tả kiến trúc, thành phần và luồng dữ liệu của xnetvn_monitord."
post_date: "2026-02-03"
---

## Kiến trúc hệ thống

## Tổng quan

xnetvn_monitord là daemon giám sát chạy nền, định kỳ kiểm tra dịch vụ và tài
nguyên, sau đó thực hiện khôi phục và gửi cảnh báo. Hệ thống tách module rõ
ràng để dễ mở rộng.

## Thành phần chính

### MonitorDaemon

- Nạp cấu hình qua ConfigLoader.
- Nạp biến môi trường từ /opt/xnetvn_monitord/config/.env.
- Thiết lập logging với rotation, tạo PID file.
- Khởi tạo ServiceMonitor, ResourceMonitor, NotificationManager.
- Vòng lặp giám sát theo general.check_interval.
- Xử lý signal SIGTERM, SIGINT, SIGHUP.

### ServiceMonitor

- Kiểm tra trạng thái dịch vụ bằng nhiều phương thức.
- Hỗ trợ action_on_failure: restart hoặc restart_and_notify.
- Hỗ trợ pre_restart_hook và post_restart_hook.
- Trả về kết quả chi tiết để daemon gửi cảnh báo.

### ResourceMonitor

- Kiểm tra CPU load (1/5/15 phút).
- Kiểm tra RAM theo ngưỡng phần trăm hoặc MB.
- Kiểm tra Disk theo từng mount point.
- Thực thi recovery_command hoặc restart dịch vụ theo cooldown.

### NotificationManager

- Quản lý Email, Telegram, Slack, Discord, Webhook.
- Lọc nội dung nhạy cảm theo content_filter.
- Áp dụng min severity và rate limit theo kênh.
- Gửi thông báo theo loại sự kiện (service/resource/action).

### UpdateChecker

- Kiểm tra phiên bản qua GitHub Releases.
- Ghi trạng thái lần kiểm tra vào state_file.
- Tùy chọn gửi thông báo hoặc auto update.

### ConfigLoader và EnvLoader

- Nạp YAML, mở rộng biến môi trường.
- Khi biến môi trường thiếu, giá trị sẽ thành null (YAML None).

### ServiceManager

- Tự động phát hiện systemd/OpenRC/SysV.
- Xây dựng lệnh kiểm tra và restart tương ứng.

## Luồng dữ liệu

1. MonitorDaemon nạp .env và cấu hình YAML.
2. Khởi tạo logging, PID file, monitors, notifiers.
3. Nếu bật update checker, thực hiện kiểm tra phiên bản.
4. Vòng lặp:
    - ServiceMonitor.check_all_services → kết quả → NotificationManager.
    - ResourceMonitor.check_resources → recovery → NotificationManager.
5. SIGHUP → reload config và cập nhật runtime.

## Tích hợp bên ngoài

- Systemd/OpenRC/SysV: quản lý lifecycle và restart dịch vụ.
- SMTP: gửi email cảnh báo.
- Telegram Bot API: gửi cảnh báo qua Telegram.
- Slack/Discord webhook: gửi cảnh báo qua webhook.
- Webhook tùy chỉnh: gửi payload JSON tới các endpoint nội bộ.
- GitHub API: kiểm tra cập nhật phiên bản.

## Lưu ý vận hành

- test_on_startup quyết định có gửi thông báo thử khi khởi động.
- Rate limit và min severity giúp tránh spam cảnh báo.
- Cooldown ngăn lặp lại hành động khôi phục liên tục.

## Mở rộng kiến trúc

- Bổ sung notifier mới bằng cách mở rộng NotificationManager.
- Bổ sung check method mới cho ServiceMonitor theo nhu cầu.