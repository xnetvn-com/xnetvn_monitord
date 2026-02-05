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

"""Telegram notification module.

This module provides functionality to send notifications via Telegram Bot API.
"""

import json
import logging
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

from xnetvn_monitord.utils.network import force_ipv4

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send notifications via Telegram Bot API."""

    def __init__(self, config: Dict):
        """Initialize the Telegram notifier.

        Args:
            config: Telegram notification configuration dictionary.
        """
        self.config = config
        self.enabled = config.get("enabled", False)
        self.bot_token = config.get("bot_token", "")
        self.chat_ids = config.get("chat_ids", [])
        self.parse_mode = config.get("parse_mode", "HTML")
        self.disable_preview = config.get("disable_preview", True)
        self.timeout = config.get("timeout", 30)
        self.hostname = socket.gethostname()
        self.only_ipv4 = config.get("only_ipv4", False)
        self.api_base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_notification(self, message: str) -> bool:
        """Send a notification to all configured chat IDs.

        Args:
            message: Message text to send.

        Returns:
            True if at least one message sent successfully, False otherwise.
        """
        if not self.enabled:
            logger.debug("Telegram notifications are disabled")
            return False

        if not self.bot_token:
            logger.warning("Telegram bot token not configured")
            return False

        if not self.chat_ids:
            logger.warning("No Telegram chat IDs configured")
            return False

        success_count = 0
        for chat_id in self.chat_ids:
            chat_target, thread_id = self._parse_chat_target(str(chat_id))
            if self._send_message(chat_target, message, thread_id):
                success_count += 1

        if success_count > 0:
            logger.info(
                f"Telegram notification sent successfully to {success_count}/{len(self.chat_ids)} chats"
            )
            return True
        else:
            logger.error("Failed to send Telegram notification to any chat")
            return False

    def _send_message(
        self,
        chat_id: str,
        message: str,
        message_thread_id: Optional[int] = None,
    ) -> bool:
        """Send a message to a specific chat ID.

        Args:
            chat_id: Telegram chat ID.
            message: Message text to send.

        Returns:
            True if message sent successfully, False otherwise.
        """
        try:
            url = f"{self.api_base_url}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": self.parse_mode,
                "disable_web_page_preview": self.disable_preview,
            }

            if message_thread_id is not None:
                data["message_thread_id"] = message_thread_id

            encoded_data = urllib.parse.urlencode(data).encode("utf-8")
            request = urllib.request.Request(url, data=encoded_data, method="POST")

            with force_ipv4(self.only_ipv4):
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    if result.get("ok"):
                        logger.debug(
                            "Telegram message sent successfully to chat %s", chat_id
                        )
                        return True
                    logger.error(
                        "Telegram API error for chat %s: %s",
                        chat_id,
                        result.get("description"),
                    )
                    return False
        except Exception as e:
            logger.error(
                f"Error sending Telegram message to {chat_id}: {str(e)}", exc_info=True
            )
            return False

    def send_service_alert(self, service_name: str, status: str, details: str) -> bool:
        """Send a service status alert.

        Args:
            service_name: Name of the service.
            status: Service status (down, restarted, failed).
            details: Detailed information about the service.

        Returns:
            True if notification sent successfully, False otherwise.
        """
        message = self._format_service_alert(service_name, status, details)
        return self.send_notification(message)

    def send_resource_alert(self, resource_type: str, details: Dict) -> bool:
        """Send a resource threshold alert.

        Args:
            resource_type: Type of resource (cpu, memory, disk).
            details: Detailed resource information.

        Returns:
            True if notification sent successfully, False otherwise.
        """
        message = self._format_resource_alert(resource_type, details)
        return self.send_notification(message)

    def _format_service_alert(self, service_name: str, status: str, details: str) -> str:
        """Format service alert message.

        Args:
            service_name: Name of the service.
            status: Service status.
            details: Detailed information.

        Returns:
            Formatted message string.
        """
        if self.parse_mode == "HTML":
            status_emoji = {
                "down": "🔴",
                "restarted": "🔄",
                "failed": "❌",
                "recovered": "✅",
            }.get(status.lower(), "⚠️")

            message = f"""
{status_emoji} <b>Service Alert</b>

