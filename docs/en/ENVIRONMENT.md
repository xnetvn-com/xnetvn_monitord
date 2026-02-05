---
post_title: "Environment Configuration"
author1: "xNetVN Inc."
post_slug: "docs-en-environment"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- environment
	- secrets
ai_note: "AI-assisted"
summary: "How to use environment variables for xnetvn_monitord."
post_date: "2026-02-03"
---

## Environment Configuration

## 1. Overview

The daemon uses config/main.yaml and supports environment variables as $VAR or
${VAR}. If a variable is missing, the value becomes null.

The template /opt/xnetvn_monitord/config/.env.example is refreshed on each
install or upgrade to reflect the latest variables.

On first install, the installer creates /opt/xnetvn_monitord/config/.env from
the example file if it does not exist and sets permissions to 0600.

## 2. Required/Recommended Environment Variables

| Variable | Purpose | Required | Notes |
|---|---|---|---|
| EMAIL_PASSWORD | SMTP password | Optional | When email notifications are enabled |
| TELEGRAM_BOT_TOKEN | Telegram bot token | Optional | When Telegram notifications are enabled |
| SLACK_WEBHOOK_URL | Slack webhook | Optional | When Slack notifications are enabled |
| DISCORD_WEBHOOK_URL | Discord webhook | Optional | When Discord notifications are enabled |
| WEBHOOK_URL | Generic webhook | Optional | When Webhook notifications are enabled |
| GITHUB_TOKEN | GitHub API token | Optional | Used by update_checker |
| XNETVN_SERVICE_MANAGER | Service manager override | No | systemd, openrc, sysv |

## 3. How to Set Environment Variables

### 3.1. Temporary Shell Export

```
export EMAIL_PASSWORD="<your_password>"
export TELEGRAM_BOT_TOKEN="<your_token>"
```

### 3.2. Using systemd (Recommended)

- Define EnvironmentFile or Environment in the systemd unit.
- The secret file should have minimal permissions (0600).

#### Practical Example (EnvironmentFile)

1) Create the environment file:

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

2) Ensure the systemd unit contains:

```
EnvironmentFile=-/etc/xnetvn_monitord/xnetvn_monitord.env
```

3) Reload and restart the service:

```
sudo systemctl daemon-reload
sudo systemctl restart xnetvn_monitord
sudo systemctl status xnetvn_monitord
```

## 4. Security Notes

- Never commit secrets to the repository.
- Prefer environment variables or a secrets manager.
- Review logs to avoid leaking sensitive data.
