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

# xNetVN Monitor Daemon - Installation Script
# By default, this script installs from the current local source directory.
# Use --releases=latest or --releases=vX.Y.Z to install from GitHub releases:
# https://github.com/xnetvn-com/xnetvn_monitord/releases

set -euo pipefail
IFS=$'\n\t'

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/xnetvn_monitord"
CONFIG_DIR="$INSTALL_DIR/config"
LOG_DIR="/var/log/xnetvn_monitord"
SYSTEMD_SERVICE="/etc/systemd/system/xnetvn_monitord.service"
VENV_DIR="$INSTALL_DIR/.venv"
INSTALL_SOURCE="local"
RELEASE_VERSION=""
DRY_RUN=false
# When DRY_RUN=true we skip destructive/system operations for safe testing

# Internal state
RELEASE_DIR=""
RELEASE_TAG=""
SOURCE_DIR=""
_TEMP_DIR=""

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

usage() {
    cat <<'USAGE'
Usage: scripts/install.sh [options]

Options:
  --releases VALUE     Install from GitHub releases (`latest` or `vX.Y.Z`)
  --install-dir PATH   Override install directory (default: /opt/xnetvn_monitord)
  --dry-run            Simulate installation without making changes
  --help               Show this help
USAGE
}

validate_release_selector() {
    local selector="$1"

    if [ "$selector" = "latest" ]; then
        return 0
    fi

    if [[ "$selector" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        return 0
    fi

    log_error "Invalid value for --releases: $selector"
    log_error "Expected 'latest' or a tag in the form vX.Y.Z"
    exit 1
}

parse_args() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --releases)
                if [ "$#" -lt 2 ]; then
                    log_error "Missing value for --releases"
                    usage
                    exit 1
                fi
                INSTALL_SOURCE="release"
                validate_release_selector "$2"
                if [ "$2" = "latest" ]; then
                    RELEASE_VERSION=""
                else
                    RELEASE_VERSION="$2"
                fi
                shift 2
                ;;
            --releases=*)
                INSTALL_SOURCE="release"
                validate_release_selector "${1#*=}"
                if [ "${1#*=}" = "latest" ]; then
                    RELEASE_VERSION=""
                else
                    RELEASE_VERSION="${1#*=}"
                fi
                shift
                ;;
            --install-dir)
                if [ "$#" -lt 2 ]; then
                    log_error "Missing value for --install-dir"
                    usage
                    exit 1
                fi
                INSTALL_DIR="$2"
                CONFIG_DIR="$INSTALL_DIR/config"
                VENV_DIR="$INSTALL_DIR/.venv"
                shift 2
                ;;
            --install-dir=*)
                INSTALL_DIR="${1#*=}"
                CONFIG_DIR="$INSTALL_DIR/config"
                VENV_DIR="$INSTALL_DIR/.venv"
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --dry-run=*)
                DRY_RUN=true
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

