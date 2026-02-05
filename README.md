# xnetvn_monitord

**Automated Server Monitoring and Service Recovery for Linux**

[Vietnamese Documentation](docs/vi/README.md) | [English Documentation](docs/en/README.md)

---

## 🎯 Overview

**xnetvn_monitord** is an enterprise-grade monitoring solution designed to automatically track critical services and system resources on modern Linux servers. When a service fails or resources exceed thresholds, the daemon performs recovery actions and sends notifications via email, Telegram, Slack, Discord, or Webhook.

### Key Features

- ⚡ **Automatic Recovery**: Auto-restart services when failures detected
- 🔧 **Sequential Restart Commands**: Support list-based restart commands and scripts
- 📊 **Comprehensive Monitoring**: CPU, RAM, disk space, and critical services
- 🌐 **HTTP/HTTPS Health Checks**: Detect connection errors, 4xx/5xx, timeouts, slow responses
- 📧 **Multi-channel Notifications**: Email, Telegram, Slack, Discord, Webhook
- 🧭 **Hostname in Alerts**: Prefix notifications with the server hostname
- 🌐 **IPv4-only Option**: Force outbound HTTP checks and notifications to IPv4
- 🧵 **Telegram Topics**: Send to topics using chat IDs like `-100XXXX_YYY`
- ⬆️ **Manual Update Script**: `scripts/update.sh` with backups and confirmation
- 🔒 **Security First**: Sensitive data filtering, rate limiting, audit logging
- 🔄 **Flexible Configuration**: Easy YAML config with environment variables support
- 🛡️ **Production Ready**: Cooldown mechanisms, retry logic, graceful shutdown
- ⬆️ **Update Checker**: GitHub Releases checks with optional auto update

---

## 📋 Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/xnetvn-com/xnetvn_monitord.git
cd xnetvn_monitord

# Run installation script
sudo bash scripts/install.sh

# Note (Ubuntu 24 LTS / PEP 668): the installer uses
# /opt/xnetvn_monitord/.venv for Python packages.

# Edit configuration
sudo vi /opt/xnetvn_monitord/config/main.yaml

# Start service
sudo systemctl start xnetvn_monitord

# Check status
sudo systemctl status xnetvn_monitord
```

### Manual Update

```bash
sudo bash scripts/update.sh
```

---

## 🎨 What It Monitors

### Services
- Nginx, Apache2, PHP-FPM (all versions), MariaDB/MySQL, PostgreSQL
- Redis, Memcached, Docker, SSH, Cron, Fail2Ban, UFW
- HestiaCP stack: Hestia service, Exim/Postfix, Dovecot, Bind9/Named, FTP
- ClamAV, SpamAssassin (spamd), custom services via regex
- IPtables firewall checks
- HTTP/HTTPS web endpoints (local or public), including Roundcube/SnappyMail,
  phpMyAdmin, and phpPgAdmin health checks

### Resources
- **CPU Load**: 1/5/15-minute averages
- **Memory**: Free RAM by percentage and MB
- **Disk Space**: Multiple mount points monitoring

---

## 📖 Documentation

- **Vietnamese**: [docs/vi/README.md](docs/vi/README.md)
- **English**: [docs/en/README.md](docs/en/README.md)

---

## 🔐 Environment Variables (.env + systemd)

The daemon loads an optional `.env` file from:

```
/opt/xnetvn_monitord/config/.env
```

Use `/opt/xnetvn_monitord/config/.env.example` as a template and copy it to
`.env` without committing secrets.

The installer and auto-updater refresh `/opt/xnetvn_monitord/config/main.example.yaml`
and `/opt/xnetvn_monitord/config/.env.example` on each install/upgrade, without
overwriting `/opt/xnetvn_monitord/config/main.yaml` or `/opt/xnetvn_monitord/config/.env`.
On first install, the script also creates `/opt/xnetvn_monitord/config/.env`
with permissions set to 0600 if it does not exist.

You can also use systemd `EnvironmentFile` entries when running via systemd:

When using `${VAR}` in `config/main.yaml`, define environment variables via a
systemd EnvironmentFile:

```
/etc/xnetvn_monitord/xnetvn_monitord.env
```

Common entries:

```
EMAIL_PASSWORD=your_smtp_password
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
SLACK_WEBHOOK_URL=your_slack_webhook_url
DISCORD_WEBHOOK_URL=your_discord_webhook_url
WEBHOOK_URL_1=your_webhook_url
GITHUB_TOKEN=your_github_token
```

After updating the file:

```
sudo systemctl daemon-reload
sudo systemctl restart xnetvn_monitord
```

---

## 🔧 Configuration Example

```yaml
general:
  check_interval: 60

update_checker:
  enabled: true
  auto_update: false

service_monitor:
  enabled: true
  action_on_failure: "restart_and_notify"
  services:
    - name: "nginx"
      restart_command:
        - "systemctl restart nginx"
        - "bash /opt/xnetvn_monitord/scripts/custom-restart.sh"

resource_monitor:
  enabled: true
  cpu_load:
    threshold_1min: 99.0
  memory:
    free_percent_threshold: 5.0
    free_mb_threshold: 512

notifications:
  email:
    enabled: true
  telegram:
    enabled: true
  slack:
    enabled: false
  discord:
    enabled: false
  webhook:
    enabled: false
```

---

## 🚀 Usage

```bash
# Start
sudo systemctl start xnetvn_monitord

# Status
sudo systemctl status xnetvn_monitord

# Logs
sudo journalctl -u xnetvn_monitord -f

# Stop
sudo systemctl stop xnetvn_monitord

# Reload config
sudo systemctl reload xnetvn_monitord
```

---

## 📊 System Requirements

- Linux distributions: Ubuntu LTS, Debian, CentOS, RHEL, Rocky/Alma, Fedora, Arch,
  openSUSE/SLES, Alpine
- Python 3.8+ (3.10+ recommended)
- System privileges to manage services and write logs
- Network access for notifications

## 🧩 Service Manager Compatibility

- systemd (Ubuntu/Debian/RHEL/CentOS/Rocky/Alma/Fedora/Arch/openSUSE/SLES)
- OpenRC (Alpine)
- SysV init (fallback)

You can override auto-detection with the `XNETVN_SERVICE_MANAGER` environment variable
(`systemd`, `openrc`, or `sysv`).

---

## 📄 License

Copyright © 2026 xNetVN Inc.

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) file.

---

## 📞 Contact

- **Website**: https://xnetvn.com
- **Email**: license@xnetvn.net
- **Repository**: https://github.com/xnetvn-com/xnetvn_monitord

---

**Made with ❤️ by xNetVN Inc.**
