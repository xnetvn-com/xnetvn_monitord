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

"""Webhook notification module.

This module provides functionality to send JSON notifications to webhook endpoints.
"""

import json
import logging
import ssl
import urllib.error
import urllib.request
from typing import Dict, List, Optional

from xnetvn_monitord.utils.network import force_ipv4

logger = logging.getLogger(__name__)


class WebhookNotifier:
    """Send notifications to generic webhook endpoints."""

    def __init__(self, config: Dict):
        """Initialize the webhook notifier.

        Args:
            config: Webhook notification configuration dictionary.
        """
        self.config = config
        self.enabled = config.get("enabled", False)
        self.urls = self._normalize_urls(config)
        self.headers = config.get("headers", {})
        self.timeout = config.get("timeout", 30)
        self.verify_ssl = config.get("verify_ssl", True)
        self.test_on_startup = config.get("test_on_startup", False)
        self.only_ipv4 = config.get("only_ipv4", False)

    def send_notification(self, payload: Dict, extra_headers: Optional[Dict] = None) -> bool:
        """Send a JSON payload to all configured webhook URLs.

        Args:
            payload: JSON-serializable payload to send.
            extra_headers: Optional headers to merge with configured headers.

        Returns:
            True if at least one webhook request succeeded, False otherwise.
        """
        if not self.enabled:
            logger.debug("Webhook notifications are disabled")
            return False

        if not self.urls:
            logger.warning("No webhook URLs configured")
            return False

        merged_headers = {"Content-Type": "application/json"}
        merged_headers.update(self.headers)
        if extra_headers:
            merged_headers.update(extra_headers)

        success_count = 0
        for url in self.urls:
            if self._post_payload(url, payload, merged_headers):
                success_count += 1

        if success_count > 0:
            logger.info(
                "Webhook notification sent successfully to %s/%s endpoints",
                success_count,
                len(self.urls),
            )
            return True

        logger.error("Failed to send webhook notification to any endpoint")
        return False

    def test_connection(self) -> bool:
        """Test webhook configuration.

        Returns:
            True if configuration looks valid or test request succeeds, False otherwise.
        """
        if not self.enabled:
            logger.info("Webhook notifications are disabled")
            return False

        if not self.urls:
            logger.warning("No webhook URLs configured")
            return False

        if not self.test_on_startup:
            logger.info("Webhook test_on_startup disabled; skipping live test")
            return True

        test_payload = {
            "type": "test",
            "message": "Webhook test notification from xNetVN Monitor",
        }
        return self._post_payload(self.urls[0], test_payload, {"Content-Type": "application/json"})

    def _post_payload(self, url: str, payload: Dict, headers: Dict) -> bool:
        """Send a POST request with JSON payload.

        Args:
            url: Webhook endpoint URL.
            payload: JSON-serializable payload.
            headers: HTTP headers.

        Returns:
            True if request succeeded, False otherwise.
        """
        try:
            data = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(url, data=data, headers=headers, method="POST")

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
                        logger.debug("Webhook POST succeeded: %s", url)
                        return True

                    logger.error("Webhook POST failed (%s): %s", status_code, url)
                    return False

        except urllib.error.URLError as exc:
            logger.error("Webhook URL error for %s: %s", url, exc)
            return False
        except Exception as exc:
            logger.error("Webhook POST error for %s: %s", url, exc, exc_info=True)
            return False

    @staticmethod
    def _normalize_urls(config: Dict) -> List[str]:
        """Normalize webhook URLs from configuration.

        Args:
            config: Webhook configuration dictionary.

        Returns:
            List of webhook URLs.
        """
        urls = config.get("urls") or []
        url = config.get("url")
        if url:
            urls = [url]
        return [item for item in urls if item]
