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
DRY_RUN=false
# When DRY_RUN=true we skip destructive/system operations for safe testing

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
    if [ "$DRY_RUN" = true ]; then
        log_info "Dry-run: skipping root privilege check"
        return 0
    fi

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
                if [ "$#" -lt 2 ]; then
                    log_error "Missing value for --install-dir"
                    usage
                    exit 1
                fi
                INSTALL_DIR="$2"
                shift 2
                ;;
            --install-dir=*)
                INSTALL_DIR="${1#*=}"
                shift
                ;;
            --service-name)
                if [ "$#" -lt 2 ]; then
                    log_error "Missing value for --service-name"
                    usage
                    exit 1
                fi
                SERVICE_NAME="$2"
                shift 2
                ;;
            --service-name=*)
                SERVICE_NAME="${1#*=}"
                shift
                ;;
            --yes)
                ASSUME_YES=true
                shift
                ;;
            --quiet)
                QUIET=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                ASSUME_YES=true
                shift
                ;;
            --dry-run=*)
                DRY_RUN=true
                ASSUME_YES=true
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
    python3 - "$INSTALL_DIR/xnetvn_monitord/__init__.py" <<'PY'
import re
import sys

path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as handle:
    data = handle.read()
match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", data)
if not match:
    sys.exit(2)
print(match.group(1))
PY
}

