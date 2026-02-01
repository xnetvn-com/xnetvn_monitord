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

"""xNetVN Monitor Daemon Package.

This package provides comprehensive monitoring and automatic recovery
capabilities for Ubuntu 22 LTS servers.
"""

__version__ = "1.0.0"
__author__ = "xNetVN Inc."
__license__ = "Apache-2.0"

from .daemon import MonitorDaemon

__all__ = ["MonitorDaemon"]
