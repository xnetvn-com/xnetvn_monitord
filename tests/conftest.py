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

"""Pytest configuration and shared fixtures.

This module provides shared fixtures and configuration for all tests.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Generator

import pytest
import yaml


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Get the test data directory path.

    Returns:
        Path to test data directory.
    """
    return Path(__file__).parent / "data"


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests.

    Yields:
        Path to temporary directory.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def sample_config() -> Dict:
    """Provide a sample valid configuration dictionary.

    Returns:
        Sample configuration dictionary.
    """
    return {
        "general": {
            "app_name": "xnetvn_monitord",
            "app_version": "1.0.0",
            "check_interval": 60,
            "pid_file": "/tmp/xnetvn_monitord.pid",
            "logging": {
                "enabled": True,
                "level": "INFO",
                "file": "/tmp/xnetvn_monitord.log",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "max_size_mb": 100,
                "backup_count": 10,
            },
        },
        "service_monitor": {
            "enabled": True,
            "action_on_failure": "restart_and_notify",
            "max_restart_attempts": 3,
            "restart_cooldown": 300,
            "services": [
                {
                    "name": "nginx",
                    "enabled": True,
                    "check_method": "systemctl",
                    "service_name": "nginx",
                },
                {
                    "name": "php-fpm",
                    "enabled": True,
                    "check_method": "process_regex",
                    "process_pattern": "php-fpm.*master",
                },
            ],
        },
        "resource_monitor": {
            "enabled": True,
            "cpu_load": {
                "enabled": True,
                "check_1min": True,
                "threshold_1min": 10.0,
                "check_5min": True,
                "threshold_5min": 8.0,
                "check_15min": True,
                "threshold_15min": 6.0,
            },
            "memory": {
                "enabled": True,
                "free_percent_threshold": 10.0,
                "free_mb_threshold": 512,
                "condition": "or",
            },
            "disk": {
                "enabled": True,
                "paths": [
                    {"path": "/", "threshold_percent": 90.0},
                    {"path": "/var", "threshold_percent": 85.0},
                ],
            },
        },
        "notifications": {
            "enabled": True,
            "rate_limit": {
                "enabled": True,
                "max_per_minute": 5,
                "max_per_hour": 50,
            },
            "content_filter": {
                "enabled": True,
                "patterns": [
                    "password",
                    "api[_-]?key",
                    "secret",
                    "token",
                ],
            },
            "email": {
                "enabled": False,
                "from_address": "monitor@example.com",
                "from_name": "xNetVN Monitor",
                "to_addresses": ["admin@example.com"],
                "subject_prefix": "[Test Monitor]",
                "include_hostname": True,
                "smtp": {
                    "host": "localhost",
                    "port": 25,
                    "username": "",
                    "password": "",
                    "use_tls": False,
                    "use_ssl": False,
                    "timeout": 30,
                },
                "template": {
                    "format": "plain",
                },
            },
            "telegram": {
                "enabled": False,
                "bot_token": "",
                "chat_ids": [],
                "parse_mode": "HTML",
                "disable_preview": True,
                "timeout": 30,
            },
        },
    }


@pytest.fixture
def config_file(temp_dir: Path, sample_config: Dict) -> Path:
    """Create a temporary configuration file.

    Args:
        temp_dir: Temporary directory fixture.
        sample_config: Sample configuration fixture.

    Returns:
        Path to created configuration file.
    """
    config_path = temp_dir / "test_config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(sample_config, f)
    return config_path


