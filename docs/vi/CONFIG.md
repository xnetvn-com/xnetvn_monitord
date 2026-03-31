---
post_title: "Cấu hình"
author1: "xNetVN Inc."
post_slug: "docs-vi-config"
microsoft_alias: ""
featured_image: ""
categories:
  - monitoring
tags:
  - configuration
  - yaml
ai_note: "AI-assisted"
summary: "Hướng dẫn cấu hình xnetvn_monitord dựa trên main.example.yaml."
post_date: "2026-02-03"
---

## Cấu hình

Tài liệu này mô tả các khối cấu hình chính trong config/main.yaml.

## Tổng quan

Các khối chính:

- general: thông tin ứng dụng, logging, PID.
- network: cấu hình mạng outbound.
- update_checker: kiểm tra cập nhật GitHub Releases.
- service_monitor: cấu hình dịch vụ (phương thức check, interval, restart).
- resource_monitor: giám sát CPU/Memory/Disk và recovery.
- notifications: cấu hình Email/Telegram/Slack/Discord/Webhook.

## general

- app_name: thông tin hiển thị.
- Các cấu hình cũ có thể vẫn còn `general.app_version`, nhưng trường này bị bỏ
  qua; quyết định update dùng version thực tế của package đang chạy.
- check_interval: chu kỳ vòng lặp chính (giây).
- logging: level, file, rotation.
- pid_file, work_dir: PID và thư mục runtime.


### general.logging.level

`general.logging.level` điều khiển mức severity tối thiểu được phát ra bởi
root logger của daemon, rotating file handler, và stdout console handler. Trên
thực tế, thiết lập này chi phối gần như toàn bộ log của các module đang dùng
hệ phân cấp logging chuẩn của Python.

- Giá trị mặc định: `INFO`.
- Giá trị hỗ trợ: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
- Không phân biệt hoa thường: `info` và `INFO` được xử lý như nhau.
- Giá trị không hợp lệ sẽ bị từ chối ngay khi nạp cấu hình bằng `ValueError`
  có nhắc trực tiếp tới `general.logging.level`.

Khuyến nghị sử dụng:

| Mức | Dùng khi | Đánh đổi vận hành |
|-----|----------|-------------------|
| `DEBUG` | Điều tra bug, lỗi khởi động, hoặc hành vi monitor bất thường | Lượng log lớn nhất; chỉ nên bật tạm thời |
| `INFO` | Vận hành production hằng ngày | Cân bằng tốt nhất giữa khả năng quan sát và độ ồn |
| `WARNING` | Chỉ muốn thấy các tình huống bất thường nhưng còn phục hồi được | Che bớt log thành công và log vòng đời thường lệ |
| `ERROR` | Muốn tập trung vào check thất bại hoặc recovery thất bại | Có thể bỏ lỡ tín hiệu cảnh báo sớm trước khi sự cố nặng hơn |
| `CRITICAL` | Chỉ muốn log mức khẩn cấp trong lúc xử lý sự cố nghiêm trọng | Quá hẹp cho vận hành bình thường |

- Cùng một mức được áp dụng cho cả `/var/log/xnetvn_monitord/monitor.log` và stdout.

### general.logging.deep_debug và các khóa liên quan

`general.logging.deep_debug` chỉ có hiệu lực khi đồng thời thỏa hai điều kiện:

- `general.logging.enabled: true`
- `general.logging.level: DEBUG`

Hành vi theo từng chế độ:

- `DEBUG` với `deep_debug: false`: daemon phát thêm các sự kiện observability nội bộ vào các log handler thông thường. Nhóm sự kiện này bao gồm decision path, thời gian retry, preview stdout/stderr của lệnh, preview request/response HTTP đã redacted, và các resource snapshot do chính `xnetvn_monitord` trực tiếp thu thập.
- `DEBUG` với `deep_debug: true`: vẫn giữ lớp observability nội bộ ở trên và bổ sung một startup host sweep theo kiểu best-effort, ghi vào file deep debug riêng.

Các khóa hỗ trợ:

- `general.logging.deep_debug`: bật lớp startup host sweep.
- `general.logging.deep_debug_file`: file riêng cho deep debug. Nếu bỏ trống, daemon sẽ suy ra đường dẫn `deep-debug.log` cùng thư mục với `general.logging.file`.
- `general.logging.deep_debug_max_size_mb`: kích thước rotate cho file deep debug.
- `general.logging.deep_debug_backup_count`: số file deep debug đã rotate được giữ lại.
- `general.logging.preview_chars`: giới hạn cắt ngắn cho preview command và HTTP.