<b>Service:</b> {service_name}
<b>Status:</b> {status.upper()}
<b>Server:</b> {self.hostname}

<b>Details:</b>
<code>{self._escape_html(details)}</code>

<i>xNetVN Monitor</i>
"""
        else:  # Markdown
            status_emoji = {
                "down": "🔴",
                "restarted": "🔄",
                "failed": "❌",
                "recovered": "✅",
            }.get(status.lower(), "⚠️")

            message = f"""
{status_emoji} *Service Alert*

*Service:* {service_name}
*Status:* {status.upper()}
*Server:* {self.hostname}

*Details:*
```
{details}
```

_xNetVN Monitor_
"""
        return message.strip()

    @staticmethod
    def _parse_chat_target(chat_id: str) -> Tuple[str, Optional[int]]:
        """Parse Telegram chat ID and optional topic thread ID.

        Args:
            chat_id: Chat identifier, optionally with "_" separator.

        Returns:
            Tuple of chat ID and optional message thread ID.
        """
        if "_" not in chat_id:
            return chat_id, None

        base_id, thread_id = chat_id.split("_", 1)
        if not base_id:
            return chat_id, None

        if thread_id.isdigit():
            return base_id, int(thread_id)

        logger.warning("Invalid Telegram topic id in chat_id: %s", chat_id)
        return base_id, None

    def _format_resource_alert(self, resource_type: str, details: Dict) -> str:
        """Format resource alert message.

        Args:
            resource_type: Type of resource.
            details: Resource details.

        Returns:
            Formatted message string.
        """
        resource_emoji = {
            "cpu": "💻",
            "memory": "🧠",
            "disk": "💾",
        }.get(resource_type.lower(), "📊")

        if self.parse_mode == "HTML":
            message = f"""
{resource_emoji} <b>Resource Alert</b>

<b>Resource:</b> {resource_type.upper()}
<b>Server:</b> {self.hostname}

<b>Details:</b>
<code>{self._escape_html(self._dict_to_string(details))}</code>

<i>xNetVN Monitor</i>
"""
        else:  # Markdown
            message = f"""
{resource_emoji} *Resource Alert*

*Resource:* {resource_type.upper()}
*Server:* {self.hostname}

*Details:*
```
{self._dict_to_string(details)}
```

_xNetVN Monitor_
"""
        return message.strip()

    def _dict_to_string(self, data: Dict, indent: int = 0) -> str:
        """Convert dictionary to formatted string.

        Args:
            data: Dictionary to convert.
            indent: Indentation level.

        Returns:
            Formatted string representation.
        """
        lines = []
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{'  ' * indent}{key}:")
                lines.append(self._dict_to_string(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{'  ' * indent}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(self._dict_to_string(item, indent + 1))
                    else:
                        lines.append(f"{'  ' * (indent + 1)}- {item}")
            else:
                lines.append(f"{'  ' * indent}{key}: {value}")
        return "\n".join(lines)

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters.

        Args:
            text: Text to escape.

        Returns:
            Escaped text.
        """
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def test_connection(self) -> bool:
        """Test Telegram bot connection.

        Returns:
            True if connection successful, False otherwise.
        """
        if not self.enabled:
            logger.info("Telegram notifications are disabled")
            return False

        if not self.bot_token:
            logger.warning("Telegram bot token not configured")
            return False

        try:
            url = f"{self.api_base_url}/getMe"
            request = urllib.request.Request(url, method="GET")

            with force_ipv4(self.only_ipv4):
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    if result.get("ok"):
                        bot_info = result.get("result", {})
                        bot_name = bot_info.get("username", "Unknown")
                        logger.info(
                            "Telegram bot connection test successful. Bot: @%s",
                            bot_name,
                        )
                        return True
                    logger.error(
                        "Telegram API error: %s",
                        result.get("description"),
                    )
                    return False

        except Exception as e:
            logger.error(f"Telegram connection test failed: {str(e)}")
            return False
