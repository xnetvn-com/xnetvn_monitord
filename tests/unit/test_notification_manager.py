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

"""Unit tests for NotificationManager."""

from xnetvn_monitord.notifiers import NotificationManager


class TestNotificationManagerInitialization:
    """Tests for NotificationManager initialization."""

    def test_should_disable_when_config_disabled(self):
        """Test manager disabled flag when config disables notifications."""
        manager = NotificationManager({"enabled": False})
        assert manager.enabled is False
        assert manager.get_enabled_channels() == []

    def test_should_initialize_enabled_channels(self, mocker):
        """Test enabled channel initialization based on config."""
        email_mock = mocker.patch("xnetvn_monitord.notifiers.EmailNotifier")
        telegram_mock = mocker.patch("xnetvn_monitord.notifiers.TelegramNotifier")
        webhook_mock = mocker.patch("xnetvn_monitord.notifiers.WebhookNotifier")
        slack_mock = mocker.patch("xnetvn_monitord.notifiers.SlackNotifier")
        discord_mock = mocker.patch("xnetvn_monitord.notifiers.DiscordNotifier")

        config = {
            "enabled": True,
            "email": {"enabled": True},
            "telegram": {"enabled": True},
            "webhook": {"enabled": True},
            "slack": {"enabled": True},
            "discord": {"enabled": True},
        }

        manager = NotificationManager(config)

        email_mock.assert_called_once()
        telegram_mock.assert_called_once()
        webhook_mock.assert_called_once()
        slack_mock.assert_called_once()
        discord_mock.assert_called_once()
        assert set(manager.get_enabled_channels()) == {
            "email",
            "telegram",
            "webhook",
            "slack",
            "discord",
        }


class TestNotificationManagerRateLimit:
    """Tests for rate limiting logic."""

    def test_should_allow_when_rate_limit_disabled(self):
        """Test rate limit bypass when disabled."""
        manager = NotificationManager(
            {
                "enabled": True,
                "rate_limit": {"enabled": False},
            }
        )
        assert manager._check_rate_limit("service_test") is True

    def test_should_block_when_min_interval_not_met(self, mocker):
        """Test rate limit enforcement by minimum interval."""
        mocker.patch("xnetvn_monitord.notifiers.time.time", return_value=1000.0)

        manager = NotificationManager(
            {
                "enabled": True,
                "rate_limit": {
                    "enabled": True,
                    "min_interval": 300,
                    "max_per_hour": 20,
                },
            }
        )
        manager.notification_history["service_test"] = [950.0]

        assert manager._check_rate_limit("service_test") is False

    def test_should_block_when_max_per_hour_exceeded(self, mocker):
        """Test rate limit enforcement by max per hour."""
        mocker.patch("xnetvn_monitord.notifiers.time.time", return_value=1000.0)

        manager = NotificationManager(
            {
                "enabled": True,
                "rate_limit": {
                    "enabled": True,
                    "min_interval": 1,
                    "max_per_hour": 2,
                },
            }
        )
        manager.notification_history["service_test"] = [100.0, 200.0, 300.0]

        assert manager._check_rate_limit("service_test") is False

    def test_should_cleanup_old_history_entries(self, mocker):
        """Test cleanup of old rate limit entries."""
        mocker.patch("xnetvn_monitord.notifiers.time.time", return_value=5000.0)

        manager = NotificationManager(
            {
                "enabled": True,
                "rate_limit": {
                    "enabled": True,
                    "min_interval": 1,
                    "max_per_hour": 20,
                },
            }
        )
        manager.notification_history["service_test"] = [100.0, 200.0, 300.0]

        assert manager._check_rate_limit("service_test") is True
        assert manager.notification_history["service_test"] == []


