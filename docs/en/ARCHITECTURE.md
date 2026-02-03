---
post_title: "System Architecture"
author1: "xNetVN Inc."
post_slug: "docs-en-architecture"
microsoft_alias: ""
featured_image: ""
categories:
   - documentation
tags:
   - architecture
   - monitoring
ai_note: "AI-assisted"
summary: "Architecture, components, and data flow of xnetvn_monitord."
post_date: "2026-02-03"
---

## System Architecture

## Overview

xnetvn_monitord is a background monitoring daemon that periodically checks
services and resources, then performs recovery and sends alerts. Modules are
separated clearly for easier extensibility.

## Core Components

### MonitorDaemon

- Loads configuration via ConfigLoader.
- Loads environment variables from /opt/xnetvn_monitord/config/.env.
- Sets up logging with rotation and creates a PID file.
- Initializes ServiceMonitor, ResourceMonitor, NotificationManager.
- Runs the monitoring loop using general.check_interval.
- Handles SIGTERM, SIGINT, SIGHUP.

### ServiceMonitor

- Checks service status using multiple methods.
- Supports action_on_failure: restart or restart_and_notify.
- Supports pre_restart_hook and post_restart_hook.
- Returns detailed results for daemon notifications.

### ResourceMonitor

- Checks CPU load (1/5/15 minutes).
- Checks RAM by percent or MB thresholds.
- Checks disk per mount point.
- Executes recovery_command or restarts services with cooldown.

### NotificationManager

- Manages Email, Telegram, Slack, Discord, Webhook.
- Filters sensitive content via content_filter.
- Applies min severity and rate limits per channel.
- Sends notifications by event type (service/resource/action).

### UpdateChecker

- Checks versions via GitHub Releases.
- Writes last check state to state_file.
- Optionally sends notifications or performs auto update.

### ConfigLoader and EnvLoader

- Loads YAML and expands environment variables.
- Missing environment variables resolve to null (YAML None).

### ServiceManager

- Auto-detects systemd/OpenRC/SysV.
- Builds corresponding check and restart commands.

## Data Flow

1. MonitorDaemon loads .env and YAML config.
2. Initializes logging, PID file, monitors, and notifiers.
3. If enabled, update checker runs a version check.
4. Loop:
    - ServiceMonitor.check_all_services → results → NotificationManager.
    - ResourceMonitor.check_resources → recovery → NotificationManager.
5. SIGHUP → reload config and update runtime.

## External Integrations

- Systemd/OpenRC/SysV: service lifecycle and restarts.
- SMTP: email alerts.
- Telegram Bot API: Telegram alerts.
- Slack/Discord webhooks: webhook alerts.
- Custom webhooks: JSON payloads to internal endpoints.
- GitHub API: version update checks.

## Operational Notes

- test_on_startup controls whether to send test notifications at startup.
- Rate limits and min severity help prevent alert spam.
- Cooldowns prevent repeated recovery actions.

## Architecture Extensions

- Add new notifiers by extending NotificationManager.
- Add new check methods in ServiceMonitor as needed.
