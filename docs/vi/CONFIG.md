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
- update_checker: kiểm tra cập nhật GitHub Releases.
- service_monitor: cấu hình dịch vụ (phương thức check, interval, restart).
- resource_monitor: giám sát CPU/Memory/Disk và recovery.
- notifications: cấu hình Email/Telegram/Slack/Discord/Webhook.

## general

- app_name, app_version: thông tin hiển thị.
- check_interval: chu kỳ vòng lặp chính (giây).
- logging: level, file, rotation.
- pid_file, work_dir: PID và thư mục runtime.

## update_checker

```yaml
update_checker:
  enabled: true
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
- auto_update chỉ chạy best-effort và sẽ restart service sau khi cập nhật.

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
- action_on_threshold xuất hiện trong main.example.yaml nhưng chưa được sử dụng
  trong mã nguồn hiện tại.

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

## notifications

Thông số chung:

- notifications.enabled, min_severity.
- rate_limit: min_interval, max_per_hour.
- content_filter: redact_patterns, redact_replacement.

Mỗi kênh (email/telegram/slack/discord/webhook) có:

- enabled, test_on_startup (nếu có).
- min_severity (override).
- rate_limit override (tùy chọn).

Ví dụ Slack:

```yaml
notifications:
  slack:
    enabled: true
    webhook_url: "${SLACK_WEBHOOK_URL}"
    channel: "#server-alerts"
    username: "xNetVN Monitor"
    test_on_startup: false
```
