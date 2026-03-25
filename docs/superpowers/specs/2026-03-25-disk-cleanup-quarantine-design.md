# Disk Cleanup Quarantine Design

## Summary

This design adds a production-safe disk cleanup capability to `resource_monitor.disk`
for `action_on_threshold: "cleanup"` and `action_on_threshold: "both"`.

The feature is intentionally conservative:

- It never deletes matched files directly from live locations.
- It quarantines first, then purges only quarantined items after retention rules.
- It keeps strict filesystem, path, and symlink safety boundaries.
- It is optimized to minimize CPU, disk I/O, and latency impact on busy Linux servers.
- It provides an explicit restore path via dedicated scripts and manifest metadata.

## User-Approved Direction

The approved operating mode is:

- `quarantine_then_delete`

This means:

1. Candidate files or directories are discovered from configured include selectors.
2. Protected or excluded paths are skipped.
3. Eligible items are moved into a quarantine area together with metadata.
4. Purge only happens inside quarantine after retention checks.
5. Recovery scripts can restore quarantined items back to their original paths before purge.

## Existing Codebase Findings

Current repository behavior relevant to this feature:

- `resource_monitor.disk.action_on_threshold` exists in `config/main.example.yaml` but is not consumed by the current Python implementation.
- `ResourceMonitor._handle_low_disk()` only restarts configured services through `recovery_actions.low_disk_services`.
- `ResourceMonitor` is already the orchestration point for CPU, memory, and disk threshold actions.
- Tests already cover disk threshold evaluation, cooldown behavior, and action result aggregation.
- No cleanup, quarantine, restore, or path-selector subsystem exists today.

## Design Goals

### Safety

- Never directly delete live files outside quarantine.
- Never follow symlinks during scan, quarantine, purge, or restore.
- Never operate on protected system paths.
- Never cross mount boundaries unexpectedly.
- Never overwrite an existing destination during restore without an explicit safe policy.

### Operational Stability

- Keep monitoring loop impact bounded.
- Use streaming directory iteration instead of loading large trees into memory.
- Prefer same-filesystem rename/move semantics to avoid file copy overhead.
- Stop early once enough free space is reclaimed or safety/runtime bounds are reached.

### Auditability

- Every quarantined item must have restorable metadata.
- Every run must report scanned, matched, excluded, skipped, quarantined, purged, restored, errors, and reclaimed bytes.
- Notifications and logs must describe what happened without leaking sensitive file contents.

### Compatibility

- Preserve current `notify` behavior.
- Preserve current low-disk service restart behavior.
- Keep backward compatibility for disk mount point config keys (`paths`, `mount_points`).

## Proposed Architecture

### 1. ResourceMonitor remains orchestration layer

`ResourceMonitor` will:

- evaluate disk thresholds
- read `disk.action_on_threshold`
- invoke a dedicated cleanup engine when cleanup is enabled
- invoke low-disk service recovery when required by action mode
- append structured action results for notifications

### 2. Add a dedicated cleanup engine module

Create a focused module under `src/xnetvn_monitord/monitors/` to keep responsibilities separated from `ResourceMonitor`.

Planned responsibilities:

- configuration normalization and validation
- selector matching (`exact`, `regex`, `glob`)
- safe candidate scanning
- protected path enforcement
- same-filesystem quarantine movement
- retention-based purge inside quarantine
- manifest generation and reading
- restore support primitives shared with restore scripts

### 3. Add restore scripts

Dedicated scripts will restore quarantined items back to their original locations using manifest data.

The scripts will:

- read quarantine metadata only
- validate target safety before restore
- refuse destructive overwrite by default
- restore exact original absolute paths
- support dry-run preview
- support restoring one item, all items, or filtered subsets

## Configuration Contract

### Top-Level Disk Action

Supported values for `resource_monitor.disk.action_on_threshold`:

- `notify`: send threshold notifications only
- `cleanup`: run cleanup only
- `both`: run cleanup first, then run low-disk recovery services if configured

### Cleanup Block

Proposed structure:

```yaml
resource_monitor:
  disk:
    action_on_threshold: "both"
    cleanup:
      enabled: true
      mode: "quarantine_then_delete"
      quarantine_dir: "/opt/xnetvn_monitord/.local/quarantine/disk_cleanup"
      stop_when_threshold_cleared: true
      minimum_reclaimed_mb: 512
      max_items_per_run: 500
      max_runtime_seconds: 120
      follow_symlinks: false
      continue_on_error: true
      dry_run: false
      sort_by: "largest_first"
      allow_directories: true
      selectors:
        include: []
        exclude: []
      rules:
        file_types: ["file", "directory"]
        min_age_days: 7
        min_size_mb: 10
        empty_dirs_only: false
      retention:
        quarantine_max_age_days: 14
        quarantine_max_size_mb: 2048
      safety:
        require_same_filesystem_as_mount_point: true
        require_quarantine_same_filesystem: true
        protected_paths: []
        protected_patterns: []
```

## Selector Types

Each selector item supports:

- `type: "exact"`
- `type: "regex"`
- `type: "glob"`

Each selector also has:

- `pattern`: matching expression

Matching rules:

- `exact` is case-sensitive and must match the normalized absolute path exactly.
- `regex` is matched against the normalized absolute path.
- `glob` uses shell-style glob matching against the normalized absolute path.

