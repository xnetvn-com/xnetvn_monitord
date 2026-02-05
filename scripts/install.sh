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
# This script installs and configures the xNetVN monitor daemon

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

check_root() {
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
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        log_warning "Missing dependencies: ${missing_deps[*]}"
        log_info "Installing dependencies..."
        apt-get update
        apt-get install -y "${missing_deps[@]}"
    else
        log_info "All dependencies are satisfied"
    fi
}

install_python_packages() {
    log_info "Installing Python packages..."

    local venv_python="$VENV_DIR/bin/python"
    local venv_pip="$VENV_DIR/bin/pip"

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

    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

    if [ -f "$script_dir/requirements.txt" ]; then
        "$venv_pip" install -r "$script_dir/requirements.txt"
    else
        log_warning "requirements.txt not found, falling back to core packages"
        "$venv_pip" install PyYAML psutil
    fi
}

create_directories() {
    log_info "Creating directories..."
    
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$INSTALL_DIR/.local"/{logs,reports,tmp}
    
    log_info "Directories created successfully"
}

copy_files() {
    log_info "Copying application files..."
    
    # Get script directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    
    # Copy source code
    if [ -d "$SCRIPT_DIR/src" ]; then
        cp -r "$SCRIPT_DIR/src/xnetvn_monitord" "$INSTALL_DIR/"
        log_info "Source code copied"
    else
        log_error "Source directory not found: $SCRIPT_DIR/src"
        exit 1
    fi
    
    # Copy configuration
    if [ -f "$CONFIG_DIR/main.yaml" ]; then
        log_warning "Configuration file already exists: $CONFIG_DIR/main.yaml"
        log_warning "Skipping configuration copy to avoid overwriting user changes"
    elif [ -f "$SCRIPT_DIR/config/main.example.yaml" ]; then
        cp "$SCRIPT_DIR/config/main.example.yaml" "$CONFIG_DIR/main.yaml"
        log_warning "Using example configuration. Please edit $CONFIG_DIR/main.yaml"
    elif [ -f "$SCRIPT_DIR/config/main.yaml" ]; then
        cp "$SCRIPT_DIR/config/main.yaml" "$CONFIG_DIR/"
        log_info "Configuration file copied"
    else
        log_error "No configuration file found"
        exit 1
    fi

    if [ -f "$CONFIG_DIR/.env" ]; then
        log_warning "Environment file already exists: $CONFIG_DIR/.env"
        log_warning "Skipping environment copy to avoid overwriting user changes"
    elif [ -f "$SCRIPT_DIR/config/.env.example" ]; then
        cp "$SCRIPT_DIR/config/.env.example" "$CONFIG_DIR/.env"
        log_warning "Using example environment file. Please edit $CONFIG_DIR/.env"
    else
        log_warning "Environment example file not found in repository"
    fi

    if [ -f "$SCRIPT_DIR/config/main.example.yaml" ]; then
        cp "$SCRIPT_DIR/config/main.example.yaml" "$CONFIG_DIR/main.example.yaml"
        log_info "Configuration example file refreshed"
    else
        log_warning "Configuration example file not found in repository"
    fi

    if [ -f "$SCRIPT_DIR/config/.env.example" ]; then
        cp "$SCRIPT_DIR/config/.env.example" "$CONFIG_DIR/.env.example"
        log_info "Environment example file refreshed"
    else
        log_warning "Environment example file not found in repository"
    fi
    
    # Copy systemd service
    if [ -f "$SCRIPT_DIR/systemd/xnetvn_monitord.service" ]; then
        if [ -f "$SYSTEMD_SERVICE" ]; then
            log_warning "Systemd service file already exists: $SYSTEMD_SERVICE"
            log_warning "Skipping service file copy to avoid overwriting changes"
        else
            cp "$SCRIPT_DIR/systemd/xnetvn_monitord.service" "$SYSTEMD_SERVICE"
            log_info "Systemd service file copied"
        fi
    else
        log_error "Systemd service file not found"
        exit 1
    fi
}

set_permissions() {
    log_info "Setting permissions..."
    
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
    
    systemctl daemon-reload
    systemctl enable xnetvn_monitord.service
    
    log_info "Systemd service configured and enabled"
}

show_completion_message() {
    echo ""
    log_info "=================================================="
    log_info "Installation completed successfully!"
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
    log_info "Starting xNetVN Monitor Daemon installation..."
    echo ""
    
    check_root
    check_dependencies
    create_directories
    install_python_packages
    copy_files
    set_permissions
    configure_systemd
    show_completion_message
}

# Run main function
main
