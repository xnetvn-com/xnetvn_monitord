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

"""Configuration loader utility.

This module provides functionality to load and validate configuration files.
"""

import logging
import os
import re
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Load and manage application configuration."""

    def __init__(self, config_path: str):
        """Initialize the configuration loader.

        Args:
            config_path: Path to the configuration file.
        """
        self.config_path = config_path
        self.config: Dict = {}

    def load(self) -> Dict:
        """Load configuration from file.

        Returns:
            Configuration dictionary.

        Raises:
            FileNotFoundError: If configuration file not found.
            yaml.YAMLError: If configuration file is invalid.
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        logger.info(f"Loading configuration from: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Expand environment variables
        content = self._expand_env_vars(content)

        # Parse YAML
        self.config = yaml.safe_load(content)

        # Validate configuration
        self._validate_config()

        logger.info("Configuration loaded successfully")
        return self.config

    def _expand_env_vars(self, content: str) -> str:
        """Expand environment variables in configuration.

        Args:
            content: Configuration file content.

        Returns:
            Content with expanded environment variables.
        """
        # Pattern to match ${VAR_NAME} or $VAR_NAME
        pattern = re.compile(r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)')

        def replacer(match):
            var_name = match.group(1) or match.group(2)
            value = os.environ.get(var_name)
            if value is None:
                logger.warning(f"Environment variable not found: {var_name}")
                return "null"  # Return 'null' string which YAML will parse as None
            return value

        return pattern.sub(replacer, content)

    def _validate_config(self) -> None:
        """Validate configuration structure.

        Raises:
            ValueError: If configuration is invalid.
        """
        # Handle empty YAML files (yaml.safe_load returns None)
        if self.config is None:
            self.config = {}
        
        if not isinstance(self.config, dict):
            raise ValueError("Configuration must be a dictionary")

        # Validate required sections
        required_sections = ["general", "service_monitor", "resource_monitor", "notifications"]
        for section in required_sections:
            if section not in self.config:
                logger.warning(f"Missing configuration section: {section}")

        logger.debug("Configuration validation passed")

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key.

        Args:
            key: Configuration key (supports dot notation, e.g., 'general.app_name').
            default: Default value if key not found.

        Returns:
            Configuration value.
        """
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def reload(self) -> Dict:
        """Reload configuration from file.

        Returns:
            Reloaded configuration dictionary.
        """
        logger.info("Reloading configuration...")
        return self.load()
