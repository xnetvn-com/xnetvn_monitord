---
post_title: "Data flow diagram (DFD)"
author1: "xNetVN Inc."
post_slug: "docs-en-main-dfd"
microsoft_alias: ""
featured_image: ""
categories:
    - architecture
tags:
    - dfd
ai_note: "AI-assisted"
summary: "Describes the primary data flow of the daemon."
post_date: "2026-02-03"
---

## Data flow diagram (DFD)

## 1. Main flow

```
[Config YAML] -> [ConfigLoader] -> [MonitorDaemon]
                                   |-> [ServiceMonitor] -> [ServiceManager/systemctl/openrc/sysv/process]
                                   |-> [ResourceMonitor] -> [psutil/os]
                                   |-> [UpdateChecker] -> [GitHub API]
                                   |-> [NotificationManager] -> [SMTP/Telegram/Slack/Discord/Webhook]
```

## 2. Description

- YAML config is loaded and expanded with environment variables.
- The daemon orchestrates service/resource checks.
- When thresholds are exceeded or failures occur, it runs recovery and sends alerts.
