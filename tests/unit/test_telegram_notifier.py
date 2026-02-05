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

"""Unit tests for TelegramNotifier."""

import json
import urllib.error
import urllib.parse

from xnetvn_monitord.notifiers.telegram_notifier import TelegramNotifier


class DummyResponse:
    """Dummy response object for urlopen context manager."""

    def __init__(self, payload: dict):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestTelegramNotifierSendNotification:
    """Tests for send_notification."""

    def test_should_return_false_when_disabled(self):
        """Test disabled notifier returns False."""
        notifier = TelegramNotifier({"enabled": False})
        assert notifier.send_notification("message") is False

    def test_should_return_false_when_missing_token(self):
        """Test missing token returns False."""
        notifier = TelegramNotifier(
            {"enabled": True, "bot_token": "", "chat_ids": ["1"]}
        )
        assert notifier.send_notification("message") is False

    def test_should_return_false_when_no_chat_ids(self):
        """Test missing chat IDs returns False."""
        notifier = TelegramNotifier(
            {"enabled": True, "bot_token": "token", "chat_ids": []}
        )
        assert notifier.send_notification("message") is False

    def test_should_send_to_multiple_chat_ids(self, mocker):
        """Test send notification to multiple chat IDs."""
        notifier = TelegramNotifier(
            {
                "enabled": True,
                "bot_token": "token",
                "chat_ids": ["1", "2"],
            }
        )

        mocker.patch.object(notifier, "_send_message", side_effect=[True, False])

        assert notifier.send_notification("message") is True

    def test_should_return_false_when_all_sends_fail(self, mocker):
        """Test send_notification returns False when all sends fail."""
        notifier = TelegramNotifier(
            {
                "enabled": True,
                "bot_token": "token",
                "chat_ids": ["1", "2"],
            }
        )

        mocker.patch.object(notifier, "_send_message", return_value=False)

        assert notifier.send_notification("message") is False


class TestTelegramNotifierSendMessage:
    """Tests for _send_message."""

    def test_should_return_true_on_success(self, mocker):
        """Test successful API response."""
        mocker.patch(
            "urllib.request.urlopen",
            return_value=DummyResponse({"ok": True, "result": {"message_id": 1}}),
        )

        notifier = TelegramNotifier(
            {
                "enabled": True,
                "bot_token": "token",
                "chat_ids": ["1"],
            }
        )

        assert notifier._send_message("1", "message") is True

    def test_should_return_false_on_api_error(self, mocker):
        """Test API returns ok=false."""
        mocker.patch(
            "urllib.request.urlopen",
            return_value=DummyResponse({"ok": False, "description": "fail"}),
        )

        notifier = TelegramNotifier(
            {
                "enabled": True,
                "bot_token": "token",
                "chat_ids": ["1"],
            }
        )

        assert notifier._send_message("1", "message") is False

    def test_should_handle_url_error(self, mocker):
        """Test URL error handling."""
        mocker.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("fail"))

        notifier = TelegramNotifier(
            {
                "enabled": True,
                "bot_token": "token",
                "chat_ids": ["1"],
            }
        )

        assert notifier._send_message("1", "message") is False

    def test_should_handle_generic_exception(self, mocker):
        """Test generic exception handling in send message."""
        mocker.patch("urllib.request.urlopen", side_effect=ValueError("fail"))

        notifier = TelegramNotifier(
            {
                "enabled": True,
                "bot_token": "token",
                "chat_ids": ["1"],
            }
        )

        assert notifier._send_message("1", "message") is False

    def test_should_include_message_thread_id(self, mocker):
        """Test message thread id is included in send payload."""
        captured = {}

        def fake_urlopen(request, timeout):
            captured["data"] = request.data
            return DummyResponse({"ok": True, "result": {"message_id": 1}})

        mocker.patch("urllib.request.urlopen", side_effect=fake_urlopen)

        notifier = TelegramNotifier(
            {
                "enabled": True,
                "bot_token": "token",
                "chat_ids": ["1"],
            }
        )

        assert notifier._send_message("-100123", "message", 456) is True

        parsed = urllib.parse.parse_qs(captured["data"].decode("utf-8"))
        assert parsed["message_thread_id"] == ["456"]


