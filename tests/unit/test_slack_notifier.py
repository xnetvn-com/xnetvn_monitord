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

"""Unit tests for SlackNotifier."""

import ssl
import urllib.error

from xnetvn_monitord.notifiers.slack_notifier import SlackNotifier


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


class TestSlackNotifier:
    """Tests for SlackNotifier."""

    def test_should_return_false_when_disabled(self):
        """Test disabled notifier returns False."""
        notifier = SlackNotifier({"enabled": False})
        assert notifier.send_notification("test") is False

    def test_should_return_false_when_missing_webhook(self):
        """Test missing webhook URL returns False."""
        notifier = SlackNotifier({"enabled": True})
        assert notifier.send_notification("test") is False

    def test_should_include_optional_payload_fields(self, mocker):
        """Test optional payload fields are included and overridden."""
        payloads = []

        def capture_payload(payload):
            payloads.append(payload)
            return True

        mocker.patch.object(SlackNotifier, "_post_payload", side_effect=capture_payload)

        notifier = SlackNotifier(
            {
                "enabled": True,
                "webhook_url": "https://example.com",
                "channel": "#alerts",
                "username": "bot",
                "icon_emoji": ":bell:",
                "icon_url": "https://example.com/icon.png",
            }
        )

        assert notifier.send_notification("test", payload={"text": "override"}) is True
        assert payloads[0]["channel"] == "#alerts"
        assert payloads[0]["username"] == "bot"
        assert payloads[0]["icon_emoji"] == ":bell:"
        assert payloads[0]["icon_url"] == "https://example.com/icon.png"
        assert payloads[0]["text"] == "override"

    def test_should_send_notification(self, mocker):
        """Test successful Slack notification."""
        mocker.patch("urllib.request.urlopen", return_value=DummyResponse())

        notifier = SlackNotifier({"enabled": True, "webhook_url": "https://example.com"})

        assert notifier.send_notification("test") is True

    def test_should_return_false_on_non_2xx_status(self, mocker):
        """Test non-2xx response returns False."""
        mocker.patch("urllib.request.urlopen", return_value=DummyResponse(status=500))

        notifier = SlackNotifier({"enabled": True, "webhook_url": "https://example.com"})

        assert notifier.send_notification("test") is False

    def test_should_return_false_on_url_error(self, mocker):
        """Test URL error returns False."""
        mocker.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down"))

        notifier = SlackNotifier({"enabled": True, "webhook_url": "https://example.com"})

        assert notifier.send_notification("test") is False

    def test_should_skip_live_test_when_disabled(self):
        """Test connection check skips live test when disabled."""
        notifier = SlackNotifier({"enabled": True, "webhook_url": "https://example.com"})
        assert notifier.test_connection() is True

    def test_should_return_false_when_connection_disabled(self):
        """Test test_connection returns False when disabled."""
        notifier = SlackNotifier({"enabled": False})
        assert notifier.test_connection() is False

    def test_should_return_false_when_connection_missing_webhook(self):
        """Test test_connection returns False when webhook missing."""
        notifier = SlackNotifier({"enabled": True})
        assert notifier.test_connection() is False

    def test_should_run_live_test_when_enabled(self, mocker):
        """Test live test executes when test_on_startup is enabled."""
        mocker.patch("urllib.request.urlopen", return_value=DummyResponse())

        notifier = SlackNotifier(
            {
                "enabled": True,
                "webhook_url": "https://example.com",
                "test_on_startup": True,
            }
        )

        assert notifier.test_connection() is True

    def test_should_use_unverified_ssl_context_when_disabled(self, mocker):
        """Test SSL verification disabled uses unverified context."""
        context_mock = mocker.patch(
            "ssl._create_unverified_context",
            return_value=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
        )
        urlopen_mock = mocker.patch("urllib.request.urlopen", return_value=DummyResponse())

        notifier = SlackNotifier(
            {
                "enabled": True,
                "webhook_url": "https://example.com",
                "verify_ssl": False,
            }
        )

        assert notifier.send_notification("test") is True
        context_mock.assert_called_once()
        assert urlopen_mock.call_args.kwargs.get("context") is not None
