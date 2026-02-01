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

"""Environment file loader for runtime configuration."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _strip_quotes(value: str) -> str:
    """Strip surrounding quotes from a value if present.

    Args:
        value: Raw value string.

    Returns:
        Unquoted value.
    """
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _parse_env_line(line: str) -> Optional[Tuple[str, str]]:
    """Parse a single line from a .env file.

    Args:
        line: Raw line content.

    Returns:
        Tuple of (key, value) or None if line is invalid or a comment.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("export "):
        stripped = stripped[7:].strip()

    if "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()

    if not key or not _ENV_KEY_PATTERN.match(key):
        logger.warning("Skipping invalid environment key in .env file: %s", key)
        return None

    return key, _strip_quotes(value)


def load_env_file(file_path: str, overwrite: bool = False) -> Dict[str, str]:
    """Load environment variables from a .env file.

    Args:
        file_path: Path to the .env file.
        overwrite: Whether to overwrite existing environment variables.

    Returns:
        Dictionary of loaded environment variables.
    """
    env_path = Path(file_path)
    if not env_path.exists():
        logger.info("Environment file not found: %s", env_path)
        return {}

    loaded: Dict[str, str] = {}

    try:
        with env_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                parsed = _parse_env_line(line)
                if not parsed:
                    continue
                key, value = parsed
                if not overwrite and key in os.environ:
                    logger.debug("Skipping existing environment key: %s", key)
                    continue
                os.environ[key] = value
                loaded[key] = value
    except Exception as exc:
        logger.error("Failed to load environment file %s: %s", env_path, exc)
        return {}

    logger.info("Loaded %d environment variables from %s", len(loaded), env_path)
    return loaded