---
post_title: "Changelog"
author1: "xNetVN Inc."
post_slug: "docs-en-changelog"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- changelog
ai_note: "AI-assisted"
summary: "Change history following Keep a Changelog."
post_date: "2026-02-06"
---

## Changelog

All notable changes to this project will be documented here.

This format follows Keep a Changelog and uses Semantic Versioning.

## [Unreleased]

### Added

- None.

### Changed

- None.

### Fixed

- None.

## [1.1.0] - 2026-02-06

### Added

- Updated Vietnamese documentation (README, index, architecture, configuration, installation).
- Added iptables check method and sample configuration entries for HestiaCP services/apps.
- Added documentation updates covering iptables and HestiaCP webmail/admin health checks.

### Changed

- None.

### Fixed

- Ensure update checks run on the first execution when no state file exists.
- Harden installer venv setup to handle missing ensurepip/pip on Ubuntu 24 LTS.
- Documented Ubuntu 24 LTS venv/pip installation recovery steps.
- Fixed update script version detection to avoid import failures and refresh the
	installed updater in /opt/xnetvn_monitord/scripts.
- Merged PR #6 (f1c5c56): feat(installation): enhance venv setup and add recovery docs for Ubuntu 24 LTS.

## [1.0.0] - 2026-01-31

### Added

- Service and system resource monitoring daemon.
- Automatic recovery actions (service restart or recovery command).
- Email/Telegram/Slack/Discord/Webhook alerts with rate limiting and content filtering.
- Logging with rotation and PID file.
- Unit/integration/security test suite.
