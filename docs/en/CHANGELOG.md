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
post_date: "2026-02-03"
---

## Changelog

All notable changes to this project will be documented here.

This format follows Keep a Changelog and uses Semantic Versioning.

## [Unreleased]

### Added

- Updated Vietnamese documentation (README, index, architecture, configuration, installation).

### Changed

- None.

### Fixed

- Fixed update script version detection to avoid import failures and refresh the
	installed updater in /opt/xnetvn_monitord/scripts.

## [1.0.0] - 2026-01-31

### Added

- Service and system resource monitoring daemon.
- Automatic recovery actions (service restart or recovery command).
- Email/Telegram/Slack/Discord/Webhook alerts with rate limiting and content filtering.
- Logging with rotation and PID file.
- Unit/integration/security test suite.
