# xnetvn_monitord

**Automated Server Monitoring and Service Recovery for Linux**

[Vietnamese Documentation](docs/vi/README.md) | [English Documentation](docs/en/README.md)

---

## 🎯 Overview

**xnetvn_monitord** is an enterprise-grade monitoring solution designed to automatically track critical services and system resources on modern Linux servers. When a service fails or resources exceed thresholds, the daemon automatically performs recovery actions and sends notifications via email/Telegram.

### Key Features

- ⚡ **Automatic Recovery**: Auto-restart services when failures detected
- 📊 **Comprehensive Monitoring**: CPU, RAM, disk space, and critical services
- 🌐 **HTTP/HTTPS Health Checks**: Detect connection errors, 4xx/5xx, timeouts, slow responses
- 📧 **Multi-channel Notifications**: Email, Telegram, Slack, Discord, Webhook
- 🔒 **Security First**: Sensitive data filtering, rate limiting, audit logging
- 🔄 **Flexible Configuration**: Easy YAML config with environment variables support
- 🛡️ **Production Ready**: Cooldown mechanisms, retry logic, graceful shutdown

---

## 📋 Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/xnetvn-com/xnetvn_monitord.git
cd xnetvn_monitord

# Run installation script
sudo bash scripts/install.sh

# Edit configuration
sudo vi /opt/xnetvn_monitord/config/main.yaml

# Start service
sudo systemctl start xnetvn_monitord

# Check status
sudo systemctl status xnetvn_monitord
```

---

## 🎨 What It Monitors

### Services
- Nginx, Apache2, PHP-FPM (all versions), MariaDB/MySQL, PostgreSQL
- Redis, Memcached, Docker, SSH, Cron, Fail2Ban, UFW
- HestiaCP stack: Hestia service, Exim/Postfix, Dovecot, Bind9/Named, FTP
- ClamAV, SpamAssassin (spamd), custom services via regex
- HTTP/HTTPS web endpoints for health checks (local or public)

### Resources
- **CPU Load**: 1/5/15-minute averages
- **Memory**: Free RAM by percentage and MB
- **Disk Space**: Multiple mount points monitoring

---

## 📖 Documentation

- **Vietnamese**: [docs/vi/README.md](docs/vi/README.md)
- **English**: [docs/en/README.md](docs/en/README.md)

---

## 🔧 Configuration Example

```yaml
general:
  check_interval: 60

service_monitor:
  enabled: true
  action_on_failure: "restart_and_notify"

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
