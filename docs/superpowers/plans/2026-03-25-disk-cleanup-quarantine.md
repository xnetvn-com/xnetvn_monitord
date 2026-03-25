# Disk Cleanup Quarantine Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a production-safe disk cleanup workflow that quarantines matched files first, restores them exactly when requested, and only purges inside quarantine after retention checks.

**Architecture:** `ResourceMonitor` remains the orchestrator for disk threshold actions while a new dedicated cleanup engine encapsulates selector matching, safety validation, quarantine movement, purge logic, manifest metadata, and restore support. The implementation prioritizes bounded work, same-filesystem moves, no symlink following, and explicit recovery tooling.

**Tech Stack:** Python 3, pytest, psutil, pathlib/os/scandir, YAML config, Bash operator scripts.

---

## Context Map

### Files to Modify

| File | Purpose | Changes Needed |
|------|---------|----------------|
| `src/xnetvn_monitord/monitors/resource_monitor.py` | Resource threshold orchestration | Wire `disk.action_on_threshold`, invoke cleanup engine, aggregate cleanup and recovery results |
| `config/main.example.yaml` | Canonical sample config | Add full cleanup/quarantine/restore config with detailed English comments and supported values |
| `tests/unit/test_resource_monitor.py` | Existing disk monitor coverage | Extend orchestration tests for `notify`, `cleanup`, `both`, cooldown, and action aggregation |
| `docs/en/CONFIG.md` | English config contract | Document cleanup configuration, restore semantics, and supported values |
| `docs/vi/CONFIG.md` or equivalent Vietnamese config doc | Source-of-truth Vietnamese docs | Mirror the new config contract and safety guidance |

### Files to Create

| File | Purpose |
|------|---------|
| `src/xnetvn_monitord/monitors/disk_cleanup.py` | Dedicated cleanup engine and data normalization helpers |
| `tests/unit/test_disk_cleanup.py` | Unit coverage for selectors, scanning, quarantine, purge, restore metadata, and safety guards |
| `scripts/restore_disk_cleanup.sh` | Operator-facing restore entrypoint with dry-run and filtering support |
| `docs/superpowers/specs/2026-03-25-disk-cleanup-quarantine-design.md` | Approved design spec |

### Dependencies (may need updates)

| File | Relationship |
|------|--------------|
| `src/xnetvn_monitord/monitors/__init__.py` | May need export update if cleanup engine is shared/imported elsewhere |
| `src/xnetvn_monitord/daemon.py` | Consumes `action_results`; verify no payload contract regressions |
| `tests/conftest.py` | May add cleanup-specific fixtures or temporary filesystem helpers |
| `scripts/run_tests.sh` | No direct change expected, but resulting tests must remain compatible |

### Test Files

| Test | Coverage |
|------|----------|
| `tests/unit/test_resource_monitor.py` | Disk threshold orchestration, action modes, cooldown, result aggregation |
| `tests/unit/test_disk_cleanup.py` | Cleanup engine behavior, safety guards, manifest, restore, purge, low-I/O bounds |

### Reference Patterns

| File | Pattern |
|------|---------|
| `src/xnetvn_monitord/monitors/resource_monitor.py` | Existing action orchestration and structured action results |
| `tests/unit/test_resource_monitor.py` | Existing TDD-style monitor coverage patterns |
| `src/xnetvn_monitord/utils/update_checker.py` | Existing safety-oriented validation style for destructive archive handling |
| `scripts/update.sh` | Operator-facing script conventions, safety prompts, and dry-run expectations |

### Risk Assessment

- [x] Breaking changes to public API: configuration contract expands; backward compatibility must be preserved
- [ ] Database migrations needed
- [x] Configuration changes required
- [x] Operational scripts required
- [x] Destructive behavior risk requires strict quarantine-first and restore path

## Chunk 1: Cleanup Engine Contract

### Task 1: Define cleanup engine public contract

**Files:**
- Create: `src/xnetvn_monitord/monitors/disk_cleanup.py`
- Test: `tests/unit/test_disk_cleanup.py`

- [ ] **Step 1: Write the failing tests for config normalization and selector validation**

Add tests for:

```python
def test_should_accept_exact_regex_and_glob_selectors():
    ...

def test_should_reject_invalid_selector_type():
    ...

def test_should_reject_invalid_regex_selector():
    ...
```

- [ ] **Step 2: Run targeted tests to verify red state**

Run: `pytest tests/unit/test_disk_cleanup.py -q`
Expected: failures for missing module or missing helpers

- [ ] **Step 3: Implement minimal cleanup config normalization layer**

Implement typed/structured helpers that:

- normalize include/exclude selectors
- normalize supported enum values
- merge built-in protected paths with configured ones
- validate `mode == "quarantine_then_delete"`

- [ ] **Step 4: Run targeted tests to verify green state**