get_latest_release() {
    python3 - <<'PY'
import contextlib
import json
import os
import re
import socket
import sys
import traceback
import urllib.request

def is_env_true(name: str) -> bool:
    value = os.environ.get(name, '').strip().lower()
    return value in {'1', 'true', 'yes', 'y', 'on'}

@contextlib.contextmanager
def force_ipv4(enabled: bool):
    if not enabled:
        yield
        return
    original_getaddrinfo = socket.getaddrinfo

    def ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        results = original_getaddrinfo(host, port, family, type, proto, flags)
        return [info for info in results if info[0] == socket.AF_INET]

    socket.getaddrinfo = ipv4_only_getaddrinfo
    try:
        yield
    finally:
        socket.getaddrinfo = original_getaddrinfo

def open_url(url: str, headers: dict, force_ipv4_enabled: bool):
    req = urllib.request.Request(url, headers=headers)
    with force_ipv4(force_ipv4_enabled):
        return urllib.request.urlopen(req, timeout=15)

def request_json(url: str, headers: dict, force_ipv4_enabled: bool):
    with open_url(url, headers, force_ipv4_enabled) as response:
        data = json.loads(response.read().decode('utf-8'))
        return data

repo = os.environ.get('XNETVN_MONITORD_GITHUB_REPO', 'xnetvn-com/xnetvn_monitord')
api_base = os.environ.get('XNETVN_MONITORD_GITHUB_API_BASE_URL', 'https://api.github.com')
headers = {
    'Accept': 'application/vnd.github+json',
    'User-Agent': 'xnetvn_monitord-update-script'
}
if os.environ.get('GITHUB_TOKEN'):
    headers['Authorization'] = f"Bearer {os.environ['GITHUB_TOKEN']}"

force_ipv4_enabled = is_env_true('XNETVN_MONITORD_FORCE_IPV4') or is_env_true('XNETVN_MONITORD_ONLY_IPV4')

tag_name = ''
tarball_url = ''
html_url = ''
api_url = f"{api_base}/repos/{repo}/releases/latest"

try:
    data = request_json(api_url, headers, False)
except Exception as e:
    print(f"DEBUG: API request failed: {e!r}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    api_exc = e
    data = None

if not data and force_ipv4_enabled:
    try:
        data = request_json(api_url, headers, True)
    except Exception as e:
        print(f"DEBUG: API request (IPv4) failed: {e!r}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        api_ipv4_exc = e
        data = None

if isinstance(data, dict):
    tag_name = str(data.get('tag_name', '')).strip()
    tarball_url = str(data.get('tarball_url', '')).strip()
    html_url = str(data.get('html_url', '')).strip()

if not tag_name or not tarball_url:
    latest_url = f"https://github.com/{repo}/releases/latest"
    try:
        with open_url(latest_url, headers, False) as response:
            final_url = response.geturl()
    except Exception as e:
        print(f"DEBUG: HTML redirect check failed: {e!r}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        redirect_exc = e
        final_url = ''

    if not final_url and force_ipv4_enabled:
        try:
            with open_url(latest_url, headers, True) as response:
                final_url = response.geturl()
        except Exception as e:
            print(f"DEBUG: HTML redirect (IPv4) check failed: {e!r}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            redirect_ipv4_exc = e
            final_url = ''

    if final_url:
        match = re.search(r"/tag/([^/?#]+)", final_url)
        if match:
            tag_name = match.group(1)
            html_url = final_url
            tarball_url = f"https://github.com/{repo}/archive/refs/tags/{tag_name}.tar.gz"

if not tag_name or not tarball_url:
    # Print consolidated debug info to help triage failures
    sys.stderr.write(f"DEBUG: Failed to determine release tag/tarball. repo={repo} api_base={api_base} force_ipv4={force_ipv4_enabled}\n")
    if 'api_exc' in locals():
        print("DEBUG: api_exc:", repr(api_exc), file=sys.stderr)
        traceback.print_exception(type(api_exc), api_exc, api_exc.__traceback__, file=sys.stderr)
    if 'api_ipv4_exc' in locals():
        print("DEBUG: api_ipv4_exc:", repr(api_ipv4_exc), file=sys.stderr)
        traceback.print_exception(type(api_ipv4_exc), api_ipv4_exc, api_ipv4_exc.__traceback__, file=sys.stderr)
    if 'redirect_exc' in locals():
        print("DEBUG: redirect_exc:", repr(redirect_exc), file=sys.stderr)
        traceback.print_exception(type(redirect_exc), redirect_exc, redirect_exc.__traceback__, file=sys.stderr)
    if 'redirect_ipv4_exc' in locals():
        print("DEBUG: redirect_ipv4_exc:", repr(redirect_ipv4_exc), file=sys.stderr)
        traceback.print_exception(type(redirect_ipv4_exc), redirect_ipv4_exc, redirect_ipv4_exc.__traceback__, file=sys.stderr)
    sys.exit(1)

print(tag_name)
print(tarball_url)
print(html_url)
PY
}

compare_versions() {
    python3 - "$1" "$2" <<'PY'
import re
import sys

pattern = re.compile(
    r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$"
)

def parse(version: str):
    match = pattern.match(version.strip())
    if not match:
        return None
    major, minor, patch, prerelease, _build = match.groups()
    pre_parts = prerelease.split('.') if prerelease else []
    return int(major), int(minor), int(patch), pre_parts

def compare_prerelease(left, right):
    for left_part, right_part in zip(left, right):
        left_is_num = left_part.isdigit()
        right_is_num = right_part.isdigit()

        if left_is_num and right_is_num:
            left_val = int(left_part)
            right_val = int(right_part)
            if left_val != right_val:
                return -1 if left_val < right_val else 1
        elif left_is_num != right_is_num:
            return -1 if left_is_num else 1
        else:
            if left_part != right_part:
                return -1 if left_part < right_part else 1

    if len(left) != len(right):
        return -1 if len(left) < len(right) else 1
    return 0

def compare_versions(current: str, latest: str):
    current_parsed = parse(current)
    latest_parsed = parse(latest)
    if not current_parsed or not latest_parsed:
        return None

    current_core = current_parsed[:3]
    latest_core = latest_parsed[:3]
    if current_core != latest_core:
        return -1 if current_core < latest_core else 1

    current_pre = current_parsed[3]
    latest_pre = latest_parsed[3]
    if not current_pre and not latest_pre:
        return 0
    if not current_pre:
        return 1
    if not latest_pre:
        return -1
    return compare_prerelease(current_pre, latest_pre)

result = compare_versions(sys.argv[1], sys.argv[2])
print('none' if result is None else result)
PY
}

prompt_confirmation() {
    if [ "$ASSUME_YES" = true ] || [ "$DRY_RUN" = true ]; then
        log_info "Proceeding automatically (assume-yes or dry-run enabled)"
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
    local backup_dir
    backup_dir="$INSTALL_DIR/.local/backups/update_$(date +%Y%m%d_%H%M%S)"
    if [ "$DRY_RUN" = true ]; then
        log_info "Dry-run: would create backup directory: $backup_dir"
        if [ -d "$INSTALL_DIR/xnetvn_monitord" ]; then
            log_info "Dry-run: would copy $INSTALL_DIR/xnetvn_monitord to $backup_dir"
        else
            log_info "Dry-run: no existing installation found to backup"
        fi
        return 0
    fi

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
    # Only remove temp_dir if it is set and exists; avoid calling `rm -rf ''` or removing unexpected paths
    trap 'if [ -n "${temp_dir-}" ] && [ -d "${temp_dir}" ]; then rm -rf -- "${temp_dir}"; fi' RETURN

    if [ "$DRY_RUN" = true ]; then
        log_info "Dry-run: would download release tarball from: $tarball_url"
        log_info "Dry-run: would extract tarball and copy new files into $INSTALL_DIR"
        return 0
    fi

    log_info "Downloading release tarball..."
    python3 - "$tarball_url" "$temp_dir/release.tar.gz" <<'PY'
import contextlib
import os
import socket
import sys
import urllib.request

def is_env_true(name: str) -> bool:
    value = os.environ.get(name, '').strip().lower()
    return value in {'1', 'true', 'yes', 'y', 'on'}

@contextlib.contextmanager
def force_ipv4(enabled: bool):
    if not enabled:
        yield
        return
    original_getaddrinfo = socket.getaddrinfo

    def ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        results = original_getaddrinfo(host, port, family, type, proto, flags)
        return [info for info in results if info[0] == socket.AF_INET]

    socket.getaddrinfo = ipv4_only_getaddrinfo
    try:
        yield
    finally:
        socket.getaddrinfo = original_getaddrinfo

def build_headers() -> dict:
    headers = {
        'User-Agent': 'xnetvn_monitord-update-script'
    }
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = f"Bearer {token}"
    return headers

def download(url: str, dest: str, force_ipv4_enabled: bool) -> None:
    request = urllib.request.Request(url, headers=build_headers())
    with force_ipv4(force_ipv4_enabled):
        with urllib.request.urlopen(request, timeout=30) as response:
            with open(dest, 'wb') as handle:
                handle.write(response.read())

url = sys.argv[1]
dest = sys.argv[2]
force_ipv4_enabled = is_env_true('XNETVN_MONITORD_FORCE_IPV4') or is_env_true('XNETVN_MONITORD_ONLY_IPV4')

try:
    download(url, dest, False)
except Exception:
    if not force_ipv4_enabled:
        download(url, dest, True)
    else:
        raise
PY

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

    if [ -f "$release_root/scripts/update.sh" ]; then
        mkdir -p "$INSTALL_DIR/scripts"
        cp -a "$release_root/scripts/update.sh" "$INSTALL_DIR/scripts/update.sh"
        chmod 755 "$INSTALL_DIR/scripts/update.sh"
    fi

    mkdir -p "$CONFIG_DIR"

    if [ -d "$release_root/config" ]; then
        if [ -f "$release_root/config/main.example.yaml" ]; then
            cp -a "$release_root/config/main.example.yaml" "$CONFIG_DIR/main.example.yaml"
        fi
        if [ -f "$release_root/config/.env.example" ]; then
            cp -a "$release_root/config/.env.example" "$CONFIG_DIR/.env.example"
        fi
    fi

}

main() {
    parse_args "$@"
    check_root
    check_dependencies

    if [ ! -d "$INSTALL_DIR" ] && [ "$DRY_RUN" != true ]; then
        log_error "Install directory not found: $INSTALL_DIR"
        exit 1
    elif [ ! -d "$INSTALL_DIR" ] && [ "$DRY_RUN" = true ]; then
        log_info "Dry-run: install directory does not need to exist: $INSTALL_DIR"
    fi

    if [ ! -f "$INSTALL_DIR/xnetvn_monitord/__init__.py" ] && [ "$DRY_RUN" != true ]; then
        log_error "xnetvn_monitord package not found in $INSTALL_DIR"
        exit 1
    elif [ ! -f "$INSTALL_DIR/xnetvn_monitord/__init__.py" ] && [ "$DRY_RUN" = true ]; then
        log_info "Dry-run: package file not required for dry-run"
    fi

    local current_version
    current_version="$(get_current_version || true)"
    if [ -z "$current_version" ]; then
        if [ "$DRY_RUN" = true ]; then
            log_info "Dry-run: current version not found; proceeding with simulation"
            current_version="(none)"
        else
            log_error "Unable to determine current version from $INSTALL_DIR/xnetvn_monitord/__init__.py"
            exit 1
        fi
    fi

    local latest_version
    local tarball_url
    local release_url
    local release_info

    # Allow tests to inject release info to avoid network calls and fragile in-file replacements.
    # The environment variable should contain three newline-separated values: tag_name, tarball_url, html_url
    if [ -n "${XNETVN_MONITORD_TEST_LATEST_RELEASE-}" ]; then
        readarray -t __release_lines <<< "$XNETVN_MONITORD_TEST_LATEST_RELEASE"
        latest_version="${__release_lines[0]:-}"
        tarball_url="${__release_lines[1]:-}"
        release_url="${__release_lines[2]:-}"
    else
        release_info="$(get_latest_release || true)"

        # Safely split release_info into lines
        readarray -t __release_lines <<< "$release_info"
        latest_version="${__release_lines[0]:-}"
        tarball_url="${__release_lines[1]:-}"
        release_url="${__release_lines[2]:-}"
    fi

    if [ -z "$latest_version" ] || [ -z "$tarball_url" ]; then
        log_error "Unable to fetch latest release metadata"
        log_error "Debug output from get_latest_release:"
        echo "$release_info" >&2
        exit 1
    fi

    local comparison
    comparison="$(compare_versions "$current_version" "$latest_version")"

    if [ "$comparison" = "none" ]; then
        if [ "$DRY_RUN" = true ] && [ "$current_version" = "(none)" ]; then
            log_info "Dry-run: treating missing current version as outdated for simulation"
            comparison=-1
        else
            log_error "Unable to compare versions: $current_version vs $latest_version"
            exit 1
        fi
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
    if [ -f "$INSTALL_DIR/scripts/update.sh" ]; then
        log_info "Update script refreshed: $INSTALL_DIR/scripts/update.sh"
    fi
    log_info "Restart the service to load the new version: systemctl restart $SERVICE_NAME"
}

main "$@"