class TestNotificationManagerContentFilter:
    """Tests for content filtering."""

    def test_should_filter_sensitive_content(self):
        """Test sensitive content filtering."""
        manager = NotificationManager(
            {
                "enabled": True,
                "content_filter": {
                    "enabled": True,
                    "redact_patterns": [r"password=\S+"],
                    "redact_replacement": "[REDACTED]",
                },
            }
        )

        filtered = manager._filter_sensitive_content("password=secret")
        assert filtered == "[REDACTED]"

    def test_should_warn_on_invalid_filter_pattern(self, caplog):
        """Test invalid filter pattern handling."""
        manager = NotificationManager(
            {
                "enabled": True,
                "content_filter": {
                    "enabled": True,
                    "redact_patterns": ["["],
                    "redact_replacement": "[REDACTED]",
                },
            }
        )

        result = manager._filter_sensitive_content("test")

        assert result == "test"
        assert any("Error applying content filter pattern" in record.message for record in caplog.records)

    def test_should_filter_nested_dict(self):
        """Test recursive dictionary filtering."""
        manager = NotificationManager(
            {
                "enabled": True,
                "content_filter": {
                    "enabled": True,
                    "redact_patterns": [r"secret"],
                    "redact_replacement": "[REDACTED]",
                },
            }
        )

        payload = {"token": "secret", "nested": {"value": "secret"}}
        filtered = manager._filter_dict_content(payload)

        assert filtered["token"] == "[REDACTED]"
        assert filtered["nested"]["value"] == "[REDACTED]"

    def test_should_return_value_when_not_dict(self):
        """Test filter dictionary returns non-dict values unchanged."""
        manager = NotificationManager({"enabled": True})

        assert manager._filter_dict_content("value") == "value"


