---
post_title: "Xử lý sự cố"
author1: "xNetVN Inc."
post_slug: "docs-vi-troubleshooting"
microsoft_alias: ""
featured_image: ""
categories:
  - monitoring
tags:
  - troubleshooting
ai_note: "AI-assisted"
summary: "Các tình huống lỗi thường gặp và cách xử lý."
post_date: "2026-02-03"
---

## Xử lý sự cố

## 1. Service không khởi động

### Triệu chứng

- `systemctl status xnetvn_monitord` báo lỗi.

### Kiểm tra

- Xem log:
  - `journalctl -u xnetvn_monitord -f`
- Kiểm tra cấu hình:
  - `/opt/xnetvn_monitord/config/main.yaml`

## 2. Không gửi được email/telegram

### Kiểm tra

- Xác nhận `notifications.email.enabled` hoặc `notifications.telegram.enabled`.
- Kiểm tra biến môi trường `EMAIL_PASSWORD`, `TELEGRAM_BOT_TOKEN`.
- Xem log lỗi trong `monitor.log`.

## 3. Không restart service khi lỗi

### Kiểm tra

- Xác nhận service_monitor.action_on_failure.
- Kiểm tra danh sách service trong cấu hình.
- Đảm bảo daemon có quyền thực thi `systemctl`.

## 4. Không ghi log

### Kiểm tra

- general.logging.enabled.
- Quyền ghi vào `/var/log/xnetvn_monitord/`.

## 5. Cảnh báo gửi quá nhiều

### Giải pháp

- Điều chỉnh `notifications.rate_limit`.
- Kiểm tra các ngưỡng trong `resource_monitor`.

## 6. ResourceMonitor — Hành động khôi phục (recovery)

### Triệu chứng

- Cảnh báo tài nguyên (CPU/memory/disk) được gửi nhưng thao tác khôi phục không thực hiện hoặc không hiệu quả.

### Kiểm tra & Giải pháp

- **recovery_command**:
  - Lệnh cấu hình trong `resource_monitor` sẽ được thực thi trong shell (sh), với timeout mặc định **60s**.
  - Kiểm tra `monitor.log` để xem `stdout`/`stderr` và trạng thái thực thi (thời gian chờ, lỗi). Theo dõi trường `action_results` trong log (nếu có) để biết chi tiết.
  - Nếu lệnh cần môi trường (PATH, biến môi trường), hãy khai báo đầy đủ đường dẫn hoặc wrapper script để đảm bảo môi trường thực thi giống như khi chạy thủ công.

- **restart services qua recovery_actions**:
  - Daemon sẽ restart các dịch vụ trong recovery_actions.high_cpu_services,
    low_memory_services, low_disk_services theo thứ tự cấu hình.
  - **Hành vi tuần tự**: dịch vụ được xử lý lần lượt; nếu muốn song song, cần
    wrapper script riêng.
  - Kiểm tra quyền cho daemon để gọi systemctl (cần sudo hoặc quyền phù hợp).

- **Cooldown và restart_interval**:
  - ResourceMonitor áp dụng cooldown mặc định 1800s cho mỗi action_type.
  - restart_interval điều khiển khoảng thời gian giữa các lần restart dịch vụ.

- **Debug**:
  - Bật logging ở mức DEBUG trong cấu hình để thu thêm ngữ cảnh.
  - Chạy recovery_command thủ công dưới cùng user với cùng biến môi trường.
  - Kiểm tra /var/log/xnetvn_monitord/monitor.log để xem action_results.

## 7. Notifier — Kiểm tra và test_on_startup

### Triệu chứng

- Không nhận được thông báo khi khởi động hoặc khi test notifier chạy.

### Kiểm tra & Giải pháp

- **test_on_startup**:
  - Khi bật, notifiers sẽ cố gắng gửi một thông báo thử khi daemon khởi động. Kiểm tra cấu hình `notifications.<provider>.test_on_startup`.
  - Nếu `test_on_startup` = false, daemon sẽ *không* gửi thông báo thử; bật tạm thời để xác minh kết nối.

- **Hành vi giới hạn tốc độ (rate_limit)**:
  - Nếu gửi quá nhiều thông báo trong thời gian ngắn, hệ thống có thể chặn theo cấu hình `notifications.rate_limit` hoặc do hạn chế bên thứ ba (Slack API, Telegram). Điều chỉnh `rate_limit` nếu cần.

- **Kiểm tra chi tiết**:
  - Xác thực các biến môi trường (SLACK_WEBHOOK_URL, TELEGRAM_BOT_TOKEN,
    EMAIL_PASSWORD).
  - Sử dụng curl để kiểm thử webhook bên ngoài.
  - Xem log monitor.log để biết lỗi trả về từ provider (HTTP status, body).