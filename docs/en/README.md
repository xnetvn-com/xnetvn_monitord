---
post_title: "xnetvn_monitord"
author1: "xNetVN Inc."
post_slug: "docs-en-readme"
microsoft_alias: ""
featured_image: ""
categories:
    - monitoring
tags:
    - daemon
    - linux
    - monitoring
ai_note: "AI-assisted"
summary: "Overview, key features, and quick start for xnetvn_monitord."
post_date: "2026-02-03"
---

## xnetvn_monitord

**xnetvn_monitord** is a Linux server monitoring daemon that tracks services and
system resources. When it detects failures or threshold breaches, the daemon
automatically performs recovery actions and sends notifications via Email,
Telegram, Slack, Discord, or Webhook.

## Goals

- Continuously monitor critical services and resources.
- Automatically recover to reduce downtime.
- Send timely alerts with rate limiting and sensitive-content filtering.

## Key Features

- Service monitoring via `systemctl`, `service`, `openrc`, process checks, regex,
    custom commands, and HTTP/HTTPS health checks.
- List-based `restart_command` to run multiple commands in order.
- CPU/RAM/Disk threshold monitoring with per-mount support.
- Recovery actions with cooldowns and `pre_restart_hook`/`post_restart_hook`.
- Service check frequency in seconds/minutes/hours.
- Pre/post recovery notifications with min severity and rate limiting.
- Email, Telegram, Slack, Discord, and Webhook notifications.
- Update checker via GitHub Releases with optional auto update.
- Logging with rotation and PID file support.

## Common Services (Ubuntu Web Server & HestiaCP)

The full sample list is provided in `config/main.example.yaml` (disabled by
default), including:

- Web stack: Nginx, Apache2, PHP-FPM, MariaDB/MySQL, PostgreSQL.
- Cache and platform: Redis, Memcached, Docker.
- Security and system: SSH, Cron, Fail2Ban, UFW, iptables.
- HestiaCP stack: Hestia service, Exim/Postfix, Dovecot, Bind9/Named, FTP.
- Anti-malware: ClamAV (daemon/freshclam), SpamAssassin (spamd).
- HTTP/HTTPS health checks (public or localhost), including Roundcube,
    SnappyMail, phpMyAdmin, phpPgAdmin.

## System Requirements

- Linux distributions: Ubuntu/Debian/RHEL/CentOS/Rocky/Alma/Fedora/Arch/
    openSUSE/Alpine.
- Python 3.8+ (3.10+ recommended).
- System privileges for service checks and log writing.

## Service Manager Compatibility

- systemd
- OpenRC
- SysV init (fallback)

Override auto-detection with `XNETVN_SERVICE_MANAGER` (`systemd`, `openrc`, or
`sysv`).

## Quick Installation

- Production install via script (Debian/Ubuntu only, as the script uses apt-get):
    - sudo bash scripts/install.sh
- Dev/test install: see docs/en/INSTALL.md.
- Other distributions: install manually following INSTALL.md.

## Configuration

- Default config file: config/main.yaml (see config/main.example.yaml).
- Environment variable expansion supports $VAR or ${VAR}.

Key sections:

- general: app metadata, logging, PID.
- update_checker: update checks and optional auto update.
- service_monitor: services, intervals, check methods, recovery actions.
- resource_monitor: CPU/RAM/Disk thresholds, recovery commands, restart services.
- notifications: Email/Telegram/Slack/Discord/Webhook, rate limits, content
    filtering, min severity.

Example list-based `restart_command`:

```yaml
service_monitor:
    services:
        - name: "nginx"
            restart_command:
                - "systemctl restart nginx"
                - "bash /opt/xnetvn_monitord/scripts/custom-restart.sh"
```

## Environment Variables (.env + systemd)

The daemon loads a `.env` file from:

```
/opt/xnetvn_monitord/config/.env
```

Use `/opt/xnetvn_monitord/config/.env.example` as a template and copy it to
`.env` (do not commit secrets). The install script and auto update refresh
`main.example.yaml` and `.env.example`, but never overwrite `main.yaml` or `.env`.

Define variables via a systemd EnvironmentFile:

```
/etc/xnetvn_monitord/xnetvn_monitord.env
```

Common variables:

- EMAIL_PASSWORD
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID_1
- SLACK_WEBHOOK_URL
- DISCORD_WEBHOOK_URL
- WEBHOOK_URL_1
- GITHUB_TOKEN
- XNETVN_SERVICE_MANAGER

After updates:

```
sudo systemctl daemon-reload
sudo systemctl restart xnetvn_monitord
```

Operational notes:

- list-based `restart_command` runs sequentially.
- cooldowns and rate limits prevent repeated actions and alert spam.
- per-channel `test_on_startup` validates configuration at startup.

## Quick Operations

- sudo systemctl start xnetvn_monitord
- sudo systemctl status xnetvn_monitord
- sudo journalctl -u xnetvn_monitord -f

## Documentation

- Index: docs/en/index.md.
- Architecture: docs/en/ARCHITECTURE.md.
- Installation: docs/en/INSTALL.md.
- Operations: docs/en/guides/operation-guide.md.

## Contact

- Website: https://xnetvn.com/
- Email: license@xnetvn.net
- Repository: https://github.com/xnetvn-com/xnetvn_monitord