class TestNotificationManagerSending:
    """Tests for sending notifications."""

    def test_should_send_event_notifications(self, mocker):
        """Test event notifications across channels."""
        email_instance = mocker.Mock()
        email_instance.send_notification.return_value = True

        telegram_instance = mocker.Mock()
        telegram_instance.send_notification.return_value = True

        webhook_instance = mocker.Mock()
        webhook_instance.send_notification.return_value = True

        slack_instance = mocker.Mock()
        slack_instance.send_notification.return_value = True

        discord_instance = mocker.Mock()
        discord_instance.send_notification.return_value = True

        mocker.patch(
            "xnetvn_monitord.notifiers.EmailNotifier",
            return_value=email_instance,
        )
        mocker.patch(
            "xnetvn_monitord.notifiers.TelegramNotifier",
            return_value=telegram_instance,
        )
        mocker.patch(
            "xnetvn_monitord.notifiers.WebhookNotifier",
            return_value=webhook_instance,
        )
        mocker.patch(
            "xnetvn_monitord.notifiers.SlackNotifier",
            return_value=slack_instance,
        )
        mocker.patch(
            "xnetvn_monitord.notifiers.DiscordNotifier",
            return_value=discord_instance,
        )

        manager = NotificationManager(
            {
                "enabled": True,
                "rate_limit": {"enabled": False},
                "content_filter": {"enabled": False},
                "email": {"enabled": True},
                "telegram": {"enabled": True},
                "webhook": {"enabled": True},
                "slack": {"enabled": True},
                "discord": {"enabled": True},
            }
        )

        event = {
            "event_type": "service_down",
            "timestamp": 1700000000.0,
            "severity": "high",
            "service": {"name": "nginx", "status": "down"},
            "details": "Service not responding",
        }

        success = manager.notify_event(event)

        assert success is True
        email_instance.send_notification.assert_called_once()
        telegram_instance.send_notification.assert_called_once()
        webhook_instance.send_notification.assert_called_once()
        slack_instance.send_notification.assert_called_once()
        discord_instance.send_notification.assert_called_once()

    def test_should_send_action_result_notifications(self, mocker):
        """Test action result notifications."""
        email_instance = mocker.Mock()
        email_instance.send_notification.return_value = True

        mocker.patch(
            "xnetvn_monitord.notifiers.EmailNotifier",
            return_value=email_instance,
        )

        manager = NotificationManager(
            {
                "enabled": True,
                "rate_limit": {"enabled": False},
                "content_filter": {"enabled": False},
                "email": {"enabled": True},
            }
        )

        report = {
            "event_type": "service_recovery",
            "timestamp": 1700000100.0,
            "severity": "info",
            "service": {"name": "nginx", "status": "restarted"},
            "action": {"action": "restart_service", "success": True},
        }

        success = manager.notify_action_result(report)

        assert success is True
        email_instance.send_notification.assert_called_once()

    def test_should_send_custom_message(self, mocker):
        """Test custom message notification."""
        email_instance = mocker.Mock()
        email_instance.send_notification.return_value = True

        telegram_instance = mocker.Mock()
        telegram_instance.send_notification.return_value = True

        slack_instance = mocker.Mock()
        slack_instance.send_notification.return_value = True

        discord_instance = mocker.Mock()
        discord_instance.send_notification.return_value = True

        webhook_instance = mocker.Mock()
        webhook_instance.send_notification.return_value = True

        mocker.patch(
            "xnetvn_monitord.notifiers.EmailNotifier",
            return_value=email_instance,
        )
        mocker.patch(
            "xnetvn_monitord.notifiers.TelegramNotifier",
            return_value=telegram_instance,
        )
        mocker.patch(
            "xnetvn_monitord.notifiers.SlackNotifier",
            return_value=slack_instance,
        )
        mocker.patch(
            "xnetvn_monitord.notifiers.DiscordNotifier",
            return_value=discord_instance,
        )
        mocker.patch(
            "xnetvn_monitord.notifiers.WebhookNotifier",
            return_value=webhook_instance,
        )

        manager = NotificationManager(
            {
                "enabled": True,
                "content_filter": {"enabled": False},
                "email": {"enabled": True},
                "telegram": {"enabled": True},
                "slack": {"enabled": True},
                "discord": {"enabled": True},
                "webhook": {"enabled": True},
            }
        )

        success = manager.notify_custom_message("Subject", "Body")

        assert success is True
        email_instance.send_notification.assert_called_once()
        telegram_instance.send_notification.assert_called_once()
        slack_instance.send_notification.assert_called_once()
        discord_instance.send_notification.assert_called_once()
        webhook_instance.send_notification.assert_called_once()

    def test_should_not_send_when_rate_limited(self, mocker):
        """Test notify_event respects rate limits."""
        mocker.patch("xnetvn_monitord.notifiers.time.time", return_value=1000.0)

        email_instance = mocker.Mock()
        email_instance.send_notification.return_value = True
        mocker.patch(
            "xnetvn_monitord.notifiers.EmailNotifier",
            return_value=email_instance,
        )

        manager = NotificationManager(
            {
                "enabled": True,
                "rate_limit": {
                    "enabled": True,
                    "min_interval": 300,
                    "max_per_hour": 20,
                },
                "content_filter": {"enabled": False},
                "email": {"enabled": True},
            }
        )
        manager.notification_history["email:event_service_down"] = [950.0]

        success = manager.notify_event(
            {
                "event_type": "service_down",
                "timestamp": 1000.0,
                "severity": "high",
                "service": {"name": "nginx", "status": "down"},
            }
        )

        assert success is False
        email_instance.send_notification.assert_not_called()

    def test_should_handle_custom_message_exceptions(self, mocker):
        """Test custom message handling when channel errors occur."""
        email_instance = mocker.Mock()
        email_instance.send_notification.side_effect = RuntimeError("fail")

        telegram_instance = mocker.Mock()
        telegram_instance.send_notification.return_value = False

        slack_instance = mocker.Mock()
        slack_instance.send_notification.return_value = False

        mocker.patch(
            "xnetvn_monitord.notifiers.EmailNotifier",
            return_value=email_instance,
        )
        mocker.patch(
            "xnetvn_monitord.notifiers.TelegramNotifier",
            return_value=telegram_instance,
        )
        mocker.patch(
            "xnetvn_monitord.notifiers.SlackNotifier",
            return_value=slack_instance,
        )

        manager = NotificationManager(
            {
                "enabled": True,
                "content_filter": {"enabled": False},
                "email": {"enabled": True},
                "telegram": {"enabled": True},
                "slack": {"enabled": True},
            }
        )

        assert manager.notify_custom_message("Subject", "Body") is False