Run: `pytest tests/unit/test_disk_cleanup.py -q`
Expected: new selector/config tests pass

## Chunk 2: Safe Path Matching And Traversal

### Task 2: Implement low-I/O candidate scanning with safety pruning

**Files:**
- Modify: `src/xnetvn_monitord/monitors/disk_cleanup.py`
- Test: `tests/unit/test_disk_cleanup.py`

- [ ] **Step 1: Write the failing tests for path selection and pruning**

Add tests for:

```python
def test_should_match_exact_path_case_sensitively():
    ...

def test_should_match_regex_against_normalized_absolute_path():
    ...

def test_should_match_glob_against_normalized_absolute_path():
    ...

def test_should_skip_excluded_paths_before_descending():
    ...

def test_should_skip_protected_paths():
    ...

def test_should_skip_symlink_targets():
    ...

def test_should_skip_paths_outside_mount_boundary():
    ...
```

- [ ] **Step 2: Run targeted tests to verify red state**

Run: `pytest tests/unit/test_disk_cleanup.py -q`
Expected: traversal and safety tests fail

- [ ] **Step 3: Implement streaming traversal**

Implementation requirements:

- use `os.scandir()`
- prune excluded/protected directories before recursion
- do not follow symlinks
- optionally sort candidates lazily by configured strategy after bounded collection
- stop when `max_items_per_run` or `max_runtime_seconds` is hit

- [ ] **Step 4: Run targeted tests to verify green state**

Run: `pytest tests/unit/test_disk_cleanup.py -q`
Expected: selector and traversal tests pass

## Chunk 3: Quarantine Movement And Manifest Metadata

### Task 3: Quarantine matched items safely

**Files:**
- Modify: `src/xnetvn_monitord/monitors/disk_cleanup.py`
- Test: `tests/unit/test_disk_cleanup.py`

- [ ] **Step 1: Write the failing tests for quarantine operations**

Add tests for:

```python
def test_should_require_quarantine_on_same_filesystem_when_configured():
    ...

def test_should_move_file_into_quarantine_and_record_manifest():
    ...

def test_should_move_directory_into_quarantine_when_allowed():
    ...

def test_should_refuse_directory_quarantine_when_disallowed():
    ...

def test_should_preserve_original_path_in_manifest():
    ...

def test_should_not_fallback_to_direct_delete_when_quarantine_move_fails():
    ...
```

- [ ] **Step 2: Run targeted tests to verify red state**

Run: `pytest tests/unit/test_disk_cleanup.py -q`
Expected: quarantine and manifest tests fail

- [ ] **Step 3: Implement quarantine move and metadata recording**

Implementation requirements:

- generate stable item ids
- create per-run manifest data
- record original path, quarantine path, size, timestamps, selector match, and restore status
- use same-filesystem move/rename semantics only when required by config

- [ ] **Step 4: Run targeted tests to verify green state**

Run: `pytest tests/unit/test_disk_cleanup.py -q`
Expected: quarantine and manifest tests pass

## Chunk 4: Purge Logic Inside Quarantine Only

### Task 4: Add retention-based purge

**Files:**
- Modify: `src/xnetvn_monitord/monitors/disk_cleanup.py`
- Test: `tests/unit/test_disk_cleanup.py`

- [ ] **Step 1: Write the failing tests for purge behavior**

Add tests for:

```python
def test_should_purge_only_items_inside_quarantine():
    ...

def test_should_purge_items_older_than_retention():
    ...

def test_should_skip_non_manifested_items():
    ...

def test_should_support_dry_run_purge():
    ...
```

- [ ] **Step 2: Run targeted tests to verify red state**

Run: `pytest tests/unit/test_disk_cleanup.py -q`
Expected: purge tests fail

- [ ] **Step 3: Implement purge policy**

Implementation requirements:

- purge only quarantined items validated by manifest metadata
- never purge live-path items
- support retention by age and quarantine size policy
- report reclaimed bytes and purge counts

- [ ] **Step 4: Run targeted tests to verify green state**

Run: `pytest tests/unit/test_disk_cleanup.py -q`
Expected: purge tests pass

## Chunk 5: Restore Support And Operator Scripts

### Task 5: Add restore primitives and operator-facing script

**Files:**
- Modify: `src/xnetvn_monitord/monitors/disk_cleanup.py`
- Create: `scripts/restore_disk_cleanup.sh`
- Test: `tests/unit/test_disk_cleanup.py`

- [ ] **Step 1: Write the failing tests for restore semantics**

Add tests for:

```python
def test_should_restore_item_to_exact_original_path():
    ...

def test_should_refuse_restore_when_destination_already_exists():
    ...

def test_should_support_restore_by_run_id():
    ...

def test_should_support_restore_dry_run():
    ...
```

- [ ] **Step 2: Run targeted tests to verify red state**

