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

"""Unit tests for DiscordNotifier."""

import json
import logging
import ssl
from urllib.error import URLError

from xnetvn_monitord.notifiers.discord_notifier import DiscordNotifier
from xnetvn_monitord.utils.network import ProxyConfigurationError


class DummyResponse:
    """Minimal response stub for urllib."""

    def __init__(self, status=200):
        self.status = status

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return b"ok"


class TestDiscordNotifier:
    """Tests for DiscordNotifier."""

    def test_should_return_false_when_disabled(self):
        """Test disabled notifier returns False."""
        notifier = DiscordNotifier({"enabled": False})
        assert notifier.send_notification("test") is False

    def test_should_return_false_when_missing_webhook(self):
        """Test missing webhook URL returns False."""
        notifier = DiscordNotifier({"enabled": True})
        assert notifier.send_notification("test") is False

    def test_should_include_optional_payload_fields(self, mocker):
        """Test optional payload fields are included and overridden."""
        payloads = []

        def capture_payload(payload):
            payloads.append(payload)
            return True

        mocker.patch.object(DiscordNotifier, "_post_payload", side_effect=capture_payload)

        notifier = DiscordNotifier(
            {
                "enabled": True,
                "webhook_url": "https://example.com",
                "username": "bot",
                "avatar_url": "https://example.com/avatar.png",
            }
        )

        assert notifier.send_notification("test", payload={"content": "override"}) is True
        assert payloads[0]["username"] == "bot"
        assert payloads[0]["avatar_url"] == "https://example.com/avatar.png"
        assert payloads[0]["content"] == "override"

    def test_should_send_notification(self, mocker):
        """Test successful Discord notification."""
        mocker.patch("xnetvn_monitord.notifiers.discord_notifier.open_url", return_value=DummyResponse())

        notifier = DiscordNotifier({"enabled": True, "webhook_url": "https://example.com"})

        assert notifier.send_notification("test") is True

    def test_should_include_user_agent_header_in_request(self, mocker):
        """Test Discord requests include a user-agent header."""
        open_url_mock = mocker.patch(
            "xnetvn_monitord.notifiers.discord_notifier.open_url",
            return_value=DummyResponse(),
        )

        notifier = DiscordNotifier({"enabled": True, "webhook_url": "https://example.com"})

        assert notifier.send_notification("test") is True
        request = open_url_mock.call_args.args[0]
        assert request.get_header("User-agent") == "xnetvn_monitord/1.0"

    def test_should_truncate_content_to_discord_limit(self, mocker):
        """Test Discord content is capped at the API limit."""
        open_url_mock = mocker.patch(
            "xnetvn_monitord.notifiers.discord_notifier.open_url",
            return_value=DummyResponse(),
        )

        notifier = DiscordNotifier({"enabled": True, "webhook_url": "https://example.com"})

        long_message = "a" * 2001

        assert notifier.send_notification(long_message) is True
        request = open_url_mock.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        assert len(payload["content"]) == 2000
        assert payload["content"] != long_message

    def test_should_return_false_on_non_2xx_status(self, mocker):
        """Test non-2xx response returns False."""
        mocker.patch(
            "xnetvn_monitord.notifiers.discord_notifier.open_url",
            return_value=DummyResponse(status=500),
        )

        notifier = DiscordNotifier({"enabled": True, "webhook_url": "https://example.com"})

        assert notifier.send_notification("test") is False

    def test_should_return_false_on_url_error(self, mocker):
        """Test URL error returns False."""
        mocker.patch(
            "xnetvn_monitord.notifiers.discord_notifier.open_url",
            side_effect=URLError("down"),
        )

        notifier = DiscordNotifier({"enabled": True, "webhook_url": "https://example.com"})

        assert notifier.send_notification("test") is False

    def test_should_log_sanitized_target_on_url_error(self, mocker, caplog):
        """Test Discord errors log redacted endpoint context."""
        caplog.set_level(logging.ERROR)
        mocker.patch(
            "xnetvn_monitord.notifiers.discord_notifier.open_url",
            side_effect=URLError("down"),
        )

        notifier = DiscordNotifier(
            {
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/secret-token",
            }
        )

        assert notifier.send_notification("test") is False
        assert "https://discord.com" in caplog.text
        assert "secret-token" not in caplog.text

    def test_should_skip_live_test_when_disabled(self):
        """Test connection check skips live test when disabled."""
        notifier = DiscordNotifier({"enabled": True, "webhook_url": "https://example.com"})
        assert notifier.test_connection() is True

    def test_should_return_false_when_connection_disabled(self):
        """Test test_connection returns False when disabled."""
        notifier = DiscordNotifier({"enabled": False})
        assert notifier.test_connection() is False

    def test_should_return_false_when_connection_missing_webhook(self):
        """Test test_connection returns False when webhook missing."""
        notifier = DiscordNotifier({"enabled": True})
        assert notifier.test_connection() is False

    def test_should_run_live_test_when_enabled(self, mocker):
        """Test live test executes when test_on_startup is enabled."""
        mocker.patch("xnetvn_monitord.notifiers.discord_notifier.open_url", return_value=DummyResponse())

        notifier = DiscordNotifier(
            {
                "enabled": True,
                "webhook_url": "https://example.com",
                "test_on_startup": True,
            }
        )

        assert notifier.test_connection() is True

    def test_should_use_unverified_ssl_context_when_disabled(self, mocker):
        """Test SSL verification disabled uses default context with verification disabled."""
        context_mock = mocker.patch(
            "ssl.create_default_context",
            return_value=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
        )
        open_url_mock = mocker.patch(
            "xnetvn_monitord.notifiers.discord_notifier.open_url",
            return_value=DummyResponse(),
        )

        notifier = DiscordNotifier(
            {
                "enabled": True,
                "webhook_url": "https://example.com",
                "verify_ssl": False,
            }
        )

        assert notifier.send_notification("test") is True
        context_mock.assert_called_once()
        # Verify that the SSL context is passed to open_url
        assert open_url_mock.call_args[0][2] is not None
        # Verify that SSL verification was disabled on the context
        context = context_mock.return_value
        assert context.check_hostname is False
        assert context.verify_mode == ssl.CERT_NONE

    def test_should_return_false_on_proxy_error(self, mocker):
        """Test proxy configuration errors return False."""
        mocker.patch(
            "xnetvn_monitord.notifiers.discord_notifier.open_url",
            side_effect=ProxyConfigurationError("proxy error"),
        )

        notifier = DiscordNotifier(
            {
                "enabled": True,
                "webhook_url": "https://example.com",
                "proxy": {"enabled": True, "uri": "http://127.0.0.1:8080"},
            }
        )

        assert notifier.send_notification("test") is False
