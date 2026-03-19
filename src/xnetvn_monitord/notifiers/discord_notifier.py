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

from xnetvn_monitord.utils.network import (
    ProxyConfigurationError,
    is_http_url,
    mask_proxy_uri,
    open_url,
    read_response_preview,
    redact_url_for_logs,
    resolve_proxy_uri,
)

logger = logging.getLogger(__name__)

DISCORD_WEBHOOK_USER_AGENT = "xnetvn_monitord/1.0"
DISCORD_CONTENT_LIMIT = 2000


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
        self.proxy_config = config.get("proxy")

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
            target_label = redact_url_for_logs(self.webhook_url)
            if not is_http_url(self.webhook_url):
                logger.error("Discord webhook URL has invalid scheme: %s", target_label)
                return False

            discord_payload = dict(payload)
            content = discord_payload.get("content")
            if isinstance(content, str) and len(content) > DISCORD_CONTENT_LIMIT:
                logger.warning(
                    "Discord content exceeded %s characters; truncating target=%s original_length=%s",
                    DISCORD_CONTENT_LIMIT,
                    target_label,
                    len(content),
                )
                discord_payload["content"] = content[: DISCORD_CONTENT_LIMIT - len("...")] + "..."

            data = json.dumps(discord_payload).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "User-Agent": DISCORD_WEBHOOK_USER_AGENT,
            }
            request = urllib.request.Request(self.webhook_url, data=data, headers=headers, method="POST")

            ssl_context = None
            if not self.verify_ssl:
                logger.warning("Discord SSL verification is disabled for webhook requests")
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

            with open_url(
                request,
                self.timeout,
                ssl_context,
                self.proxy_config,
                self.only_ipv4,
            ) as response:  # nosec B310
                status_code = getattr(response, "status", response.getcode())
                if 200 <= status_code < 300:
                    logger.debug("Discord notification sent successfully")
                    return True

                logger.error(
                    "Discord webhook request failed target=%s status=%s response=%s",
                    target_label,
                    status_code,
                    read_response_preview(response) or "<empty>",
                )
                return False

        except urllib.error.HTTPError as exc:
            logger.error(
                "Discord webhook request failed target=%s status=%s response=%s",
                redact_url_for_logs(self.webhook_url),
                exc.code,
                read_response_preview(exc) or str(exc),
            )
            return False

        except urllib.error.URLError as exc:
            logger.error("Discord webhook request error target=%s: %s", redact_url_for_logs(self.webhook_url), exc)
            return False
        except ProxyConfigurationError as exc:
            proxy_uri = resolve_proxy_uri(self.proxy_config)
            proxy_label = mask_proxy_uri(proxy_uri) if proxy_uri else "unknown"
            logger.error(
                "Discord proxy configuration error target=%s proxy=%s: %s",
                redact_url_for_logs(self.webhook_url),
                proxy_label,
                exc,
            )
            return False
        except Exception as exc:
            logger.error(
                "Discord notification error target=%s: %s",
                redact_url_for_logs(self.webhook_url),
                exc,
                exc_info=True,
            )
            return False
