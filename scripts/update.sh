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
CONFIG_DIR="$INSTALL_DIR/config"
SERVICE_NAME="xnetvn_monitord"
QUIET=false
ASSUME_YES=false

log_info() {
    if [ "$QUIET" = false ]; then
        echo "[INFO] $1"
    fi
}

log_warning() {
    if [ "$QUIET" = false ]; then
        echo "[WARN] $1" >&2
    fi
}

log_error() {
    echo "[ERROR] $1" >&2
}

usage() {
    cat <<'USAGE'
Usage: scripts/update.sh [options]

Options:
  --install-dir PATH   Override install directory (default: /opt/xnetvn_monitord)
  --service-name NAME  Override systemd service name (default: xnetvn_monitord)
  --yes                Skip confirmation prompt
  --quiet              Suppress non-error output
  --help               Show this help
USAGE
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

check_dependencies() {
    if ! command -v python3 >/dev/null 2>&1; then
        log_error "python3 is required"
        exit 1
    fi
    if ! command -v tar >/dev/null 2>&1; then
        log_error "tar is required"
        exit 1
    fi
}

parse_args() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --install-dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            --service-name)
                SERVICE_NAME="$2"
                shift 2
                ;;
            --yes)
                ASSUME_YES=true
                shift
                ;;
            --quiet)
                QUIET=true
                shift
                ;;
            --help)
                usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
}

get_current_version() {
    python3 -c "import importlib.util; spec=importlib.util.spec_from_file_location('xnetvn_monitord', '${INSTALL_DIR}/xnetvn_monitord/__init__.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); print(mod.__version__)"
}

get_latest_release() {
    python3 -c """
import json
import os
import urllib.request

url = 'https://api.github.com/repos/xnetvn-com/xnetvn_monitord/releases/latest'
headers = {
    'Accept': 'application/vnd.github+json',
    'User-Agent': 'xnetvn_monitord-update-script'
}
if os.environ.get('GITHUB_TOKEN'):
    headers['Authorization'] = f"Bearer {os.environ['GITHUB_TOKEN']}"
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=15) as response:
    data = json.loads(response.read().decode('utf-8'))
print(data.get('tag_name', '').strip())
print(data.get('tarball_url', '').strip())
print(data.get('html_url', '').strip())
"""
}

compare_versions() {
    python3 -c """
import importlib.util
import sys

spec = importlib.util.spec_from_file_location('update_checker', '${INSTALL_DIR}/xnetvn_monitord/utils/update_checker.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = module.compare_versions(sys.argv[1], sys.argv[2])
print('none' if result is None else result)
""" "$1" "$2"
}

prompt_confirmation() {
    if [ "$ASSUME_YES" = true ]; then
        return 0
    fi

    echo "Proceed with update? [y/N]" >&2
    read -r answer
    case "$answer" in
        y|Y|yes|YES)
            return 0
            ;;
        *)
            log_warning "Update cancelled"
            return 1
            ;;
    esac
}

perform_backup() {
    local backup_dir="$INSTALL_DIR/.local/backups/update_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    if [ -d "$INSTALL_DIR/xnetvn_monitord" ]; then
        cp -a "$INSTALL_DIR/xnetvn_monitord" "$backup_dir/"
    fi
    log_info "Backup created at $backup_dir"
}

apply_update() {
    local tarball_url="$1"
    local temp_dir
    temp_dir="$(mktemp -d)"

    log_info "Downloading release tarball..."
    python3 -c """
import urllib.request
import sys
urllib.request.urlretrieve(sys.argv[1], sys.argv[2])
""" "$tarball_url" "$temp_dir/release.tar.gz"

    log_info "Extracting release tarball..."
    tar -xzf "$temp_dir/release.tar.gz" -C "$temp_dir"

    local release_root
    release_root="$(find "$temp_dir" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
    if [ -z "$release_root" ]; then
        log_error "No release directory found in tarball"
        return 1
    fi

    local source_dir="$release_root/src/xnetvn_monitord"
    if [ ! -d "$source_dir" ]; then
        log_error "Release source directory not found: $source_dir"
        return 1
    fi

    rm -rf "$INSTALL_DIR/xnetvn_monitord"
    cp -a "$source_dir" "$INSTALL_DIR/"

    mkdir -p "$CONFIG_DIR"

    if [ -d "$release_root/config" ]; then
        if [ -f "$release_root/config/main.example.yaml" ]; then
            cp -a "$release_root/config/main.example.yaml" "$CONFIG_DIR/main.example.yaml"
        fi
        if [ -f "$release_root/config/.env.example" ]; then
            cp -a "$release_root/config/.env.example" "$CONFIG_DIR/.env.example"
        fi
    fi

    rm -rf "$temp_dir"
}

main() {
    parse_args "$@"
    check_root
    check_dependencies

    if [ ! -d "$INSTALL_DIR" ]; then
        log_error "Install directory not found: $INSTALL_DIR"
        exit 1
    fi

    if [ ! -f "$INSTALL_DIR/xnetvn_monitord/__init__.py" ]; then
        log_error "xnetvn_monitord package not found in $INSTALL_DIR"
        exit 1
    fi

    local current_version
    current_version="$(get_current_version)"

    local latest_version
    local tarball_url
    local release_url
    local release_info

    release_info="$(get_latest_release)"
    IFS=$'\n' read -r latest_version tarball_url release_url <<< "$release_info"

    if [ -z "$latest_version" ] || [ -z "$tarball_url" ]; then
        log_error "Unable to fetch latest release metadata"
        exit 1
    fi

    local comparison
    comparison="$(compare_versions "$current_version" "$latest_version")"

    if [ "$comparison" = "none" ]; then
        log_error "Unable to compare versions: $current_version vs $latest_version"
        exit 1
    fi

    if [ "$comparison" -ge 0 ]; then
        log_info "Already on latest version ($current_version)"
        exit 0
    fi

    log_info "Current version: $current_version"
    log_info "Latest version:  $latest_version"
    log_info "Release URL:     $release_url"

    if ! prompt_confirmation; then
        exit 1
    fi

    perform_backup
    apply_update "$tarball_url"

    log_info "Update applied successfully"
    log_info "Restart the service to load the new version: systemctl restart $SERVICE_NAME"
}

main "$@"
