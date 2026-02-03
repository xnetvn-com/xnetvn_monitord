---
post_title: "Installation"
author1: "xNetVN Inc."
post_slug: "docs-en-install"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- install
	- systemd
ai_note: "AI-assisted"
summary: "Install and start xnetvn_monitord on Linux."
post_date: "2026-02-03"
---

## Installation Guide

## 1. System Requirements

- Linux (preferably Ubuntu/Debian/CentOS/RHEL/Rocky/Alma/Fedora/Arch/openSUSE/SLES/Alpine).
- Python 3.8+ (3.10+ recommended).
- Root or sudo permissions to install the systemd service and write system logs.

## 2. Production Install via Script

The scripts/install.sh script will:

- Install python3 and pip3 (if missing).
- Install PyYAML and psutil.
- Copy source code to /opt/xnetvn_monitord.
- Copy configuration to /opt/xnetvn_monitord/config/main.yaml.
- Always refresh /opt/xnetvn_monitord/config/main.example.yaml and
  /opt/xnetvn_monitord/config/.env.example (overwriting template files).
- Install the systemd unit to /etc/systemd/system/xnetvn_monitord.service.

Note: the script does not overwrite /opt/xnetvn_monitord/config/main.yaml or
/opt/xnetvn_monitord/config/.env if they already exist.

Note: the script is optimized for systemd. For OpenRC (Alpine), install manually
or create an OpenRC service according to your distribution.

Run:

```
sudo bash scripts/install.sh
```

After installation, edit the configuration:

```
sudo vi /opt/xnetvn_monitord/config/main.yaml
```

Set secrets via EnvironmentFile (recommended):

```
sudo mkdir -p /etc/xnetvn_monitord
sudo vi /etc/xnetvn_monitord/xnetvn_monitord.env
sudo chmod 600 /etc/xnetvn_monitord/xnetvn_monitord.env
```

Start the service:

```
sudo systemctl start xnetvn_monitord
sudo systemctl status xnetvn_monitord
```

## 3. Development Setup

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run the daemon manually:

```
python3 -m xnetvn_monitord.daemon config/main.yaml
```

## 4. Logs and PID File

- Default log: /var/log/xnetvn_monitord/monitor.log.
- Default PID file: /var/run/xnetvn_monitord.pid.

## 5. Uninstall (Manual)

```
sudo systemctl stop xnetvn_monitord
sudo systemctl disable xnetvn_monitord
sudo rm -f /etc/systemd/system/xnetvn_monitord.service
sudo rm -rf /opt/xnetvn_monitord
sudo rm -rf /var/log/xnetvn_monitord
```