resolve_local_source_dir() {
    SOURCE_DIR="$(pwd -P)"

    local required_paths=(
        "$SOURCE_DIR/src/xnetvn_monitord"
        "$SOURCE_DIR/config"
        "$SOURCE_DIR/scripts/update.sh"
        "$SOURCE_DIR/systemd/xnetvn_monitord.service"
    )

    local missing_paths=()
    local path
    for path in "${required_paths[@]}"; do
        if [ ! -e "$path" ]; then
            missing_paths+=("$path")
        fi
    done

    if [ ${#missing_paths[@]} -gt 0 ]; then
        log_error "Current directory does not look like a valid xnetvn_monitord source tree: $SOURCE_DIR"
        for path in "${missing_paths[@]}"; do
            log_error "Missing required path: $path"
        done
        log_error "Run the installer from the repository root, or use --releases=latest / --releases=vX.Y.Z"
        exit 1
    fi

    RELEASE_TAG="local"
}

check_root() {
    if [ "$DRY_RUN" = true ]; then
        log_info "Dry-run: skipping root privilege check"
        return 0
    fi

    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

check_dependencies() {
    log_info "Checking dependencies..."

    local missing_deps=()

    # Check Python 3
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    fi

    # Check pip
    if ! command -v pip3 &> /dev/null; then
        missing_deps+=("python3-pip")
    fi

    # Check venv/ensurepip (ensurepip is provided by python3-venv on Debian/Ubuntu)
    if ! python3 -m venv --help &> /dev/null; then
        missing_deps+=("python3-venv")
    fi

    if ! python3 -c "import ensurepip" &> /dev/null; then
        missing_deps+=("python3-venv")
    fi

    if ! command -v tar &> /dev/null; then
        missing_deps+=("tar")
    fi

    if [ ${#missing_deps[@]} -gt 0 ]; then
        if [ "$DRY_RUN" = true ]; then
            log_warning "Dry-run: missing dependencies (would install): ${missing_deps[*]}"
        else
            log_warning "Missing dependencies: ${missing_deps[*]}"
            log_info "Installing dependencies..."
            apt-get update
            apt-get install -y "${missing_deps[@]}"
        fi
    else
        log_info "All dependencies are satisfied"
    fi
}

# Fetches release metadata (tag_name, tarball_url, html_url) from GitHub.
# If RELEASE_VERSION is set, fetches that specific tag; otherwise fetches the latest release.
# Prints three lines: tag_name, tarball_url, html_url
get_release_info() {
    python3 - "$RELEASE_VERSION" <<'PY'
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

requested_version = sys.argv[1] if len(sys.argv) > 1 else ''
repo = os.environ.get('XNETVN_MONITORD_GITHUB_REPO', 'xnetvn-com/xnetvn_monitord')
api_base = os.environ.get('XNETVN_MONITORD_GITHUB_API_BASE_URL', 'https://api.github.com')
headers = {
    'Accept': 'application/vnd.github+json',
    'User-Agent': 'xnetvn_monitord-install-script'
}
if os.environ.get('GITHUB_TOKEN'):
    headers['Authorization'] = f"Bearer {os.environ['GITHUB_TOKEN']}"

force_ipv4_enabled = is_env_true('XNETVN_MONITORD_FORCE_IPV4') or is_env_true('XNETVN_MONITORD_ONLY_IPV4')

tag_name = ''
tarball_url = ''
html_url = ''

if requested_version:
    # Fetch a specific release by tag
    tag = requested_version if requested_version.startswith('v') else f"v{requested_version}"
    api_url = f"{api_base}/repos/{repo}/releases/tags/{tag}"
else:
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
    if not requested_version:
        # Fall back to HTML redirect for latest release
        latest_url = f"https://github.com/{repo}/releases/latest"
        try:
            with open_url(latest_url, headers, False) as response:
                final_url = response.geturl()
        except Exception as e:
            print(f"DEBUG: HTML redirect check failed: {e!r}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            api_exc = e
            final_url = ''

        if not final_url and force_ipv4_enabled:
            try:
                with open_url(latest_url, headers, True) as response:
                    final_url = response.geturl()
            except Exception as e:
                print(f"DEBUG: HTML redirect (IPv4) check failed: {e!r}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                api_ipv4_exc = e
                final_url = ''

        if final_url:
            match = re.search(r"/tag/([^/?#]+)", final_url)
            if match:
                tag_name = match.group(1)
                html_url = final_url
                tarball_url = f"https://github.com/{repo}/archive/refs/tags/{tag_name}.tar.gz"

if not tag_name or not tarball_url:
    sys.stderr.write(
        f"DEBUG: Failed to determine release tag/tarball. repo={repo} api_base={api_base} "
        f"requested_version={requested_version!r} force_ipv4={force_ipv4_enabled}\n"
    )
    if 'api_exc' in locals():
        print("DEBUG: api_exc:", repr(api_exc), file=sys.stderr)
        traceback.print_exception(type(api_exc), api_exc, api_exc.__traceback__, file=sys.stderr)
    if 'api_ipv4_exc' in locals():
        print("DEBUG: api_ipv4_exc:", repr(api_ipv4_exc), file=sys.stderr)
        traceback.print_exception(type(api_ipv4_exc), api_ipv4_exc, api_ipv4_exc.__traceback__, file=sys.stderr)
    sys.exit(1)

print(tag_name)
print(tarball_url)
print(html_url)
PY
}

# Downloads the release tarball and extracts it; sets RELEASE_DIR to the extracted root.
download_release() {
    local tarball_url="$1"

    _TEMP_DIR="$(mktemp -d)"
    # Cleanup temp dir on exit
    trap 'if [ -n "${_TEMP_DIR-}" ] && [ -d "${_TEMP_DIR}" ]; then rm -rf -- "${_TEMP_DIR}"; fi' EXIT

    if [ "$DRY_RUN" = true ]; then
        log_info "Dry-run: would download release tarball from: $tarball_url"
        log_info "Dry-run: would extract tarball to temp directory"
        RELEASE_DIR="$_TEMP_DIR/dry-run-release"
        return 0
    fi

    log_info "Downloading release tarball from: $tarball_url"
    python3 - "$tarball_url" "$_TEMP_DIR/release.tar.gz" <<'PY'
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
        'User-Agent': 'xnetvn_monitord-install-script'
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
    download(url, dest, force_ipv4_enabled)
except Exception:
    if not force_ipv4_enabled:
        download(url, dest, True)
    else:
        raise
PY

    log_info "Extracting release tarball..."
    tar -xzf "$_TEMP_DIR/release.tar.gz" -C "$_TEMP_DIR"

    RELEASE_DIR="$(find "$_TEMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
    if [ -z "$RELEASE_DIR" ]; then
        log_error "No release directory found in tarball"
        exit 1
    fi
    log_info "Release extracted to: $RELEASE_DIR"
}

install_python_packages() {
    log_info "Installing Python packages..."

    local venv_python="$VENV_DIR/bin/python"
    local venv_pip="$VENV_DIR/bin/pip"

    if [ "$DRY_RUN" = true ]; then
        log_info "Dry-run: would create/use virtual environment at $VENV_DIR"
        log_info "Dry-run: would install Python packages from $SOURCE_DIR/requirements.txt"
        return 0
    fi

    if [ ! -d "$VENV_DIR" ]; then
        if ! python3 -m venv "$VENV_DIR"; then
            log_warning "Failed to create virtual environment. Installing python3-venv and retrying..."
            apt-get update
            apt-get install -y python3-venv
            python3 -m venv "$VENV_DIR"
        fi
        log_info "Created virtual environment at $VENV_DIR"
    else
        log_info "Using existing virtual environment at $VENV_DIR"
    fi

    if ! "$venv_python" -m pip --version &> /dev/null; then
        log_warning "pip is missing in the virtual environment. Bootstrapping with ensurepip..."
        if ! "$venv_python" -m ensurepip --upgrade &> /dev/null; then
            log_warning "ensurepip failed. Recreating virtual environment..."
            rm -rf "$VENV_DIR"
            python3 -m venv "$VENV_DIR"
        fi
    fi

    "$venv_python" -m pip install --upgrade pip

    if [ -n "$SOURCE_DIR" ] && [ -f "$SOURCE_DIR/requirements.txt" ]; then
        "$venv_pip" install -r "$SOURCE_DIR/requirements.txt"
    else
        log_warning "requirements.txt not found in source, falling back to core packages"
        "$venv_pip" install PyYAML psutil
    fi
}

create_directories() {
    log_info "Creating directories..."

    if [ "$DRY_RUN" = true ]; then
        log_info "Dry-run: would create directories under $INSTALL_DIR and $LOG_DIR"
        return 0
    fi

    mkdir -p "$INSTALL_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$INSTALL_DIR/scripts"
    mkdir -p "$LOG_DIR"
    mkdir -p "$INSTALL_DIR/.local"/{logs,reports,tmp}

    log_info "Directories created successfully"
}

copy_files() {
    log_info "Copying application files from source..."

    if [ "$DRY_RUN" = true ]; then
        if [ "$INSTALL_SOURCE" = "local" ]; then
            log_info "Dry-run: would use local source directory: $SOURCE_DIR"
            log_info "Dry-run: would copy source code, scripts, configs, and systemd service from local source"
        else
            log_info "Dry-run: would copy source code, scripts, configs, and systemd service from release $RELEASE_TAG"
        fi
        return 0
    fi

    # Copy source code from the selected source
    if [ -d "$SOURCE_DIR/src/xnetvn_monitord" ]; then
        cp -r "$SOURCE_DIR/src/xnetvn_monitord" "$INSTALL_DIR/"
        log_info "Source code copied from $RELEASE_TAG"
    else
        log_error "Source directory not found: $SOURCE_DIR/src/xnetvn_monitord"
        exit 1
    fi

    # Copy update script from the selected source
    if [ -f "$SOURCE_DIR/scripts/update.sh" ]; then
        mkdir -p "$INSTALL_DIR/scripts"
        cp "$SOURCE_DIR/scripts/update.sh" "$INSTALL_DIR/scripts/update.sh"
        cp "$SOURCE_DIR/scripts/restore_quarantine.sh" "$INSTALL_DIR/scripts/restore_quarantine.sh"
        chmod 755 "$INSTALL_DIR/scripts/update.sh"
        chmod 755 "$INSTALL_DIR/scripts/restore_quarantine.sh"
        log_info "Update script copied to $INSTALL_DIR/scripts/update.sh"
        log_info "Restore script copied to $INSTALL_DIR/scripts/restore_quarantine.sh"
    else
        log_warning "Update script not found in source"
    fi

    # Copy configuration (do not overwrite existing user config)
    mkdir -p "$CONFIG_DIR"
    if [ -f "$CONFIG_DIR/main.yaml" ]; then
        log_warning "Configuration file already exists: $CONFIG_DIR/main.yaml"
        log_warning "Skipping configuration copy to avoid overwriting user changes"
    elif [ -f "$SOURCE_DIR/config/main.example.yaml" ]; then
        cp "$SOURCE_DIR/config/main.example.yaml" "$CONFIG_DIR/main.yaml"
        log_warning "Using example configuration. Please edit $CONFIG_DIR/main.yaml"
    elif [ -f "$SOURCE_DIR/config/main.yaml" ]; then
        cp "$SOURCE_DIR/config/main.yaml" "$CONFIG_DIR/"
        log_info "Configuration file copied"
    else
        log_error "No configuration file found in source"
        exit 1
    fi

    if [ -f "$CONFIG_DIR/.env" ]; then
        log_warning "Environment file already exists: $CONFIG_DIR/.env"
        log_warning "Skipping environment copy to avoid overwriting user changes"
    elif [ -f "$SOURCE_DIR/config/.env.example" ]; then
        cp "$SOURCE_DIR/config/.env.example" "$CONFIG_DIR/.env"
        log_warning "Using example environment file. Please edit $CONFIG_DIR/.env"
    else
        log_warning "Environment example file not found in source"
    fi

    if [ -f "$SOURCE_DIR/config/main.example.yaml" ]; then
        cp "$SOURCE_DIR/config/main.example.yaml" "$CONFIG_DIR/main.example.yaml"
        log_info "Configuration example file refreshed"
    else
        log_warning "Configuration example file not found in source"
    fi

    if [ -f "$SOURCE_DIR/config/.env.example" ]; then
        cp "$SOURCE_DIR/config/.env.example" "$CONFIG_DIR/.env.example"
        log_info "Environment example file refreshed"
    else
        log_warning "Environment example file not found in source"
    fi

    # Copy systemd service from the selected source
    if [ -f "$SOURCE_DIR/systemd/xnetvn_monitord.service" ]; then
        if [ -f "$SYSTEMD_SERVICE" ]; then
            log_warning "Systemd service file already exists: $SYSTEMD_SERVICE"
            log_warning "Skipping service file copy to avoid overwriting changes"
        else
            cp "$SOURCE_DIR/systemd/xnetvn_monitord.service" "$SYSTEMD_SERVICE"
            log_info "Systemd service file copied"
        fi
    else
        log_error "Systemd service file not found in source"
        exit 1
    fi
}

set_permissions() {
    log_info "Setting permissions..."

    if [ "$DRY_RUN" = true ]; then
        log_info "Dry-run: would set permissions on $INSTALL_DIR, $LOG_DIR, $SYSTEMD_SERVICE"
        return 0
    fi

    chmod -R 755 "$INSTALL_DIR"
    if [ -f "$CONFIG_DIR/main.yaml" ]; then
        chmod 600 "$CONFIG_DIR/main.yaml"
    fi
    if [ -f "$CONFIG_DIR/.env" ]; then
        chmod 600 "$CONFIG_DIR/.env"
    fi
    chmod -R 755 "$LOG_DIR"
    chmod 644 "$SYSTEMD_SERVICE"

    log_info "Permissions set successfully"
}

configure_systemd() {
    log_info "Configuring systemd service..."

    if [ "$DRY_RUN" = true ]; then
        log_info "Dry-run: would run: systemctl daemon-reload && systemctl enable xnetvn_monitord.service"
        return 0
    fi

    systemctl daemon-reload
    systemctl enable xnetvn_monitord.service

    log_info "Systemd service configured and enabled"
}

show_completion_message() {
    echo ""
    log_info "=================================================="
    log_info "Installation completed successfully! ($RELEASE_TAG)"
    log_info "=================================================="
    echo ""
    log_info "Configuration file: $CONFIG_DIR/main.yaml"
    log_info "Environment example: $CONFIG_DIR/.env.example"
    log_info "Log directory: $LOG_DIR"
    echo ""
    log_warning "IMPORTANT: Please edit the configuration file before starting the service:"
    log_warning "  vi $CONFIG_DIR/main.yaml"
    echo ""
    log_info "To start the service:"
    log_info "  systemctl start xnetvn_monitord"
    echo ""
    log_info "To check service status:"
    log_info "  systemctl status xnetvn_monitord"
    echo ""
    log_info "To view logs:"
    log_info "  journalctl -u xnetvn_monitord -f"
    echo ""
}

# Main installation process
main() {
    parse_args "$@"

    log_info "Starting xNetVN Monitor Daemon installation..."
    if [ "$INSTALL_SOURCE" = "local" ]; then
        resolve_local_source_dir
        log_info "Source: local directory ($SOURCE_DIR)"
    else
        log_info "Source: https://github.com/xnetvn-com/xnetvn_monitord/releases"
    fi
    echo ""

    check_root
    check_dependencies

    if [ "$INSTALL_SOURCE" = "release" ]; then
        # Fetch release metadata from GitHub
        local release_info
        # Allow tests to inject release info via environment variable to avoid network calls
        # The variable should contain three newline-separated values: tag_name, tarball_url, html_url
        if [ -n "${XNETVN_MONITORD_TEST_LATEST_RELEASE-}" ]; then
            release_info="$XNETVN_MONITORD_TEST_LATEST_RELEASE"
        else
            release_info="$(get_release_info || true)"
        fi

        local release_lines
        readarray -t release_lines <<< "$release_info"
        RELEASE_TAG="${release_lines[0]:-}"
        local tarball_url="${release_lines[1]:-}"
        local release_html_url="${release_lines[2]:-}"

        if [ -z "$RELEASE_TAG" ] || [ -z "$tarball_url" ]; then
            log_error "Unable to fetch release metadata from GitHub"
            log_error "Debug output:"
            echo "$release_info" >&2
            exit 1
        fi

        log_info "Release: $RELEASE_TAG"
        if [ -n "$release_html_url" ]; then
            log_info "Release URL: $release_html_url"
        fi

        download_release "$tarball_url"
        SOURCE_DIR="$RELEASE_DIR"
    fi

    create_directories
    install_python_packages
    copy_files
    set_permissions
    configure_systemd
    show_completion_message
}

# Run main function
main "$@"
