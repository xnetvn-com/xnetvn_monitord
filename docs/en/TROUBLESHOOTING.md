---
post_title: "Troubleshooting"
author1: "xNetVN Inc."
post_slug: "docs-en-troubleshooting"
microsoft_alias: ""
featured_image: ""
categories:
  - monitoring
tags:
  - troubleshooting
ai_note: "AI-assisted"
summary: "Common issues and how to resolve them."
post_date: "2026-02-03"
---

## Troubleshooting

## 1. Service does not start

### Symptoms

- `systemctl status xnetvn_monitord` reports an error.

### Checks

- View logs:
  - `journalctl -u xnetvn_monitord -f`
- Verify configuration:
  - `/opt/xnetvn_monitord/config/main.yaml`

## 1.1 Installation fails with python3-venv or missing pip

### Symptoms

- `python3 -m venv` fails with `ensurepip is not available`.
- The installer reports `/opt/xnetvn_monitord/.venv/bin/python: No module named pip`.

### Fix

- Install the venv package and re-run the installer:
  - `sudo apt-get update && sudo apt-get install -y python3-venv`
  - `sudo bash scripts/install.sh`
- If the virtual environment already exists, remove it and reinstall:
  - `sudo rm -rf /opt/xnetvn_monitord/.venv`
  - `sudo bash scripts/install.sh`

## 2. Email/Telegram notifications are not sent

### Checks

- Confirm `notifications.email.enabled` or `notifications.telegram.enabled`.
- Verify environment variables `EMAIL_PASSWORD`, `TELEGRAM_BOT_TOKEN`.
- Inspect error logs in `monitor.log`.

## 3. Service is not restarted on failure

### Checks

- Verify service_monitor.action_on_failure.
- Check service list in configuration.
- Ensure the daemon has permission to execute `systemctl`.

## 4. No logs are written

### Checks

- general.logging.enabled.
- Write permissions for `/var/log/xnetvn_monitord/`.

## 5. Too many alerts

### Resolution

- Adjust `notifications.rate_limit`.
- Review thresholds in `resource_monitor`.

## 6. ResourceMonitor — Recovery Actions

### Symptoms

- Resource alerts (CPU/memory/disk) are sent but recovery actions do not run or are ineffective.

### Checks & Fixes

- **recovery_command**:
  - The command configured in `resource_monitor` is executed by the shell (sh) with a default **60s** timeout.
  - Check `monitor.log` for stdout/stderr and execution status (timeouts, errors). Review `action_results` in logs (if present) for details.
  - If the command needs a specific environment (PATH, env vars), provide full paths or a wrapper script to match manual execution.

- **Restart services via recovery_actions**:
  - The daemon restarts services listed in recovery_actions.high_cpu_services,
    low_memory_services, low_disk_services in the configured order.
  - **Sequential behavior**: services are handled one by one; use a custom wrapper if you need parallel execution.
  - Verify the daemon has permission to call systemctl (sudo or equivalent permissions).

- **Cooldown and restart_interval**:
  - ResourceMonitor applies a default 1800s cooldown per action_type.
  - restart_interval controls the delay between service restarts.

- **Debug**:
  - Enable DEBUG logging for more context.
  - Run recovery_command manually under the same user and environment.
  - Inspect /var/log/xnetvn_monitord/monitor.log for action_results.

## 7. Notifier — test_on_startup and validation

### Symptoms

- No notification at startup or when the notifier test runs.

### Checks & Fixes

- **test_on_startup**:
  - When enabled, notifiers attempt to send a test message on daemon startup. Check `notifications.<provider>.test_on_startup`.
  - If `test_on_startup` is false, the daemon will *not* send a test message; enable temporarily to validate connectivity.

- **Rate limiting behavior (rate_limit)**:
  - Sending too many alerts in a short window may be blocked by `notifications.rate_limit` or third-party limits (Slack API, Telegram). Adjust rate limits if needed.

- **Detailed checks**:
  - Validate environment variables (SLACK_WEBHOOK_URL, TELEGRAM_BOT_TOKEN,
    EMAIL_PASSWORD).
  - Use curl to test external webhooks.
  - Check monitor.log for provider errors (HTTP status, body).
