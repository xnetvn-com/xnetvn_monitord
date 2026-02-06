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

"""Unit tests for EmailNotifier."""

import smtplib

from xnetvn_monitord.notifiers.email_notifier import EmailNotifier


class TestEmailNotifierSendNotification:
    """Tests for send_notification."""

    def test_should_return_false_when_disabled(self):
        """Test disabled notifier returns False."""
        notifier = EmailNotifier({"enabled": False})
        assert notifier.send_notification("Subject", "Message") is False

    def test_should_return_false_when_no_recipients(self):
        """Test missing recipients returns False."""
        notifier = EmailNotifier({"enabled": True, "to_addresses": []})
        assert notifier.send_notification("Subject", "Message") is False

    def test_should_send_plain_text_email(self, mocker):
        """Test sending a plain text email."""
        smtp_instance = mocker.Mock()
        mocker.patch("smtplib.SMTP", return_value=smtp_instance)

        config = {
            "enabled": True,
            "to_addresses": ["admin@example.com"],
            "from_address": "monitor@example.com",
            "smtp": {
                "host": "localhost",
                "port": 25,
                "use_tls": False,
                "use_ssl": False,
            },
        }

        notifier = EmailNotifier(config)
        result = notifier.send_notification("Subject", "Message", is_html=False)

        assert result is True
        smtp_instance.send_message.assert_called_once()
        smtp_instance.quit.assert_called_once()

    def test_should_send_html_email(self, mocker):
        """Test sending an HTML email."""
        smtp_instance = mocker.Mock()
        mocker.patch("smtplib.SMTP", return_value=smtp_instance)

        config = {
            "enabled": True,
            "to_addresses": ["admin@example.com"],
            "from_address": "monitor@example.com",
            "smtp": {
                "host": "localhost",
                "port": 25,
                "use_tls": False,
                "use_ssl": False,
            },
        }

        notifier = EmailNotifier(config)
        result = notifier.send_notification("Subject", "<b>Message</b>", is_html=True)

        assert result is True
        smtp_instance.send_message.assert_called_once()

    def test_should_return_false_when_send_fails(self, mocker):
        """Test send_notification returns False when SMTP fails."""
        config = {
            "enabled": True,
            "to_addresses": ["admin@example.com"],
            "from_address": "monitor@example.com",
            "smtp": {"host": "localhost", "port": 25},
        }

        notifier = EmailNotifier(config)
        mocker.patch.object(notifier, "_send_via_smtp", side_effect=RuntimeError("fail"))

        assert notifier.send_notification("Subject", "Message") is False


class TestEmailNotifierSmtp:
    """Tests for SMTP delivery."""

    def test_should_use_tls_when_configured(self, mocker):
        """Test TLS is used when configured."""
        smtp_instance = mocker.Mock()
        mocker.patch("smtplib.SMTP", return_value=smtp_instance)

        config = {
            "enabled": True,
            "to_addresses": ["admin@example.com"],
            "from_address": "monitor@example.com",
            "smtp": {
                "host": "localhost",
                "port": 25,
                "use_tls": True,
                "use_ssl": False,
            },
        }

        notifier = EmailNotifier(config)
        notifier.send_notification("Subject", "Message")

        smtp_instance.starttls.assert_called_once()

    def test_should_use_ssl_when_configured(self, mocker):
        """Test SSL is used when configured."""
        smtp_ssl_instance = mocker.Mock()
        mocker.patch("smtplib.SMTP_SSL", return_value=smtp_ssl_instance)

        config = {
            "enabled": True,
            "to_addresses": ["admin@example.com"],
            "from_address": "monitor@example.com",
            "smtp": {
                "host": "localhost",
                "port": 465,
                "use_tls": False,
                "use_ssl": True,
            },
        }

        notifier = EmailNotifier(config)
        notifier.send_notification("Subject", "Message")

        smtp_ssl_instance.send_message.assert_called_once()


class TestEmailNotifierTemplates:
    """Tests for alert templates."""

    def test_should_send_service_alert_plain(self, mocker):
        """Test service alert in plain format."""
        notifier = EmailNotifier({"enabled": True, "template": {"format": "plain"}})
        mocker.patch.object(notifier, "send_notification", return_value=True)

        result = notifier.send_service_alert("nginx", "down", "details")

        assert result is True
        notifier.send_notification.assert_called_once()

    def test_should_send_service_alert_html(self, mocker):
        """Test service alert in HTML format."""
        notifier = EmailNotifier({"enabled": True, "template": {"format": "html"}})
        mocker.patch.object(notifier, "send_notification", return_value=True)

        result = notifier.send_service_alert("nginx", "down", "details")

        assert result is True
        notifier.send_notification.assert_called_once()

    def test_should_send_resource_alert_plain(self, mocker):
        """Test resource alert in plain format."""
        notifier = EmailNotifier({"enabled": True, "template": {"format": "plain"}})
        mocker.patch.object(notifier, "send_notification", return_value=True)

        result = notifier.send_resource_alert("cpu", {"load": 1.0})

        assert result is True
        notifier.send_notification.assert_called_once()

    def test_should_send_resource_alert_html(self, mocker):
        """Test resource alert in HTML format."""
        notifier = EmailNotifier({"enabled": True, "template": {"format": "html"}})
        mocker.patch.object(notifier, "send_notification", return_value=True)

        result = notifier.send_resource_alert("memory", {"used": 90})

        assert result is True
        notifier.send_notification.assert_called_once()


class TestEmailNotifierFormatting:
    """Tests for formatting helpers."""

    def test_should_convert_nested_dict_to_string(self):
        """Test dictionary formatting handles nested structures."""
        notifier = EmailNotifier({"enabled": True})

        data = {"a": {"b": 1}, "list": ["item", {"c": 2}]}
        result = notifier._dict_to_string(data)

        assert "a:" in result
        assert "b: 1" in result
        assert "- item" in result
        assert "c: 2" in result


class TestEmailNotifierConnection:
    """Tests for SMTP connection checks."""

    def test_should_return_false_when_disabled(self):
        """Test disabled notifier returns False for connection test."""
        notifier = EmailNotifier({"enabled": False})
        assert notifier.test_connection() is False

    def test_should_test_smtp_connection_success(self, mocker):
        """Test SMTP connection success."""
        smtp_instance = mocker.Mock()
        mocker.patch("smtplib.SMTP", return_value=smtp_instance)

        notifier = EmailNotifier({"enabled": True, "smtp": {"host": "localhost", "port": 25}})

        assert notifier.test_connection() is True
        smtp_instance.ehlo.assert_called_once()
        smtp_instance.quit.assert_called_once()

    def test_should_test_smtp_connection_with_ssl(self, mocker):
        """Test SMTP connection uses SSL when configured."""
        smtp_instance = mocker.Mock()
        mocker.patch("smtplib.SMTP_SSL", return_value=smtp_instance)

        notifier = EmailNotifier(
            {
                "enabled": True,
                "smtp": {"host": "localhost", "port": 465, "use_ssl": True},
            }
        )

        assert notifier.test_connection() is True
        smtp_instance.ehlo.assert_called_once()
        smtp_instance.quit.assert_called_once()

    def test_should_test_smtp_connection_failure(self, mocker):
        """Test SMTP connection failure handling."""
        mocker.patch("smtplib.SMTP", side_effect=smtplib.SMTPException("fail"))

        notifier = EmailNotifier({"enabled": True, "smtp": {"host": "localhost", "port": 25}})

        assert notifier.test_connection() is False