@pytest.fixture
def invalid_config_file(temp_dir: Path) -> Path:
    """Create an invalid configuration file.

    Args:
        temp_dir: Temporary directory fixture.

    Returns:
        Path to invalid configuration file.
    """
    config_path = temp_dir / "invalid_config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        f.write("invalid: yaml: content: [\n")
    return config_path


@pytest.fixture
def env_vars() -> Generator[None, None, None]:
    """Setup and teardown environment variables for tests.

    Yields:
        None
    """
    # Save original environment
    original_env = os.environ.copy()

    # Set test environment variables
    os.environ["TEST_VAR"] = "test_value"
    os.environ["TEST_PASSWORD"] = "secret123"
    os.environ["TEST_API_KEY"] = "key_12345"

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(autouse=True)
def setup_test_logging(caplog):
    """Setup logging for tests.

    Args:
        caplog: Pytest log capture fixture.
    """
    caplog.set_level(logging.DEBUG)


@pytest.fixture
def mock_service_running(mocker):
    """Mock a running service check.

    Args:
        mocker: Pytest-mock fixture.

    Returns:
        Mock object for subprocess.run.
    """
    mock = mocker.patch("subprocess.run")
    mock.return_value.returncode = 0
    mock.return_value.stdout = "active\n"
    return mock


@pytest.fixture
def mock_service_stopped(mocker):
    """Mock a stopped service check.

    Args:
        mocker: Pytest-mock fixture.

    Returns:
        Mock object for subprocess.run.
    """
    mock = mocker.patch("subprocess.run")
    mock.return_value.returncode = 3
    mock.return_value.stdout = "inactive\n"
    return mock


@pytest.fixture
def mock_psutil_memory(mocker):
    """Mock psutil memory information.

    Args:
        mocker: Pytest-mock fixture.

    Returns:
        Mock object for psutil.virtual_memory.
    """
    mock_mem = mocker.MagicMock()
    mock_mem.total = 8 * 1024 * 1024 * 1024  # 8 GB
    mock_mem.available = 2 * 1024 * 1024 * 1024  # 2 GB
    mock_mem.percent = 75.0
    return mocker.patch("psutil.virtual_memory", return_value=mock_mem)


@pytest.fixture
def mock_cpu_load(mocker):
    """Mock system load averages.

    Args:
        mocker: Pytest-mock fixture.

    Returns:
        Mock object for os.getloadavg.
    """
    return mocker.patch("os.getloadavg", return_value=(1.5, 2.0, 2.5))


@pytest.fixture
def mock_disk_usage(mocker):
    """Mock disk usage information.

    Args:
        mocker: Pytest-mock fixture.

    Returns:
        Mock object for psutil.disk_usage.
    """
    mock_usage = mocker.MagicMock()
    mock_usage.total = 100 * 1024 * 1024 * 1024  # 100 GB
    mock_usage.used = 80 * 1024 * 1024 * 1024  # 80 GB
    mock_usage.free = 20 * 1024 * 1024 * 1024  # 20 GB
    mock_usage.percent = 80.0
    return mocker.patch("psutil.disk_usage", return_value=mock_usage)


@pytest.fixture
def mock_smtp_server(mocker):
    """Mock SMTP server connection.

    Args:
        mocker: Pytest-mock fixture.

    Returns:
        Mock SMTP instance.
    """
    mock_smtp = mocker.MagicMock()
    return mocker.patch("smtplib.SMTP", return_value=mock_smtp)


@pytest.fixture
def mock_telegram_api(mocker, responses):
    """Mock Telegram Bot API responses.

    Args:
        mocker: Pytest-mock fixture.
        responses: Responses library fixture.

    Returns:
        Configured responses mock.
    """
    responses.add(
        responses.POST,
        "https://api.telegram.org/botTEST_TOKEN/sendMessage",
        json={"ok": True, "result": {"message_id": 123}},
        status=200,
    )
    return responses


# Pytest configuration hooks
def pytest_configure(config):
    """Configure pytest with custom settings.

    Args:
        config: Pytest configuration object.
    """
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, isolated)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (slower, multiple components)"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests (slowest, full workflow)"
    )
    config.addinivalue_line(
        "markers", "performance: Performance and benchmark tests"
    )
    config.addinivalue_line(
        "markers", "security: Security-focused tests"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take more than 1 second"
    )
    config.addinivalue_line(
        "markers", "requires_root: Tests that require root privileges"
    )
    config.addinivalue_line(
        "markers", "requires_network: Tests that require network access"
    )


def pytest_collection_modifyitems(config, items):
    """Assign markers based on test location and naming.

    Args:
        config: Pytest configuration object.
        items: List of collected test items.
    """
    del config

    for item in items:
        nodeid_lower = item.nodeid.lower()
        path = str(item.fspath)

        if "/tests/integration/" in path:
            item.add_marker(pytest.mark.integration)
            continue

        if "/tests/e2e/" in path:
            item.add_marker(pytest.mark.e2e)
            item.add_marker(pytest.mark.slow)
            continue

        if "/tests/performance/" in path or "performance" in nodeid_lower:
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)
            continue

        if "security" in nodeid_lower:
            item.add_marker(pytest.mark.security)

        item.add_marker(pytest.mark.unit)
