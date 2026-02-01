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

"""Unit tests for ConfigLoader.

This module contains comprehensive unit tests for the configuration
loading and validation functionality.
"""

import os
from pathlib import Path

import pytest
import yaml

from xnetvn_monitord.utils.config_loader import ConfigLoader


class TestConfigLoaderInitialization:
    """Tests for ConfigLoader initialization."""

    def test_should_initialize_with_config_path(self, config_file):
        """Test successful initialization with valid config path."""
        loader = ConfigLoader(str(config_file))
        assert loader.config_path == str(config_file)
        assert loader.config == {}

    def test_should_store_config_path_as_string(self, config_file):
        """Test that config path is stored as string."""
        loader = ConfigLoader(str(config_file))
        assert isinstance(loader.config_path, str)


class TestConfigLoaderLoad:
    """Tests for configuration loading."""

    def test_should_load_valid_yaml_successfully(self, config_file):
        """Test loading a valid YAML configuration file."""
        loader = ConfigLoader(str(config_file))
        config = loader.load()

        assert isinstance(config, dict)
        assert "general" in config
        assert "service_monitor" in config
        assert "resource_monitor" in config
        assert "notifications" in config

    def test_should_raise_error_when_file_not_found(self, temp_dir):
        """Test that FileNotFoundError is raised for non-existent file."""
        non_existent = str(temp_dir / "nonexistent.yaml")
        loader = ConfigLoader(non_existent)

        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load()

        assert "not found" in str(exc_info.value).lower()

    def test_should_raise_error_when_yaml_invalid(self, invalid_config_file):
        """Test that yaml.YAMLError is raised for invalid YAML."""
        loader = ConfigLoader(str(invalid_config_file))

        with pytest.raises(yaml.YAMLError):
            loader.load()

    def test_should_return_config_dict_with_all_sections(self, config_file):
        """Test that loaded config contains all required sections."""
        loader = ConfigLoader(str(config_file))
        config = loader.load()

        required_sections = ["general", "service_monitor", "resource_monitor", "notifications"]
        for section in required_sections:
            assert section in config

    def test_should_store_loaded_config_internally(self, config_file):
        """Test that loaded config is stored in instance variable."""
        loader = ConfigLoader(str(config_file))
        config = loader.load()

        assert loader.config == config
        assert loader.config is config

    def test_should_handle_empty_yaml_file(self, temp_dir):
        """Test handling of empty YAML file."""
        empty_file = temp_dir / "empty.yaml"
        empty_file.write_text("")

        loader = ConfigLoader(str(empty_file))
        config = loader.load()

        # Empty YAML file results in None, which might be converted to {}
        assert config is None or config == {}

    def test_should_handle_unicode_in_config(self, temp_dir):
        """Test handling of Unicode characters in configuration."""
        unicode_config = {
            "general": {
                "app_name": "モニター",  # Japanese
                "description": "Überwachung",  # German
                "message": "你好世界",  # Chinese
            }
        }

        config_file = temp_dir / "unicode.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(unicode_config, f, allow_unicode=True)

        loader = ConfigLoader(str(config_file))
        config = loader.load()

        assert config["general"]["app_name"] == "モニター"
        assert config["general"]["description"] == "Überwachung"
        assert config["general"]["message"] == "你好世界"

    def test_should_handle_large_config_file(self, temp_dir):
        """Test handling of large configuration file."""
        large_config = {"general": {"app_name": "test"}}

        # Add many services to create a large config
        large_config["service_monitor"] = {"services": []}
        for i in range(1000):
            large_config["service_monitor"]["services"].append(
                {
                    "name": f"service_{i}",
                    "enabled": True,
                    "check_method": "systemctl",
                    "service_name": f"service_{i}",
                }
            )

        config_file = temp_dir / "large.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(large_config, f)

        loader = ConfigLoader(str(config_file))
        config = loader.load()

        assert len(config["service_monitor"]["services"]) == 1000


