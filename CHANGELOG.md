## Changelog

All notable changes to this project will be documented here.

This format follows Keep a Changelog and uses Semantic Versioning.

## [Unreleased]

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

## [1.0.0] - 2026-01-31

### Added

- Service and system resource monitoring daemon.
- Automatic recovery actions (service restart or recovery command).
- Email/Telegram/Slack/Discord/Webhook alerts with rate limiting and content filtering.
- Logging with rotation and PID file.
- Unit/integration/security test suite.