## Protected Path Policy

The feature must ship with hard-coded default protected paths for Linux, especially Ubuntu.

Minimum built-in defaults:

- `/`
- `/boot`
- `/etc`
- `/usr`
- `/var/lib`
- `/var/lib/dpkg`
- `/var/lib/systemd`
- `/var/log/journal`
- `/proc`
- `/sys`
- `/dev`
- `/run`
- `/snap`

These built-ins should be merged with user-configured protected lists, not replaced by them.

## Low-Resource Execution Strategy

The user's requirement to minimize server resource usage is valid and should be mandatory.

Implementation policy:

- use `os.scandir()` for streaming traversal
- prune excluded or protected directories before descending
- avoid content hashing, compression, checksum passes, or archive creation
- avoid cross-filesystem copies by requiring quarantine on the same filesystem
- prefer atomic rename/move operations when possible
- evaluate files lazily and stop once reclaim target or threshold recovery is reached
- enforce `max_items_per_run` and `max_runtime_seconds`
- avoid changing process niceness for the whole daemon because that could affect unrelated monitor work; instead rely on bounded work and I/O-efficient operations

This is safer than trying to globally `nice` or `ionice` the daemon process, which can have uneven behavior and may require privileges not guaranteed in production.

## Quarantine Metadata Design

Each quarantined item requires metadata sufficient for exact restore.

Required fields:

- item identifier
- original absolute path
- quarantine absolute path
- mount point
- item type (`file` or `directory`)
- selector type and matched pattern
- size in bytes
- timestamps captured at quarantine time
- cleanup run id
- restore status

Metadata storage proposal:

- one manifest file per cleanup run under the quarantine root
- one metadata file per quarantined item if needed for easier restore and audit

This allows fast listing and exact restore without rescanning live trees.

## Restore Script Design

The user's request for restore scripts is valid and strongly recommended.

Required behavior:

- restore exact original paths
- support dry-run
- support restoring by run id
- support restoring a single item id
- support restoring all non-purged items
- refuse overwrite when destination already exists unless an explicit force flag is given
- validate parent directory creation safely
- validate that restore source is inside the configured quarantine root

Recommended scripts:

- `scripts/restore_disk_cleanup.sh`: operator-facing wrapper
- optional Python helper invoked by the shell script for manifest-safe path handling if shell alone becomes too fragile

## Detailed Commenting Requirement For main.example.yaml

The user's requirement to document every parameter and every supported value in `main.example.yaml` is reasonable.

Guidance:

- document all new cleanup parameters in English only
- explicitly list supported enum values next to each enum field
- document selector item schema and examples for `exact`, `regex`, and `glob`
- document restore script usage references where appropriate
- explain default safe behavior and why direct deletion is not the default

This will enlarge the sample config, but that tradeoff is justified because the feature is destructive if misconfigured.

## Action Ordering

When disk threshold is exceeded:

1. collect disk result
2. emit threshold event as today
3. if mode is `cleanup` or `both`, attempt cleanup
4. if mode is `both`, optionally run low-disk service restarts after cleanup
5. emit structured action result for cleanup and, if applicable, service recovery

Rationale:

- cleanup may already reclaim enough space, making service restart unnecessary in some deployments
- preserving ordered action results improves observability

## Error Handling Strategy

- invalid selector regex should fail configuration validation for that cleanup run and report a structured error
- path permission errors should be recorded per item and should not crash the whole monitoring cycle
- quarantine move failures should not trigger direct delete fallback
- restore failures should preserve quarantine state for retry
- purge only occurs inside quarantine and only after metadata validation

## Testing Strategy

Mandatory coverage areas:

1. selector matching
2. include/exclude precedence
3. protected path blocking
4. symlink blocking
5. same-filesystem enforcement
6. quarantine manifest creation
7. restore exact original path
8. restore collision refusal
9. bounded scan runtime and item count
10. `notify`, `cleanup`, and `both` orchestration modes
11. retention purge only inside quarantine
12. dry-run behavior

## Risks And Mitigations

### Risk: directory traversal or symlink escape

Mitigation:

- realpath normalization
- no symlink following
- quarantine root containment checks

### Risk: heavy I/O on busy servers

Mitigation:

- same-filesystem rename only
- bounded batch execution
- early stop after reclaim target
- streaming traversal

### Risk: restoring over live files

Mitigation:

- no overwrite by default
- explicit operator confirmation through script flags

### Risk: deleting critical Ubuntu state

Mitigation:

- hard-coded protected defaults
- user-configurable additional protected paths and patterns
- quarantine-first policy

## Files Expected To Change

Core code:

- `src/xnetvn_monitord/monitors/resource_monitor.py`
- new cleanup engine module under `src/xnetvn_monitord/monitors/`

Tests:

- `tests/unit/test_resource_monitor.py`
- new cleanup-focused unit test file under `tests/unit/`

Ops and config:

- `config/main.example.yaml`
- new restore script under `scripts/`

Docs:

- `docs/en/CONFIG.md`
- matching Vietnamese documentation under `docs/vi/`

Future customization updates after implementation:

- relevant repository instructions and skill files describing safe disk cleanup conventions

## Decision

Proceed with a dedicated cleanup engine, quarantine-first restore-capable workflow, low-I/O scanning policy, and explicit restore scripts.