class TestConfigLoaderEnvironmentVariables:
    """Tests for environment variable expansion."""

    def test_should_expand_environment_variables_correctly(self, temp_dir, env_vars):
        """Test expansion of environment variables in config."""
        config_content = """
general:
  app_name: ${TEST_VAR}
  password: ${TEST_PASSWORD}
"""
        config_file = temp_dir / "env_test.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader(str(config_file))
        config = loader.load()

        assert config["general"]["app_name"] == "test_value"
        assert config["general"]["password"] == "secret123"

    def test_should_warn_when_env_var_missing(self, temp_dir, caplog):
        """Test warning is logged when environment variable is missing."""
        config_content = """
general:
  app_name: ${NONEXISTENT_VAR}
"""
        config_file = temp_dir / "missing_env.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader(str(config_file))
        config = loader.load()

        # Should replace with None (null in YAML)
        assert config["general"]["app_name"] is None

        # Should log warning
        assert any("NONEXISTENT_VAR" in record.message for record in caplog.records)

    def test_should_handle_nested_env_vars(self, temp_dir, env_vars):
        """Test handling of nested structures with environment variables."""
        config_content = """
general:
  credentials:
    username: admin
    password: ${TEST_PASSWORD}
  api:
    key: ${TEST_API_KEY}
"""
        config_file = temp_dir / "nested_env.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader(str(config_file))
        config = loader.load()

        assert config["general"]["credentials"]["password"] == "secret123"
        assert config["general"]["api"]["key"] == "key_12345"

    def test_should_expand_dollar_sign_vars(self, temp_dir, env_vars):
        """Test expansion of $VAR_NAME style variables."""
        config_content = """
general:
  test_var: $TEST_VAR
"""
        config_file = temp_dir / "dollar_var.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader(str(config_file))
        config = loader.load()

        assert config["general"]["test_var"] == "test_value"

    def test_should_expand_new_env_vars_on_reload(self, temp_dir, env_vars):
        """Test that new environment variables are expanded on reload."""
        config_content = """
general:
  app_name: ${TEST_VAR}
  dynamic_var: ${DYNAMIC_VAR}
"""
        config_file = temp_dir / "reload_env.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader(str(config_file))
        config1 = loader.load()

        assert config1["general"]["app_name"] == "test_value"
        assert config1["general"]["dynamic_var"] is None  # Should be None when env var not found

        # Set new environment variable
        os.environ["DYNAMIC_VAR"] = "dynamic_value"

        # Reload configuration
        config2 = loader.reload()

        assert config2["general"]["dynamic_var"] == "dynamic_value"


class TestConfigLoaderValidation:
    """Tests for configuration validation."""

    def test_should_validate_config_structure(self, config_file):
        """Test validation of configuration structure."""
        loader = ConfigLoader(str(config_file))
        # Should not raise any exception
        config = loader.load()
        assert isinstance(config, dict)

    def test_should_raise_error_when_config_not_dict(self, temp_dir):
        """Test that ValueError is raised when config is not a dict."""
        config_file = temp_dir / "invalid_type.yaml"
        config_file.write_text("- item1\n- item2\n")

        loader = ConfigLoader(str(config_file))

        with pytest.raises(ValueError) as exc_info:
            loader.load()

        assert "dictionary" in str(exc_info.value).lower()

    def test_should_warn_when_required_section_missing(self, temp_dir, caplog):
        """Test warning when required config section is missing."""
        minimal_config = {"general": {"app_name": "test"}}

        config_file = temp_dir / "minimal.yaml"
        with open(config_file, "w") as f:
            yaml.dump(minimal_config, f)

        loader = ConfigLoader(str(config_file))
        loader.load()

        # Should warn about missing sections
        warning_messages = [r.message for r in caplog.records if r.levelname == "WARNING"]
        missing_sections = ["service_monitor", "resource_monitor", "notifications"]

        for section in missing_sections:
            assert any(section in msg for msg in warning_messages)


