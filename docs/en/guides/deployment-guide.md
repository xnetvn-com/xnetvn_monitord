---
post_title: "Deployment guide (detailed)"
author1: "xNetVN Inc."
post_slug: "docs-en-deployment-guide"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- deployment
	- systemd
ai_note: "AI-assisted"
summary: "Deployment and update workflow following systemd best practices."
post_date: "2026-02-03"
---

## Deployment guide (detailed)

## 1. Deploy with the script

```
sudo bash scripts/install.sh
```

## 2. Post-deployment checks

- Ensure the service is running: `systemctl status xnetvn_monitord`.
- Verify logs contain no critical errors.

## 3. Update workflow

1. Update the source code at `/opt/xnetvn_monitord/`.
2. Update configuration if needed.
3. Restart the service.

## 4. Rollback

- Back up configuration before updating.
- Restore the backup and restart the service.
