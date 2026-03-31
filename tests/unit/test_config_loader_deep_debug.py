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

"""Focused tests for deep-debug config validation."""

import pytest

from xnetvn_monitord.utils.config_loader import ConfigLoader


def test_should_raise_error_when_logging_deep_debug_is_not_boolean(temp_dir):
    """Logging deep_debug must be a boolean."""
    config_file = temp_dir / "invalid_deep_debug.yaml"
    config_file.write_text("""
general:
  logging:
    enabled: true
    level: DEBUG
    deep_debug: "yes"
service_monitor: {}
resource_monitor: {}
notifications: {}
""")

    loader = ConfigLoader(str(config_file))

    with pytest.raises(ValueError, match="general.logging.deep_debug"):
        loader.load()


def test_should_raise_error_when_logging_deep_debug_file_is_not_string(temp_dir):
    """Deep debug file path must be a string when configured."""
    config_file = temp_dir / "invalid_deep_debug_file.yaml"
    config_file.write_text("""
general:
  logging:
    enabled: true
    level: DEBUG
    deep_debug_file: 123
service_monitor: {}
resource_monitor: {}
notifications: {}
""")

    loader = ConfigLoader(str(config_file))

    with pytest.raises(ValueError, match="general.logging.deep_debug_file"):
        loader.load()
