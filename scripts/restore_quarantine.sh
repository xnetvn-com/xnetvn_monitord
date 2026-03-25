#!/usr/bin/env bash

# Copyright 2026 xNetVN Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -euo pipefail
IFS=$'\n\t'

INSTALL_DIR_DEFAULT="/opt/xnetvn_monitord"
INSTALL_DIR="${XNETVN_MONITORD_HOME:-$INSTALL_DIR_DEFAULT}"
QUARANTINE_DIR="${INSTALL_DIR}/.local/quarantine"
MANIFEST_PATH=""
DRY_RUN=false

usage() {
    cat <<'USAGE'
Usage: scripts/restore_quarantine.sh [options]

Options:
  --install-dir PATH     Override install directory (default: /opt/xnetvn_monitord)
  --quarantine-dir PATH  Override quarantine directory
  --manifest PATH        Restore only one manifest instead of all manifests
  --dry-run              Report restore targets without moving files
  --help                 Show this help
USAGE
}

log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
}

parse_args() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --install-dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            --install-dir=*)
                INSTALL_DIR="${1#*=}"
                shift
                ;;
            --quarantine-dir)
                QUARANTINE_DIR="$2"
                shift 2
                ;;
            --quarantine-dir=*)
                QUARANTINE_DIR="${1#*=}"
                shift
                ;;
            --manifest)
                MANIFEST_PATH="$2"
                shift 2
                ;;
            --manifest=*)
                MANIFEST_PATH="${1#*=}"
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                log_error "Unknown argument: $1"
                usage
                exit 1
                ;;
        esac
    done
}

parse_args "$@"

if ! command -v python3 >/dev/null 2>&1; then
    log_error "python3 is required"
    exit 1
fi

if [ ! -d "$INSTALL_DIR" ]; then
    log_error "Install directory not found: $INSTALL_DIR"
    exit 1
fi

if [ ! -d "$INSTALL_DIR/xnetvn_monitord" ]; then
    log_error "Installed Python package not found: $INSTALL_DIR/xnetvn_monitord"
    exit 1
fi

if [ -n "$MANIFEST_PATH" ] && [ ! -f "$MANIFEST_PATH" ]; then
    log_error "Manifest file not found: $MANIFEST_PATH"
    exit 1
fi

if [ -z "$MANIFEST_PATH" ] && [ ! -d "$QUARANTINE_DIR" ]; then
    log_error "Quarantine directory not found: $QUARANTINE_DIR"
    exit 1
fi

PYTHONPATH="$INSTALL_DIR${PYTHONPATH:+:$PYTHONPATH}" \
XNETVN_MONITORD_QUARANTINE_DIR="$QUARANTINE_DIR" \
XNETVN_MONITORD_MANIFEST_PATH="$MANIFEST_PATH" \
XNETVN_MONITORD_DRY_RUN="$DRY_RUN" \
python3 - <<'PY'
import json
import os

from xnetvn_monitord.monitors.disk_cleanup import restore_quarantine_directory
from xnetvn_monitord.monitors.disk_cleanup import restore_quarantine_manifest


def main() -> int:
    quarantine_dir = os.environ["XNETVN_MONITORD_QUARANTINE_DIR"]
    manifest_path = os.environ.get("XNETVN_MONITORD_MANIFEST_PATH", "")
    dry_run = os.environ.get("XNETVN_MONITORD_DRY_RUN", "false").lower() == "true"

    if manifest_path:
        result = restore_quarantine_manifest(manifest_path, dry_run=dry_run)
    else:
        result = restore_quarantine_directory(quarantine_dir, dry_run=dry_run)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not result.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
PY