class TestNotificationManagerReports:
    """Tests for event/action report formatting and routing."""

    def test_should_filter_by_severity(self, mocker):
        """Test channel severity filtering prevents low severity reports."""
        email_instance = mocker.Mock()
        email_instance.send_notification.return_value = True

        mocker.patch(
            "xnetvn_monitord.notifiers.EmailNotifier",
            return_value=email_instance,
        )

        manager = NotificationManager(
            {
                "enabled": True,
                "email": {"enabled": True, "min_severity": "high"},
                "rate_limit": {"enabled": False},
                "content_filter": {"enabled": False},
            }
        )

        event = {
            "event_type": "resource_threshold",
            "timestamp": 1700000000.0,
            "severity": "info",
        }

        assert manager.notify_event(event) is False
        email_instance.send_notification.assert_not_called()

    def test_should_apply_channel_rate_limit_override(self, mocker):
        """Test per-channel rate limit overrides global config."""
        mocker.patch("xnetvn_monitord.notifiers.time.time", return_value=1000.0)

        email_instance = mocker.Mock()
        email_instance.send_notification.return_value = True

        mocker.patch(
            "xnetvn_monitord.notifiers.EmailNotifier",
            return_value=email_instance,
        )

        manager = NotificationManager(
            {
                "enabled": True,
                "rate_limit": {"enabled": False},
                "email": {
                    "enabled": True,
                    "rate_limit": {"enabled": True, "min_interval": 300, "max_per_hour": 1},
                },
            }
        )

        manager.notification_history["email:event_service_down"] = [950.0]

        event = {
            "event_type": "service_down",
            "timestamp": 1000.0,
            "severity": "high",
        }

        assert manager.notify_event(event) is False
        email_instance.send_notification.assert_not_called()

    def test_should_format_report_html(self, mocker):
        """Test HTML report formatting for email."""
        email_instance = mocker.Mock()
        email_instance.send_notification.return_value = True

        mocker.patch(
            "xnetvn_monitord.notifiers.EmailNotifier",
            return_value=email_instance,
        )

        manager = NotificationManager(
            {
                "enabled": True,
                "rate_limit": {"enabled": False},
                "email": {"enabled": True, "template": {"format": "html"}},
            }
        )

        event = {
            "event_type": "service_down",
            "timestamp": 1700000000.0,
            "severity": "high",
            "service": {"name": "nginx", "status": "down"},
            "system_stats": {"cpu": {"load_1min": 5.0}},
        }

        assert manager.notify_event(event) is True
        email_instance.send_notification.assert_called_once()
        args, _ = email_instance.send_notification.call_args
        assert args[2] is True

    def test_should_strip_system_stats_for_channel(self, mocker):
        """Test channel config can exclude system stats."""
        telegram_instance = mocker.Mock()
        telegram_instance.send_notification.return_value = True

        mocker.patch(
            "xnetvn_monitord.notifiers.TelegramNotifier",
            return_value=telegram_instance,
        )

        manager = NotificationManager(
            {
                "enabled": True,
                "rate_limit": {"enabled": False},
                "telegram": {"enabled": True, "include_system_stats": False},
            }
        )

        event = {
            "event_type": "resource_threshold",
            "timestamp": 1700000000.0,
            "severity": "high",
            "system_stats": {"cpu": {"load_1min": 2.0}},
        }

        assert manager.notify_event(event) is True
        sent_message = telegram_instance.send_notification.call_args.args[0]
        assert "System Stats" not in sent_message

    def test_should_build_legacy_events(self, mocker):
        """Test legacy event builders delegate to notify_event."""
        manager = NotificationManager({"enabled": True})
        notify_mock = mocker.patch.object(manager, "notify_event", return_value=True)

        assert manager.notify_service_failure("nginx", "down", "details") is True
        assert manager.notify_resource_alert("cpu", {"usage": 95}) is True

        assert notify_mock.call_count == 2
        first_event = notify_mock.call_args_list[0].args[0]
        second_event = notify_mock.call_args_list[1].args[0]
        assert first_event["event_type"] == "service_alert"
        assert second_event["event_type"] == "resource_alert"

    def test_should_test_all_channels(self, mocker):
        """Test channel connection checks."""
        email_instance = mocker.Mock()
        email_instance.test_connection.return_value = True

        telegram_instance = mocker.Mock()
        telegram_instance.test_connection.return_value = False

        webhook_instance = mocker.Mock()
        webhook_instance.test_connection.return_value = True

        slack_instance = mocker.Mock()
        slack_instance.test_connection.return_value = True

        discord_instance = mocker.Mock()
        discord_instance.test_connection.return_value = True

        mocker.patch(
            "xnetvn_monitord.notifiers.EmailNotifier",
            return_value=email_instance,
        )
        mocker.patch(
            "xnetvn_monitord.notifiers.TelegramNotifier",
            return_value=telegram_instance,
        )
        mocker.patch(
            "xnetvn_monitord.notifiers.WebhookNotifier",
            return_value=webhook_instance,
        )
        mocker.patch(
            "xnetvn_monitord.notifiers.SlackNotifier",
            return_value=slack_instance,
        )
        mocker.patch(
            "xnetvn_monitord.notifiers.DiscordNotifier",
            return_value=discord_instance,
        )

        manager = NotificationManager(
            {
                "enabled": True,
                "email": {"enabled": True},
                "telegram": {"enabled": True},
                "webhook": {"enabled": True},
                "slack": {"enabled": True},
                "discord": {"enabled": True},
            }
        )

        results = manager.test_all_channels()

        assert results == {
            "email": True,
            "telegram": False,
            "webhook": True,
            "slack": True,
            "discord": True,
        }

    def test_should_validate_channels_without_live_test_message(self, mocker):
        """Test startup validation can skip live test messages for enabled channels."""
        email_instance = mocker.Mock()
        email_instance.test_connection.return_value = True

        telegram_instance = mocker.Mock()
        telegram_instance.test_connection.return_value = True

        webhook_instance = mocker.Mock()
        webhook_instance.test_connection.return_value = True

        slack_instance = mocker.Mock()
        slack_instance.test_connection.return_value = True

        discord_instance = mocker.Mock()
        discord_instance.test_connection.return_value = True

        mocker.patch("xnetvn_monitord.notifiers.EmailNotifier", return_value=email_instance)
        mocker.patch("xnetvn_monitord.notifiers.TelegramNotifier", return_value=telegram_instance)
        mocker.patch("xnetvn_monitord.notifiers.WebhookNotifier", return_value=webhook_instance)
        mocker.patch("xnetvn_monitord.notifiers.SlackNotifier", return_value=slack_instance)
        mocker.patch("xnetvn_monitord.notifiers.DiscordNotifier", return_value=discord_instance)

        manager = NotificationManager(
            {
                "enabled": True,
                "email": {"enabled": True},
                "telegram": {"enabled": True},
                "webhook": {"enabled": True},
                "slack": {"enabled": True},
                "discord": {"enabled": True},
            }
        )

        results = manager.test_all_channels(send_test_message=False)

        assert results == {
            "email": True,
            "telegram": True,
            "webhook": True,
            "slack": True,
            "discord": True,
        }
        email_instance.test_connection.assert_called_once_with(send_test_message=False)
        telegram_instance.test_connection.assert_called_once_with(send_test_message=False)
        webhook_instance.test_connection.assert_called_once_with(send_test_message=False)
        slack_instance.test_connection.assert_called_once_with(send_test_message=False)
        discord_instance.test_connection.assert_called_once_with(send_test_message=False)


