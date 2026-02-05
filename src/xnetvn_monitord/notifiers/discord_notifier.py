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

"""Discord notification module.

This module provides functionality to send notifications via Discord webhooks.
"""

import json
import logging
import ssl
import urllib.error
import urllib.request
from typing import Dict, Optional

from xnetvn_monitord.utils.network import force_ipv4

logger = logging.getLogger(__name__)


class DiscordNotifier:
    """Send notifications to Discord via webhooks."""

    def __init__(self, config: Dict):
        """Initialize the Discord notifier.

        Args:
            config: Discord notification configuration dictionary.
        """
        self.config = config
        self.enabled = config.get("enabled", False)
        self.webhook_url = config.get("webhook_url", "")
        self.username = config.get("username")
        self.avatar_url = config.get("avatar_url")
        self.timeout = config.get("timeout", 30)
        self.verify_ssl = config.get("verify_ssl", True)
        self.test_on_startup = config.get("test_on_startup", False)
        self.only_ipv4 = config.get("only_ipv4", False)

    def send_notification(self, message: str, payload: Optional[Dict] = None) -> bool:
        """Send a Discord notification message.

        Args:
            message: Message text to send.
            payload: Optional payload overrides.

        Returns:
            True if message sent successfully, False otherwise.
        """
        if not self.enabled:
            logger.debug("Discord notifications are disabled")
            return False

        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured")
            return False

        discord_payload = {"content": message}
        if self.username:
            discord_payload["username"] = self.username
        if self.avatar_url:
            discord_payload["avatar_url"] = self.avatar_url

        if payload:
            discord_payload.update(payload)

        return self._post_payload(discord_payload)

    def test_connection(self) -> bool:
        """Test Discord webhook configuration.

        Returns:
            True if configuration looks valid or test request succeeds, False otherwise.
        """
        if not self.enabled:
            logger.info("Discord notifications are disabled")
            return False

        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured")
            return False

        if not self.test_on_startup:
            logger.info("Discord test_on_startup disabled; skipping live test")
            return True

        return self._post_payload({"content": "Discord test notification from xNetVN Monitor"})

    def _post_payload(self, payload: Dict) -> bool:
        """Send a POST request with JSON payload to Discord.

        Args:
            payload: JSON payload to send.

        Returns:
            True if request succeeded, False otherwise.
        """
        try:
            data = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            request = urllib.request.Request(
                self.webhook_url, data=data, headers=headers, method="POST"
            )

            ssl_context = None
            if not self.verify_ssl:
                ssl_context = ssl._create_unverified_context()

            with force_ipv4(self.only_ipv4):
                with urllib.request.urlopen(
                    request,
                    timeout=self.timeout,
                    context=ssl_context,
                ) as response:
                    status_code = getattr(response, "status", response.getcode())
                    if 200 <= status_code < 300:
                        logger.debug("Discord notification sent successfully")
                        return True

                    logger.error("Discord webhook returned status %s", status_code)
                    return False

        except urllib.error.URLError as exc:
            logger.error("Discord URL error: %s", exc)
            return False
        except Exception as exc:
            logger.error("Discord notification error: %s", exc, exc_info=True)
            return False
