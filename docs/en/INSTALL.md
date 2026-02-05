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
- Create a virtual environment at /opt/xnetvn_monitord/.venv.
- Install PyYAML and psutil inside the virtual environment.
- Copy source code to /opt/xnetvn_monitord.
- Create /opt/xnetvn_monitord/config/main.yaml and /opt/xnetvn_monitord/config/.env
	from the example files if they do not exist, with permissions set to 0600.
- Always refresh /opt/xnetvn_monitord/config/main.example.yaml and
  /opt/xnetvn_monitord/config/.env.example (overwriting template files).
- Install the systemd unit to /etc/systemd/system/xnetvn_monitord.service.

Note: the script does not overwrite /opt/xnetvn_monitord/config/main.yaml or
/opt/xnetvn_monitord/config/.env if they already exist.

Note (Ubuntu 24 LTS / PEP 668): the script always uses a virtual environment
to avoid externally-managed-environment errors when installing Python packages.

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

## 3. Manual Update

The scripts/update.sh script checks GitHub Releases and applies updates.
It creates a backup before updating and never overwrites main.yaml or .env.

Run the installed update script:

```
sudo bash /opt/xnetvn_monitord/scripts/update.sh
```

Or run from the repository clone:

```
sudo bash scripts/update.sh
```

Common flags:

```
# Simulate the update without making any changes (safe for testing)
--dry-run

# Skip the interactive confirmation prompt
--yes

# Reduce non-error output
--quiet
```

If your environment requires IPv4-only outbound access, set:

```
XNETVN_MONITORD_FORCE_IPV4=1 sudo bash /opt/xnetvn_monitord/scripts/update.sh
```
## 4. Development Setup

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run the daemon manually:

```
python3 -m xnetvn_monitord.daemon config/main.yaml
```

## 5. Logs and PID File

- Default log: /var/log/xnetvn_monitord/monitor.log.
- Default PID file: /var/run/xnetvn_monitord.pid.

## 6. Uninstall (Manual)

```
sudo systemctl stop xnetvn_monitord
sudo systemctl disable xnetvn_monitord
sudo rm -f /etc/systemd/system/xnetvn_monitord.service
sudo rm -rf /opt/xnetvn_monitord
sudo rm -rf /var/log/xnetvn_monitord
```