class TestNotificationManagerHelpers:
    """Tests for NotificationManager helper methods."""

    def test_should_return_false_when_manager_disabled(self):
        """Test disabled manager returns False for notification methods."""
        manager = NotificationManager({"enabled": False})

        assert manager.notify_event({"event_type": "test"}) is False
        assert manager.notify_action_result({"event_type": "test"}) is False
        assert manager.notify_custom_message("Subject", "Body") is False

    def test_should_build_subject_from_title(self):
        """Test custom title overrides default subject."""
        manager = NotificationManager({"enabled": True})
        report = {"title": "Custom Title", "event_type": "x"}

        assert manager._build_subject("event", report) == "Custom Title"

    def test_should_resolve_hostname_from_report(self):
        """Test report hostname overrides manager hostname."""
        manager = NotificationManager({"enabled": True})
        report = {"hostname": "test-host"}

        assert manager._resolve_hostname(report) == "test-host"

    def test_should_prepend_hostname_when_available(self):
        """Test hostname prefix is added to message body."""
        message = NotificationManager._prepend_hostname("Body", "test-host")

        assert message.startswith("Hostname: test-host")

    def test_should_format_timestamp_when_missing(self):
        """Test missing timestamp returns N/A."""
        manager = NotificationManager({"enabled": True})

        assert manager._format_timestamp(None) == "N/A"

    def test_should_stringify_nested_lists(self):
        """Test dict to string handles nested lists and dicts."""
        manager = NotificationManager({"enabled": True})
        payload = {"items": [{"name": "alpha", "count": 1234}, "beta", 9876.5]}

        text = manager._dict_to_string(payload)

        assert "items:" in text
        assert "name: alpha" in text
        assert "count: 1,234" in text
        assert "- beta" in text
        assert "- 9,876.5" in text

    def test_should_filter_sensitive_content_with_invalid_pattern(self, caplog):
        """Test invalid regex pattern is handled gracefully."""
        manager = NotificationManager(
            {
                "enabled": True,
                "content_filter": {
                    "enabled": True,
                    "redact_patterns": ["["],
                    "redact_replacement": "[REDACTED]",
                },
            }
        )

        filtered = manager._filter_sensitive_content("token=abc")

        assert filtered == "token=abc"
        assert any("Error applying content filter pattern" in record.message for record in caplog.records)

    def test_should_prepare_report_for_channel_exclusions(self):
        """Test report payload excludes optional sections per channel config."""
        manager = NotificationManager({"enabled": True})
        report = {
            "details": "detail",
            "action": {"name": "restart"},
            "system_stats": {"cpu": {"load_1min": 1.0}},
        }
        channel_config = {
            "include_system_stats": False,
            "include_action_details": False,
            "include_details": False,
        }

        prepared = manager._prepare_report_for_channel(report, channel_config)

        assert "details" not in prepared
        assert "action" not in prepared
        assert "system_stats" not in prepared

    def test_should_strip_network_interfaces_for_chat_channels(self):
        """Test Telegram, Slack, and Discord reports omit per-interface network stats."""
        manager = NotificationManager({"enabled": True})
        report = {
            "system_stats": {
                "cpu": {"load_1min": 1.0},
                "network": {
                    "total": {"bytes_sent": 100, "bytes_recv": 200},
                    "interfaces": {
                        "eth0": {"bytes_sent": 10, "bytes_recv": 20},
                    },
                },
            },
        }

        prepared = manager._prepare_report_for_channel(report, {}, "telegram")

        assert "interfaces" not in prepared["system_stats"]["network"]
        assert prepared["system_stats"]["network"]["total"] == {
            "bytes_sent": 100,
            "bytes_recv": 200,
        }
        assert prepared["system_stats"]["cpu"] == {"load_1min": 1.0}

    def test_should_build_webhook_payload(self):
        """Test webhook payload wrapper."""
        manager = NotificationManager({"enabled": True})
        payload = manager._build_webhook_payload("event", {"event_type": "test"})

        assert payload["report_type"] == "event"
        assert payload["report"]["event_type"] == "test"

    def test_should_format_report_plain_with_sections(self):
        """Test plain report formatting includes sections."""
        manager = NotificationManager({"enabled": True})
        report = {
            "event_type": "resource_recovery",
            "timestamp": 1700000000.0,
            "severity": "high",
            "hostname": "test-host",
            "resource": {"type": "cpu", "iterations": 1234, "usage": 98.5},
            "action": {"name": "restart", "attempts": 2},
            "details": "Recovered",
            "system_stats": {"cpu": {"load_1min": 1234567.89}, "uptime_seconds": 9876543},
        }

        text = manager._format_report_plain("action", report)

        assert "Resource:" in text
        assert "Action:" in text
        assert "Details:" in text
        assert "System Stats:" in text
        assert "Hostname: test-host" in text
        assert "iterations: 1,234" in text
        assert "usage: 98.5" in text
        assert "attempts: 2" in text
        assert "load_1min: 1,234,567.89" in text
        assert "uptime_seconds:" in text
        assert "9,876,543" in text

    def test_should_format_report_html_with_hostname(self):
        """Test HTML report formatting includes hostname."""
        manager = NotificationManager({"enabled": True})
        report = {
            "event_type": "resource_recovery",
            "timestamp": 1700000000.0,
            "severity": "high",
            "hostname": "test-host",
        }

        text = manager._format_report_html("event", report)

        assert "<strong>Hostname:</strong> test-host" in text

    def test_should_format_startup_summary_numbers(self):
        """Test startup summary formats numeric values for display."""
        manager = NotificationManager({"enabled": True})
        report = {
            "event_type": "startup_summary",
            "timestamp": 1700000000.0,
            "severity": "info",
            "check_interval": 120000,
            "system_stats": {"cpu": {"load_1min": 1.0}},
        }

        text = manager._format_report_plain("event", report)

        assert "Startup Summary:" in text
        assert "Check Interval: 120,000" in text
        assert "load_1min: 1" in text

    def test_should_format_report_html_with_sections(self):
        """Test HTML report formatting includes sections."""
        manager = NotificationManager({"enabled": True})
        report = {
            "event_type": "resource_recovery",
            "timestamp": 1700000000.0,
            "severity": "high",
            "service": {"name": "nginx", "status": "down"},
            "resource": {"type": "cpu"},
            "action": {"name": "restart"},
            "details": "Recovered",
            "system_stats": {"cpu": {"load_1min": 1.0}},
        }

        text = manager._format_report_html("action", report)

        assert "<h3>Service</h3>" in text
        assert "<h3>Resource</h3>" in text
        assert "<h3>Action</h3>" in text
        assert "<h3>Details</h3>" in text
        assert "<h3>System Stats</h3>" in text

    def test_should_format_startup_summary_sections(self):
        """Test startup summary renders core system information."""
        manager = NotificationManager({"enabled": True})
        report = {
            "event_type": "startup_summary",
            "timestamp": 1700000000.0,
            "severity": "info",
            "hostname": "test-host",
            "version": "1.2.3",
            "check_interval": 60,
            "enabled_channels": ["email", "telegram"],
            "startup_time": "2026-03-22T00:00:00+00:00",
            "system_stats": {
                "cpu": {"load_1min": 0.1},
                "memory": {"used_percent": 42.0},
                "disk": {"root": {"used_percent": 55.0}},
            },
        }

        plain_text = manager._format_report_plain("event", report)
        html_text = manager._format_report_html("event", report)

        assert "Version:" in plain_text
        assert "Check Interval:" in plain_text
        assert "Enabled Channels:" in plain_text
        assert "Startup Time:" in plain_text
        assert "CPU:" in plain_text
        assert "RAM:" in plain_text
        assert "Disk:" in plain_text

        assert "<h3>Startup Summary</h3>" in html_text
        assert "<h3>Version</h3>" in html_text
        assert "<h3>Check Interval</h3>" in html_text
        assert "<h3>Enabled Channels</h3>" in html_text
        assert "<h3>Startup Time</h3>" in html_text
        assert "<h3>CPU</h3>" in html_text
        assert "<h3>RAM</h3>" in html_text
        assert "<h3>Disk</h3>" in html_text

    def test_should_format_top_process_sections_in_reports(self):
        """Test report formatting renders top process sections for fast diagnosis."""
        manager = NotificationManager({"enabled": True})
        report = {
            "event_type": "resource_threshold",
            "timestamp": 1700000000.0,
            "severity": "high",
            "hostname": "test-host",
            "details": "CPU load threshold exceeded",
            "system_stats": {
                "cpu": {"load_1min": 15.0},
                "top_processes": {
                    "cpu_percent": [{"user": "www-data", "pid": 111, "command": "php-fpm", "cpu_percent": 99.5}],
                    "cpu_load": [{"user": "root", "pid": 222, "command": "python3", "cpu_core_load": 1.75}],
                    "memory": [
                        {
                            "user": "mysql",
                            "pid": 333,
                            "command": "mysqld",
                            "memory_mb": 2048.0,
                            "memory_percent": 25.0,
                        }
                    ],
                    "disk_io": [{"user": "root", "pid": 444, "command": "rsync", "read_mb_per_sec": 10.5}],
                    "network": {
                        "available": False,
                        "reason": "Process-level network throughput is unavailable without an optional collector.",
                        "top": [],
                    },
                },
            },
        }

        plain_text = manager._format_report_plain("event", report)
        html_text = manager._format_report_html("event", report)

        assert "Top Processes by CPU %:" in plain_text
        assert "USER: www-data | PID: 111 | COMMAND: php-fpm | CPU %: 99.5" in plain_text
        assert "Top Processes by CPU Load (cores):" in plain_text
        assert "Top Processes by Memory:" in plain_text
        assert "Top Processes by Disk I/O:" in plain_text
        assert "Top Processes by Network:" in plain_text
        assert "Process-level network throughput is unavailable" in plain_text

        assert "<h4>Top Processes by CPU %</h4>" in html_text
        assert "www-data" in html_text
        assert "Process-level network throughput is unavailable" in html_text

    def test_should_handle_custom_message_exceptions(self, mocker):
        """Test custom message handles channel exceptions."""
        email_instance = mocker.Mock()
        email_instance.send_notification.side_effect = RuntimeError("email fail")

        telegram_instance = mocker.Mock()
        telegram_instance.send_notification.side_effect = RuntimeError("telegram fail")

        slack_instance = mocker.Mock()
        slack_instance.send_notification.side_effect = RuntimeError("slack fail")

        discord_instance = mocker.Mock()
        discord_instance.send_notification.side_effect = RuntimeError("discord fail")

        webhook_instance = mocker.Mock()
        webhook_instance.send_notification.side_effect = RuntimeError("webhook fail")

        mocker.patch("xnetvn_monitord.notifiers.EmailNotifier", return_value=email_instance)
        mocker.patch("xnetvn_monitord.notifiers.TelegramNotifier", return_value=telegram_instance)
        mocker.patch("xnetvn_monitord.notifiers.SlackNotifier", return_value=slack_instance)
        mocker.patch("xnetvn_monitord.notifiers.DiscordNotifier", return_value=discord_instance)
        mocker.patch("xnetvn_monitord.notifiers.WebhookNotifier", return_value=webhook_instance)

        manager = NotificationManager(
            {
                "enabled": True,
                "email": {"enabled": True},
                "telegram": {"enabled": True},
                "slack": {"enabled": True},
                "discord": {"enabled": True},
                "webhook": {"enabled": True},
            }
        )

        assert manager.notify_custom_message("Subject", "Body") is False

    def test_should_handle_report_send_exceptions(self, mocker):
        """Test report sending handles channel exceptions."""
        email_instance = mocker.Mock()
        email_instance.send_notification.side_effect = RuntimeError("email fail")

        telegram_instance = mocker.Mock()
        telegram_instance.send_notification.side_effect = RuntimeError("telegram fail")

        slack_instance = mocker.Mock()
        slack_instance.send_notification.side_effect = RuntimeError("slack fail")

        discord_instance = mocker.Mock()
        discord_instance.send_notification.side_effect = RuntimeError("discord fail")

        webhook_instance = mocker.Mock()
        webhook_instance.send_notification.side_effect = RuntimeError("webhook fail")

        mocker.patch("xnetvn_monitord.notifiers.EmailNotifier", return_value=email_instance)
        mocker.patch("xnetvn_monitord.notifiers.TelegramNotifier", return_value=telegram_instance)
        mocker.patch("xnetvn_monitord.notifiers.SlackNotifier", return_value=slack_instance)
        mocker.patch("xnetvn_monitord.notifiers.DiscordNotifier", return_value=discord_instance)
        mocker.patch("xnetvn_monitord.notifiers.WebhookNotifier", return_value=webhook_instance)

        manager = NotificationManager(
            {
                "enabled": True,
                "rate_limit": {"enabled": False},
                "email": {"enabled": True},
                "telegram": {"enabled": True},
                "slack": {"enabled": True},
                "discord": {"enabled": True},
                "webhook": {"enabled": True},
            }
        )

        event = {
            "event_type": "resource_threshold",
            "timestamp": 1700000000.0,
            "severity": "high",
            "resource": {"type": "cpu"},
            "action": {"name": "restart"},
            "details": "Recovered",
            "system_stats": {"cpu": {"load_1min": 1.0}},
        }

        assert manager.notify_event(event) is False

    def test_should_record_notifications(self):
        """Test notification history is recorded."""
        manager = NotificationManager({"enabled": True})

        manager._record_notification("email:event")

        assert "email:event" in manager.notification_history
        assert len(manager.notification_history["email:event"]) == 1

    def test_should_respect_min_severity(self, mocker):
        """Test channel min severity blocks lower severity events."""
        email_instance = mocker.Mock()
        email_instance.send_notification.return_value = True

        mocker.patch("xnetvn_monitord.notifiers.EmailNotifier", return_value=email_instance)

        manager = NotificationManager(
            {
                "enabled": True,
                "rate_limit": {"enabled": False},
                "email": {"enabled": True, "min_severity": "high"},
            }
        )

        event = {"event_type": "resource_threshold", "severity": "low"}

        assert manager.notify_event(event) is False
        email_instance.send_notification.assert_not_called()