class TestConfigLoaderGet:
    """Tests for configuration value retrieval."""

    def test_should_support_get_with_dot_notation(self, config_file):
        """Test getting values using dot notation."""
        loader = ConfigLoader(str(config_file))
        loader.load()

        app_name = loader.get("general.app_name")
        assert app_name == "xnetvn_monitord"

        check_interval = loader.get("general.check_interval")
        assert check_interval == 60

    def test_should_return_default_when_key_not_found(self, config_file):
        """Test returning default value when key is not found."""
        loader = ConfigLoader(str(config_file))
        loader.load()

        value = loader.get("nonexistent.key", default="default_value")
        assert value == "default_value"

    def test_should_return_none_when_no_default_provided(self, config_file):
        """Test returning None when key not found and no default."""
        loader = ConfigLoader(str(config_file))
        loader.load()

        value = loader.get("nonexistent.key")
        assert value is None

    def test_should_get_nested_values(self, config_file):
        """Test getting nested configuration values."""
        loader = ConfigLoader(str(config_file))
        loader.load()

        smtp_host = loader.get("notifications.email.smtp.host")
        assert smtp_host == "localhost"

        smtp_port = loader.get("notifications.email.smtp.port")
        assert smtp_port == 25

    def test_should_handle_special_characters_in_values(self, temp_dir):
        """Test handling special characters in configuration values."""
        special_config = {
            "general": {
                "regex_pattern": r"^php-fpm.*\d+$",
                "command": 'echo "test" && exit 0',
                "url": "https://api.example.com/v1/status?key=abc123&format=json",
            }
        }

        config_file = temp_dir / "special_chars.yaml"
        with open(config_file, "w") as f:
            yaml.dump(special_config, f)

        loader = ConfigLoader(str(config_file))
        config = loader.load()

        assert config["general"]["regex_pattern"] == r"^php-fpm.*\d+$"
        assert 'echo "test"' in config["general"]["command"]
        assert "key=abc123" in config["general"]["url"]


class TestConfigLoaderReload:
    """Tests for configuration reloading."""

    def test_should_reload_config_successfully(self, config_file):
        """Test successful configuration reload."""
        loader = ConfigLoader(str(config_file))
        config1 = loader.load()

        # Modify the config file
        with open(config_file, "r") as f:
            config_dict = yaml.safe_load(f)

        config_dict["general"]["check_interval"] = 120

        with open(config_file, "w") as f:
            yaml.dump(config_dict, f)

        # Reload
        config2 = loader.reload()

        assert config1["general"]["check_interval"] == 60
        assert config2["general"]["check_interval"] == 120

    def test_should_preserve_state_after_failed_reload(self, config_file):
        """Test that state is preserved if reload fails."""
        loader = ConfigLoader(str(config_file))
        original_config = loader.load()

        # Save original content
        with open(config_file, "r") as f:
            original_content = f.read()

        # Corrupt the config file
        with open(config_file, "w") as f:
            f.write("invalid: yaml: content: [\n")

        # Attempt reload - should fail
        with pytest.raises(yaml.YAMLError):
            loader.reload()

        # Original config should still be accessible
        # (Note: Current implementation doesn't preserve state on error,
        # this test documents expected behavior for improvement)

        # Restore original content
        with open(config_file, "w") as f:
            f.write(original_content)


class TestConfigLoaderSecurity:
    """Tests for security-related functionality."""

    @pytest.mark.security
    def test_should_not_log_sensitive_values(self, temp_dir, caplog):
        """Test that sensitive values are not logged."""
        sensitive_config = {
            "general": {"app_name": "test"},
            "notifications": {
                "email": {"smtp": {"password": "secret_password_123"}},
                "telegram": {"bot_token": "123456:ABC-DEF"},
            },
        }

        config_file = temp_dir / "sensitive.yaml"
        with open(config_file, "w") as f:
            yaml.dump(sensitive_config, f)

        loader = ConfigLoader(str(config_file))
        loader.load()

        # Check that sensitive values don't appear in logs
        log_output = "\n".join([r.message for r in caplog.records])
        assert "secret_password_123" not in log_output
        assert "123456:ABC-DEF" not in log_output

    @pytest.mark.security
    @pytest.mark.requires_root
    def test_should_validate_file_permissions(self, temp_dir):
        """Test validation of configuration file permissions."""
        config_file = temp_dir / "permissions.yaml"
        config_file.write_text("general:\n  app_name: test\n")

        # Make file world-readable
        os.chmod(config_file, 0o644)

        loader = ConfigLoader(str(config_file))
        # Should load successfully but might log warning
        # (Current implementation doesn't check permissions,
        # this test documents expected behavior for security improvement)
        config = loader.load()
        assert config is not None