class TestTelegramNotifierFormatting:
    """Tests for message formatting."""

    def test_should_escape_html(self):
        """Test HTML escaping."""
        notifier = TelegramNotifier(
            {"enabled": True, "bot_token": "token", "chat_ids": ["1"]}
        )
        assert notifier._escape_html("<tag>&") == "&lt;tag&gt;&amp;"

    def test_should_format_service_alert_html(self):
        """Test HTML formatting for service alert."""
        notifier = TelegramNotifier(
            {
                "enabled": True,
                "bot_token": "token",
                "chat_ids": ["1"],
                "parse_mode": "HTML",
            }
        )

        message = notifier._format_service_alert("nginx", "down", "details")
        assert "<b>Service Alert</b>" in message

    def test_should_format_resource_alert_markdown(self):
        """Test Markdown formatting for resource alert."""
        notifier = TelegramNotifier(
            {
                "enabled": True,
                "bot_token": "token",
                "chat_ids": ["1"],
                "parse_mode": "Markdown",
            }
        )

        message = notifier._format_resource_alert("cpu", {"load": 1})
        assert "*Resource Alert*" in message

    def test_should_format_service_alert_markdown(self):
        """Test Markdown formatting for service alert."""
        notifier = TelegramNotifier(
            {
                "enabled": True,
                "bot_token": "token",
                "chat_ids": ["1"],
                "parse_mode": "Markdown",
            }
        )

        message = notifier._format_service_alert("nginx", "down", "details")
        assert "*Service Alert*" in message

    def test_should_format_resource_alert_html(self):
        """Test HTML formatting for resource alert."""
        notifier = TelegramNotifier(
            {
                "enabled": True,
                "bot_token": "token",
                "chat_ids": ["1"],
                "parse_mode": "HTML",
            }
        )

        message = notifier._format_resource_alert("disk", {"free": 5})
        assert "<b>Resource Alert</b>" in message

    def test_should_convert_nested_dict_to_string(self):
        """Test dictionary formatting handles nested structures."""
        notifier = TelegramNotifier(
            {"enabled": True, "bot_token": "token", "chat_ids": ["1"]}
        )

        data = {"a": {"b": 1}, "list": ["item", {"c": 2}]}
        result = notifier._dict_to_string(data)

        assert "a:" in result
        assert "b: 1" in result
        assert "- item" in result
        assert "c: 2" in result


class TestTelegramNotifierChatTargetParsing:
    """Tests for chat target parsing."""

    def test_should_parse_chat_target_without_topic(self):
        """Test chat id without topic id."""
        assert TelegramNotifier._parse_chat_target("123") == ("123", None)

    def test_should_parse_chat_target_with_topic(self):
        """Test chat id with topic id."""
        assert TelegramNotifier._parse_chat_target("-100123_456") == ("-100123", 456)

    def test_should_ignore_invalid_topic_id(self, caplog):
        """Test invalid topic id returns base id only."""
        assert TelegramNotifier._parse_chat_target("123_abc") == ("123", None)
        assert any("Invalid Telegram topic id" in record.message for record in caplog.records)


class TestTelegramNotifierConnection:
    """Tests for connection checks."""

    def test_should_return_false_when_disabled(self):
        """Test disabled notifier returns False for connection test."""
        notifier = TelegramNotifier({"enabled": False})
        assert notifier.test_connection() is False

    def test_should_return_false_when_missing_token(self):
        """Test missing token returns False for connection test."""
        notifier = TelegramNotifier(
            {"enabled": True, "bot_token": "", "chat_ids": ["1"]}
        )
        assert notifier.test_connection() is False

    def test_should_return_true_on_success(self, mocker):
        """Test successful connection check."""
        mocker.patch(
            "urllib.request.urlopen",
            return_value=DummyResponse({"ok": True, "result": {"username": "bot"}}),
        )

        notifier = TelegramNotifier(
            {"enabled": True, "bot_token": "token", "chat_ids": ["1"]}
        )

        assert notifier.test_connection() is True

    def test_should_return_false_on_api_error(self, mocker):
        """Test connection check API error."""
        mocker.patch(
            "urllib.request.urlopen",
            return_value=DummyResponse({"ok": False, "description": "fail"}),
        )

        notifier = TelegramNotifier(
            {"enabled": True, "bot_token": "token", "chat_ids": ["1"]}
        )

        assert notifier.test_connection() is False