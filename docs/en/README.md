# xnetvn_monitord

**xnetvn_monitord** is a monitoring daemon for modern Linux servers that tracks critical services and system resources. When failures or threshold breaches are detected, the daemon automatically performs recovery actions and sends notifications via Email/Telegram.

## Goals

- Continuously monitor critical services and system resources.
- Automatically recover to reduce downtime.
- Send timely alerts with rate limiting and content filtering.

## Key Features

- Service monitoring (systemd/OpenRC/SysV/process/regex/custom/HTTP/HTTPS).
- Per-service check intervals and action cooldowns.
- Pre- and post-recovery notifications.
- CPU/RAM/Disk threshold monitoring.

## Common Services (Ubuntu Web Server & HestiaCP)

The full sample list is provided in `config/main.example.yaml` (disabled by default),
including the most common service groups:

- Web stack: Nginx, Apache2, PHP-FPM (all versions), MariaDB/MySQL, PostgreSQL.
- Cache and platform: Redis, Memcached, Docker.
- Security and system: SSH, Cron, Fail2Ban, UFW.
- HestiaCP stack: Hestia service, Exim/Postfix, Dovecot, Bind9/Named, FTP.
- Anti-malware: ClamAV (daemon/freshclam), SpamAssassin (spamd).
- HTTP/HTTPS health checks (public or localhost).

## System Requirements

- Linux distributions: Ubuntu LTS, Debian, CentOS, RHEL, Rocky/Alma, Fedora, Arch,
  openSUSE/SLES, Alpine
- Python 3.8+ (3.10+ recommended)
- System privileges to manage services and write logs

## Service Manager Compatibility

- systemd (Ubuntu/Debian/RHEL/CentOS/Rocky/Alma/Fedora/Arch/openSUSE/SLES)
- OpenRC (Alpine)
- SysV init (fallback)

Override auto-detection with the `XNETVN_SERVICE_MANAGER` environment variable
(`systemd`, `openrc`, or `sysv`).

## Quick Installation

```bash
git clone https://github.com/xnetvn-com/xnetvn_monitord.git
cd xnetvn_monitord
sudo bash scripts/install.sh
```

## Configuration

Default configuration file: `config/main.yaml` (see `config/main.example.yaml`).

Key sections:

- `general`: application metadata, logging, PID
- `service_monitor`: services to watch and recovery actions
- `service_monitor` also supports HTTP/HTTPS health checks and per-service intervals
- `resource_monitor`: CPU/RAM/Disk thresholds and recovery actions
- `notifications`: Email/Telegram and rate limits

## Operations

```bash
sudo systemctl start xnetvn_monitord
sudo systemctl status xnetvn_monitord
sudo journalctl -u xnetvn_monitord -f
```

## Contact

- Website: https://xnetvn.com/
- Email: license@xnetvn.net
- Repository: https://github.com/xnetvn-com/xnetvn_monitord