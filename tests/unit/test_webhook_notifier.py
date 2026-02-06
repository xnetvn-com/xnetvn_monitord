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

"""Unit tests for WebhookNotifier."""

import urllib.error

from xnetvn_monitord.notifiers.webhook_notifier import WebhookNotifier


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


class TestWebhookNotifier:
    """Tests for WebhookNotifier."""

    def test_should_return_false_when_disabled(self):
        """Test disabled notifier returns False."""
        notifier = WebhookNotifier({"enabled": False})
        assert notifier.send_notification({"test": True}) is False

    def test_should_return_false_when_no_urls(self):
        """Test missing webhook URLs returns False."""
        notifier = WebhookNotifier({"enabled": True, "urls": []})
        assert notifier.send_notification({"test": True}) is False

    def test_should_send_payload(self, mocker):
        """Test successful webhook payload delivery."""
        mocker.patch("urllib.request.urlopen", return_value=DummyResponse())

        notifier = WebhookNotifier({"enabled": True, "urls": ["https://example.com"]})

        assert notifier.send_notification({"event": "test"}) is True

    def test_should_merge_extra_headers(self, mocker):
        """Test extra headers are merged into request headers."""
        headers_seen = []

        def fake_request(url, data=None, headers=None, method=None):
            headers_seen.append(headers or {})
            return mocker.Mock()

        mocker.patch("urllib.request.Request", side_effect=fake_request)
        mocker.patch("urllib.request.urlopen", return_value=DummyResponse())

        notifier = WebhookNotifier({"enabled": True, "urls": ["https://example.com"], "headers": {"X-Base": "1"}})

        assert notifier.send_notification({"event": "test"}, extra_headers={"X-Extra": "2"})
        assert headers_seen[0]["X-Base"] == "1"
        assert headers_seen[0]["X-Extra"] == "2"

    def test_should_send_payload_when_some_endpoints_fail(self, mocker):
        """Test success when at least one endpoint returns 2xx."""
        mocker.patch(
            "urllib.request.urlopen",
            side_effect=[DummyResponse(status=500), DummyResponse(status=204)],
        )

        notifier = WebhookNotifier({"enabled": True, "urls": ["https://one.example", "https://two.example"]})

        assert notifier.send_notification({"event": "test"}) is True

    def test_should_return_false_on_non_2xx_status(self, mocker):
        """Test non-2xx response returns False."""
        mocker.patch("urllib.request.urlopen", return_value=DummyResponse(status=500))

        notifier = WebhookNotifier({"enabled": True, "urls": ["https://example.com"]})

        assert notifier._post_payload("https://example.com", {"event": "test"}, {}) is False

    def test_should_return_false_on_url_error(self, mocker):
        """Test URL error returns False."""
        mocker.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down"))

        notifier = WebhookNotifier({"enabled": True, "urls": ["https://example.com"]})

        assert notifier._post_payload("https://example.com", {"event": "test"}, {}) is False

    def test_should_skip_live_test_when_disabled(self):
        """Test connection check skips live test when disabled."""
        notifier = WebhookNotifier({"enabled": True, "urls": ["https://example.com"]})
        assert notifier.test_connection() is True

    def test_should_return_false_when_connection_disabled(self):
        """Test test_connection returns False when disabled."""
        notifier = WebhookNotifier({"enabled": False})
        assert notifier.test_connection() is False

    def test_should_return_false_when_connection_missing_urls(self):
        """Test test_connection returns False when no URLs configured."""
        notifier = WebhookNotifier({"enabled": True, "urls": []})
        assert notifier.test_connection() is False

    def test_should_run_live_test_when_enabled(self, mocker):
        """Test live test executes when test_on_startup is enabled."""
        mocker.patch("urllib.request.urlopen", return_value=DummyResponse())

        notifier = WebhookNotifier(
            {
                "enabled": True,
                "urls": ["https://example.com"],
                "test_on_startup": True,
            }
        )

        assert notifier.test_connection() is True

    def test_should_normalize_urls_with_single_url(self):
        """Test url overrides urls list in configuration."""
        notifier = WebhookNotifier(
            {
                "enabled": True,
                "url": "https://single.example",
                "urls": ["https://ignored.example"],
            }
        )

        assert notifier.urls == ["https://single.example"]

    def test_should_return_false_when_all_endpoints_fail(self, mocker):
        """Test send_notification returns False when all endpoints fail."""
        mocker.patch("urllib.request.urlopen", return_value=DummyResponse(status=500))

        notifier = WebhookNotifier({"enabled": True, "urls": ["https://one.example", "https://two.example"]})

        assert notifier.send_notification({"event": "test"}) is False