Biến môi trường override:

- `XNETVN_MONITORD_DEEP_DEBUG=1`, `true`, `yes`, hoặc `on` sẽ ép bật deep debug.
- `XNETVN_MONITORD_DEEP_DEBUG=0`, `false`, `no`, hoặc `off` sẽ ép tắt deep debug.
- Biến môi trường này ưu tiên hơn YAML, nhưng deep debug vẫn bị tắt nếu mức log chính không phải `DEBUG`.

Các nguồn dữ liệu hiện được quét ở startup khi deep debug bật:

- snapshot telemetry đọc được trong `/proc` như load, memory, PSI, disk và network counters
- các file đọc được dưới `/var/log`, nhưng chỉ lấy preview theo dòng cho các file mang tính log
- metadata snapshot cho `general.work_dir`
- output theo kiểu best-effort từ `journalctl`, `ps aux`, `df -h`, `ss -tunap`, `ip -brief addr`, `ip route`, và `systemctl list-units`

Giới hạn an toàn:

- Giá trị nhạy cảm sẽ được redacted trước khi ghi log.
- Nội dung HTTP và command sẽ bị cắt theo `general.logging.preview_chars`.
- File không mang tính log chỉ được ghi metadata snapshot, không sao chép nội dung vào deep debug log.
- Observability tái sử dụng `notifications.content_filter.redact_patterns` và `redact_replacement` để redaction.

## network

- only_ipv4: khi bật, tất cả kết nối outbound chỉ dùng IPv4.
  Áp dụng cho HTTP checks, webhook notifications và update checks.

Proxy được cấu hình theo từng dịch vụ (update_checker, HTTP checks trong
service_monitor, và từng kênh notification) thay vì cấu hình toàn cục.

## update_checker

```yaml
update_checker:
  enabled: true
  proxy:
    enabled: true
    uri: "${PROXY_URI}"
  interval:
    value: 1
    unit: "weeks"
  notify_on_update: false
  auto_update: false
  github_repo: "xnetvn-com/xnetvn_monitord"
  github_api_base_url: "https://api.github.com"
  state_file: "/opt/xnetvn_monitord/.local/tmp/update_check.json"
  service_name: "xnetvn_monitord"
```

- GITHUB_TOKEN có thể được đặt trong môi trường để tránh rate limit.
- auto_update chạy theo kiểu best-effort, làm mới `scripts/update.sh` và các
  file config ví dụ, rồi restart service sau khi cập nhật.

## service_monitor

Các check_method hỗ trợ:

- systemctl, auto, service, openrc
- process, process_regex
- custom_command
- iptables
- http, https

Các trường quan trọng:

- check_interval: dạng number hoặc {value, unit}.
- action_cooldown, max_restart_attempts, restart_wait_time, restart_cooldown.
- service_name, service_name_pattern (systemd).
- process_name, process_pattern, process_patterns, multi_instance.
- url, http_method, headers, expected_status_codes, max_response_time_ms,
  verify_tls.
- restart_command: chuỗi hoặc danh sách lệnh.
- pre_restart_hook, post_restart_hook.
- check_command/check_timeout có thể dùng với iptables để override lệnh mặc định.

Ví dụ iptables:

```yaml
service_monitor:
  services:
    - name: "iptables"
      enabled: false
      check_method: "iptables"
      check_timeout: 10
      # check_command: "iptables -L -n"
      restart_command:
        - "systemctl restart netfilter-persistent"
        - "systemctl restart iptables"
```

Ví dụ restart_command dạng danh sách:

```yaml
service_monitor:
  services:
    - name: "nginx"
      restart_command:
        - "systemctl restart nginx"
        - "bash /opt/xnetvn_monitord/scripts/custom-restart.sh"

Ví dụ proxy theo từng dịch vụ (chỉ áp dụng HTTP/HTTPS checks):

```yaml
service_monitor:
  services:
    - name: "web_homepage"
      check_method: "https"
      url: "https://example.com/health"
      proxy:
        enabled: true
        uri: "${PROXY_URI}"