Run: `pytest tests/unit/test_disk_cleanup.py -q`
Expected: restore tests fail

- [ ] **Step 3: Implement restore helper APIs and shell entrypoint**

Script requirements:

- `--dry-run`
- `--run-id <id>`
- `--item-id <id>`
- `--all`
- `--force` only for explicit overwrite behavior

Implementation note:

- if shell-only logic becomes brittle for manifest-safe parsing, keep shell as wrapper and call a Python entrypoint/helper for path-critical operations

- [ ] **Step 4: Run targeted tests and shell lint**

Run: `pytest tests/unit/test_disk_cleanup.py -q`
Expected: restore tests pass

Run: `shellcheck scripts/restore_disk_cleanup.sh`
Expected: no issues

## Chunk 6: ResourceMonitor Integration

### Task 6: Wire cleanup engine into disk threshold actions

**Files:**
- Modify: `src/xnetvn_monitord/monitors/resource_monitor.py`
- Modify: `tests/unit/test_resource_monitor.py`

- [ ] **Step 1: Write the failing orchestration tests**

Add tests for:

```python
def test_should_notify_only_when_disk_action_is_notify():
    ...

def test_should_run_cleanup_only_when_disk_action_is_cleanup():
    ...

def test_should_run_cleanup_then_service_recovery_when_disk_action_is_both():
    ...

def test_should_append_cleanup_action_results():
    ...

def test_should_respect_low_disk_cooldown_for_cleanup_and_recovery():
    ...
```

- [ ] **Step 2: Run focused tests to verify red state**

Run: `pytest tests/unit/test_resource_monitor.py -q`
Expected: orchestration tests fail

- [ ] **Step 3: Implement minimal integration**

Implementation requirements:

- read `disk.action_on_threshold`
- call cleanup engine for `cleanup` and `both`
- preserve threshold event behavior
- preserve service recovery path for `both`
- return structured action results usable by the daemon notification layer

- [ ] **Step 4: Run focused tests to verify green state**

Run: `pytest tests/unit/test_resource_monitor.py -q`
Expected: all resource monitor tests pass

## Chunk 7: Sample Config And Documentation

### Task 7: Fully document the configuration and supported values

**Files:**
- Modify: `config/main.example.yaml`
- Modify: `docs/en/CONFIG.md`
- Modify: `docs/vi/CONFIG.md`

- [ ] **Step 1: Write or update tests if config parsing behavior changes**

If parsing helpers or defaults require tests, add/update:

```python
def test_should_accept_cleanup_config_defaults():
    ...
```

- [ ] **Step 2: Update the example config with exhaustive English comments**

Requirements:

- document every new cleanup parameter
- list every supported enum value inline
- explain selector schema and examples for `exact`, `regex`, `glob`
- explain quarantine, restore, retention, dry-run, and safety behavior

- [ ] **Step 3: Update English and Vietnamese docs**

Requirements:

- document actual implemented behavior only
- keep `docs/vi` aligned in meaning with `docs/en`
- document restore script usage and operator safety expectations

- [ ] **Step 4: Run relevant tests and spot-check docs accuracy**

Run: `pytest tests/unit/test_config_loader.py -q`
Expected: config-related tests pass

## Chunk 8: Full Verification

### Task 8: Run final verification before requesting implementation approval

**Files:**
- Modify: none expected unless verification reveals gaps

- [ ] **Step 1: Run targeted unit tests for cleanup and resource monitor**

Run: `pytest tests/unit/test_disk_cleanup.py tests/unit/test_resource_monitor.py -q`
Expected: all tests pass

- [ ] **Step 2: Run config-related tests**

Run: `pytest tests/unit/test_config_loader.py -q`
Expected: pass

- [ ] **Step 3: Run formatting and lint checks for touched Python files**

Run: `python -m black --check src tests`
Expected: pass

Run: `python -m isort --check-only src tests`
Expected: pass

Run: `python -m flake8 src tests`
Expected: pass

- [ ] **Step 4: Run typing check for touched Python modules**

Run: `python -m mypy --install-types --non-interactive src`
Expected: no new errors introduced by cleanup feature

- [ ] **Step 5: Run shell lint for the restore script**

Run: `shellcheck scripts/restore_disk_cleanup.sh`
Expected: pass

- [ ] **Step 6: Review requirements coverage manually**

Checklist:

- all selector types implemented
- exclude patterns implemented
- Ubuntu/system critical paths protected
- low-resource scan strategy enforced
- quarantine-first behavior enforced
- restore scripts available
- sample config fully documented in English
- docs synchronized

## Notes For Execution

- Do not create a feature branch or worktree until the user approves this plan.
- Do not implement direct-delete behavior outside quarantine.
- If restore metadata format becomes complex, prefer a small Python helper over brittle shell parsing.
- If runtime impact during tests exposes unacceptable cost, tighten bounds rather than broadening behavior.