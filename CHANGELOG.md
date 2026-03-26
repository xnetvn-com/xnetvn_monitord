## Changelog

All notable changes to this project will be documented here.

This format follows Keep a Changelog and uses Semantic Versioning.

## [Unreleased]

## [1.5.0] - 2026-03-26

### Changed

- Release: bump package to v1.5.0 and refresh release metadata for tag-driven publication.

## [1.4.0] - 2026-03-25

### Changed

- Notifications: include safe top-5 process diagnostics in service/resource alert system stats for CPU %, CPU core load, RAM, disk I/O, and best-effort per-process network throughput.

### Fixed

- Notifications: keep process diagnostics sanitized to executable name/user/PID and explicitly mark per-process network throughput as unavailable when the optional collector is missing, unprivileged, or returns no valid rows.

## [1.3.0] - 2026-03-23

### Changed

- Release: bump package to v1.3.0, align release/install examples with tag-driven publication, and refresh release metadata.

## [1.2.7] - 2026-03-22

### Changed

- Release: bump package to v1.2.7 and refresh release metadata for tag-driven publication.

## [1.2.6] - 2026-03-19

### Changed

- Release: bump package to v1.2.6 and refresh release metadata for tag-driven publication.

## [1.2.5] - 2026-03-19

### Changed

- Release: bump package to v1.2.5 and include minor notifier fix.


## [1.2.4] - 2026-03-19

### Changed

- Bump package to v1.2.4 and update docs/examples for the release.


## [1.2.3] - 2026-03-17

### Changed

- Bump package to v1.2.3 and update docs/examples/prompts/tests (release commit).



## [1.2.2] - 2026-03-17

### Changed

- Bump package to v1.2.2 and update docs/examples/prompts/tests (c0bbf64).
- Fix: improve response handling in read_response_preview and add unit test for error cases (#23) (e086d2b).
- Enhance update mechanism and logging for xNetVN Monitor Daemon (ca00ee5).
- Docs: update installation instructions for non-technical users with direct GitHub installer commands (d826b59).

## [1.2.1] - 2026-03-17

### Added

- Installer: add `--releases=latest` and `--releases=vX.Y.Z` options for installing from GitHub release tags.
- Update documentation and release prompts to reference the current version.


## [1.2.0] - 2026-02-09

### Added

- Add CI workflows for testing, code quality, and security scanning (c772dbe).

### Changed

- Modularize GitHub Actions pipelines and streamline testing and matrix (09da261, 10b22f8, 3d35772, 4cf9099).

### Fixed

- CI: remove python3 distutils and coverage fix (44e1fde).

### Security

- Add Bandit SARIF generation and security scanning to CI.

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