```

## resource_monitor

### cpu_load

```yaml
resource_monitor:
  cpu_load:
    enabled: true
    check_1min: true
    threshold_1min: 95.0
    check_5min: true
    threshold_5min: 80.0
    check_15min: false
    threshold_15min: 60.0
    recovery_command: "systemctl restart heavy-worker"
```

- recovery_command được thực thi bằng shell với timeout 60s.

### memory

```yaml
resource_monitor:
  memory:
    enabled: true
    free_percent_threshold: 5.0
    free_mb_threshold: 512
    condition: "or"
```

### disk

```yaml
resource_monitor:
  disk:
    enabled: true
    mount_points:
      - path: "/"
        free_percent_threshold: 10.0
        free_gb_threshold: 5.0
```

- Hỗ trợ paths (chuỗi) và mount_points (dict) để tương thích cấu hình cũ.
- action_on_threshold đã được kích hoạt và hỗ trợ ba giá trị:
  - notify: giữ luồng low-disk recovery hiện có, không dọn dẹp filesystem.
  - cleanup: chỉ chạy cleanup theo cơ chế quarantine.
  - both: chạy cleanup theo cơ chế quarantine trước, sau đó restart low_disk_services.
- disk.cleanup hỗ trợ cleanup theo kiểu quarantine-first với bộ lọc exact/regex/glob,
  điều kiện tuổi/kích thước tối thiểu, danh sách protected paths, kiểm tra cùng
  filesystem cho quarantine, và giới hạn thời gian quét để giảm tải server.
- Các mục bị quarantine được ghi vào JSON manifest trong quarantine directory để
  operator có thể restore theo từng manifest hoặc restore toàn bộ trước khi purge.

## recovery_actions

```yaml
resource_monitor:
  recovery_actions:
    cooldown_period: 1800
    restart_interval: 5
    high_cpu_services:
      - "nginx"
    low_memory_services: []
    low_disk_services: []
```

- cooldown_period áp dụng cho từng action_type.
- ResourceMonitor sẽ restart services theo danh sách này khi vượt ngưỡng.
- low_disk_services sẽ chạy cho cảnh báo disk ở chế độ notify và sẽ chạy sau
  cleanup ở chế độ both.

## notifications

Thông số chung:

- notifications.enabled, min_severity.
- rate_limit: min_interval, max_per_hour.
- content_filter: redact_patterns, redact_replacement.
- Nội dung thông báo luôn hiển thị hostname ở đầu để nhận biết server.

Mỗi kênh (email/telegram/slack/discord/webhook) có:

- enabled, test_on_startup (nếu có).
- min_severity (override).
- rate_limit override (tùy chọn).
- Telegram chat ID hỗ trợ gửi vào topic theo định dạng -100XXXX_YYY,
  trong đó YYY là topic (message_thread_id).
- Khi bật `include_system_stats` cho một kênh, thông báo sự kiện sẽ kèm thêm
  chẩn đoán top 5 tiến trình theo CPU %, CPU core load, RAM MB/RAM %, disk I/O,
  và network Mbps theo kiểu best-effort.
- Phần chẩn đoán chỉ gửi tên executable, user, PID và các chỉ số tài nguyên;
  tuyệt đối không gửi full command line ra ngoài.
- Thống kê network theo tiến trình cần collector tùy chọn như `nethogs` và đủ
  quyền thực thi. Nếu không sẵn sàng, thông báo sẽ ghi rõ metric này không khả
  dụng thay vì suy đoán dữ liệu.
- Telegram, Slack và Discord sẽ ẩn `system_stats.network.interfaces`
  để giữ thông báo gọn hơn, nhưng vẫn giữ các phần còn lại của `System Stats`.
- Khi khởi động, daemon sẽ gửi một startup summary chung tới mọi kênh đang bật
  với hostname, version, thời điểm khởi động, check_interval, các kênh đang
  bật, CPU, RAM và Disk.

Ví dụ Slack:

```yaml
notifications:
  slack:
    enabled: true
    webhook_url: "${SLACK_WEBHOOK_URL}"
    channel: "#server-alerts"
    username: "xNetVN Monitor"
    test_on_startup: false

Ví dụ proxy cho Telegram:

```yaml
notifications:
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_ids: ["-100123456"]
    proxy:
      enabled: true
      uri: "${PROXY_URI}"
```
```
