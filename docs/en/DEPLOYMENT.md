---
post_title: "Deployment"
author1: "xNetVN Inc."
post_slug: "docs-en-deployment"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- deployment
	- systemd
ai_note: "AI-assisted"
summary: "Deploy xnetvn_monitord with systemd and operate safely."
post_date: "2026-02-03"
---

## Deployment

## 1. Deploy with systemd

Production deployments should use systemd to ensure auto-start and restart on
failures.

### 1.1. Install via Script

```
sudo bash scripts/install.sh
```

The script will:

- Install the service at /etc/systemd/system/xnetvn_monitord.service.
- Copy configuration to /opt/xnetvn_monitord/config/main.yaml.
- Create EnvironmentFile at /etc/xnetvn_monitord/xnetvn_monitord.env (if provided).

### 1.2. Operate the Service

```
sudo systemctl start xnetvn_monitord
sudo systemctl status xnetvn_monitord
sudo systemctl restart xnetvn_monitord
```

Follow logs:

```
sudo journalctl -u xnetvn_monitord -f
```

## 2. Update Configuration

1. Edit the configuration file.
2. Reload or restart the service:

```
sudo systemctl reload xnetvn_monitord
```

Note: ExecReload sends SIGHUP so the daemon reloads configuration at runtime.

## 3. Rollback

- Keep a backup of configuration before changes.
- If issues occur, restore config and restart the service.

## 4. Security Notes

- The unit file currently runs as User=root. Re-evaluate if reducing privileges.
- The security.run_as_user and security.run_as_group fields are not applied to
  the systemd unit automatically.
- Consider systemd hardening (NoNewPrivileges, ProtectHome,
  CapabilityBoundingSet).
