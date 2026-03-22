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

"""Notification manager module.

This module provides a unified interface for managing multiple notification channels.
"""

import copy
import html
import logging
import re
import socket
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .discord_notifier import DiscordNotifier
from .email_notifier import EmailNotifier
from .slack_notifier import SlackNotifier
from .telegram_notifier import TelegramNotifier
from .webhook_notifier import WebhookNotifier

logger = logging.getLogger(__name__)


class NotificationManager:
    """Manage and coordinate multiple notification channels."""

    _SEVERITY_RANK = {
        "debug": 0,
        "info": 1,
        "low": 2,
        "medium": 3,
        "high": 4,
        "critical": 5,
    }

    def __init__(self, config: Dict):
        """Initialize the notification manager.

        Args:
            config: Notification configuration dictionary.
        """
        self.config = config
        self.enabled = config.get("enabled", True)
        self.rate_limit_config = config.get("rate_limit", {})
        self.content_filter_config = config.get("content_filter", {})
        self.default_min_severity = config.get("min_severity", "info")
        self.hostname = socket.gethostname()
        self.only_ipv4 = config.get("only_ipv4", False)

        # Initialize notification channels
        self.email_notifier = None
        self.telegram_notifier = None
        self.webhook_notifier = None
        self.slack_notifier = None
        self.discord_notifier = None

        if self.enabled:
            email_config = self._apply_network_defaults(config.get("email", {}))
            if email_config.get("enabled", False):
                self.email_notifier = EmailNotifier(email_config)

            telegram_config = self._apply_network_defaults(config.get("telegram", {}))
            if telegram_config.get("enabled", False):
                self.telegram_notifier = TelegramNotifier(telegram_config)

            webhook_config = self._apply_network_defaults(config.get("webhook", {}))
            if webhook_config.get("enabled", False):
                self.webhook_notifier = WebhookNotifier(webhook_config)

            slack_config = self._apply_network_defaults(config.get("slack", {}))
            if slack_config.get("enabled", False):
                self.slack_notifier = SlackNotifier(slack_config)

            discord_config = self._apply_network_defaults(config.get("discord", {}))
            if discord_config.get("enabled", False):
                self.discord_notifier = DiscordNotifier(discord_config)

        # Rate limiting tracking
        self.notification_history: Dict[str, List[float]] = {}

    def notify_service_failure(self, service_name: str, status: str, details: str) -> bool:
        """Send legacy notification about service failure.

        Args:
            service_name: Name of the service.
            status: Service status.
            details: Detailed information.

        Returns:
            True if at least one notification sent, False otherwise.
        """
        event = {
            "event_type": "service_alert",
            "timestamp": time.time(),
            "severity": "high",
            "service": {"name": service_name, "status": status},
            "details": details,
        }
        return self.notify_event(event)

    def notify_resource_alert(self, resource_type: str, details: Dict) -> bool:
        """Send legacy notification about resource threshold breach.

        Args:
            resource_type: Type of resource (cpu, memory, disk).
            details: Resource details.

        Returns:
            True if at least one notification sent, False otherwise.
        """
        event = {
            "event_type": "resource_alert",
            "timestamp": time.time(),
            "severity": "medium",
            "resource": {"type": resource_type, "details": details},
        }
        return self.notify_event(event)

    def notify_event(self, event: Dict) -> bool:
        """Send an event report notification.

        Args:
            event: Event report payload.

        Returns:
            True if at least one notification sent, False otherwise.
        """
        if not self.enabled:
            return False

        return self._send_report("event", event)

    def notify_action_result(self, action_report: Dict) -> bool:
        """Send an action result report notification.

        Args:
            action_report: Action result report payload.

        Returns:
            True if at least one notification sent, False otherwise.
        """
        if not self.enabled:
            return False

        return self._send_report("action", action_report)

    def notify_custom_message(self, subject: str, message: str) -> bool:
        """Send a custom notification message.

        Args:
            subject: Notification subject/title.
            message: Notification message.

        Returns:
            True if at least one notification sent, False otherwise.
        """
        if not self.enabled:
            return False

        # Filter sensitive content
        message = self._filter_sensitive_content(message)
        hostname = self._resolve_hostname({})
        message_with_host = self._prepend_hostname(message, hostname)

        success = False

        # Send to all enabled channels
        if self.email_notifier:
            try:
                if self.email_notifier.send_notification(subject, message_with_host):
                    success = True
            except Exception as e:
                logger.error(f"Error sending email notification: {str(e)}")

        if self.telegram_notifier:
            try:
                if self.telegram_notifier.send_notification(f"{message_with_host}\n\n{subject}"):
                    success = True
            except Exception as e:
                logger.error(f"Error sending Telegram notification: {str(e)}")

        if self.slack_notifier:
            try:
                if self.slack_notifier.send_notification(f"{message_with_host}\n\n{subject}"):
                    success = True
            except Exception as e:
                logger.error(f"Error sending Slack notification: {str(e)}")

        if self.discord_notifier:
            try:
                if self.discord_notifier.send_notification(f"{message_with_host}\n\n{subject}"):
                    success = True
            except Exception as e:
                logger.error(f"Error sending Discord notification: {str(e)}")

        if self.webhook_notifier:
            try:
                payload = {
                    "subject": subject,
                    "message": message,
                    "hostname": hostname,
                }
                if self.webhook_notifier.send_notification(payload):
                    success = True
            except Exception as e:
                logger.error(f"Error sending webhook notification: {str(e)}")

        return success

    def _check_rate_limit(
        self,
        notification_key: str,
        rate_limit_config: Optional[Dict] = None,
    ) -> bool:
        """Check if notification is within rate limits.

        Args:
            notification_key: Unique key for the notification type.

        Returns:
            True if notification is allowed, False if rate limited.
        """
        rate_limit_config = rate_limit_config or self.rate_limit_config

        if not rate_limit_config.get("enabled", True):
            return True

        current_time = time.time()
        min_interval = rate_limit_config.get("min_interval", 300)
        max_per_hour = rate_limit_config.get("max_per_hour", 20)

        # Initialize history for this key if not exists
        if notification_key not in self.notification_history:
            self.notification_history[notification_key] = []

        history = self.notification_history[notification_key]

        # Check minimum interval
        if history and (current_time - history[-1]) < min_interval:
            return False

        # Clean old entries (older than 1 hour)
        history[:] = [t for t in history if (current_time - t) < 3600]

        # Check maximum per hour
        if len(history) >= max_per_hour:
            return False

        return True

    def _record_notification(self, notification_key: str) -> None:
        """Record a notification in history.

        Args:
            notification_key: Unique key for the notification type.
        """
        current_time = time.time()
        if notification_key not in self.notification_history:
            self.notification_history[notification_key] = []
        self.notification_history[notification_key].append(current_time)

    def _send_report(self, report_type: str, report: Dict) -> bool:
        """Send a report to all configured channels.

        Args:
            report_type: Report type (event or action).
            report: Report payload.

        Returns:
            True if at least one notification sent, False otherwise.
        """
        notification_key = f"{report_type}_{report.get('event_type', 'unknown')}"
        severity = self._normalize_severity(report.get("severity", "info"))

        subject = self._build_subject(report_type, report)
        payload = self._filter_dict_content(report)

        success = False

        if self.email_notifier:
            if self._should_send_to_channel("email", severity, notification_key):
                try:
                    email_config = self.config.get("email", {})
                    template_format = email_config.get("template", {}).get("format", "plain")
                    event_data = self._prepare_report_for_channel(report, email_config)
                    message = (
                        self._format_report_html(report_type, event_data)
                        if template_format == "html"
                        else self._format_report_plain(report_type, event_data)
                    )
                    message = self._filter_sensitive_content(message)
                    if self.email_notifier.send_notification(subject, message, template_format == "html"):
                        success = True
                        self._record_notification(f"email:{notification_key}")
                except Exception as e:
                    logger.error("Error sending email report: %s", str(e))

        if self.telegram_notifier:
            if self._should_send_to_channel("telegram", severity, notification_key):
                try:
                    event_data = self._prepare_report_for_channel(
                        report,
                        self.config.get("telegram", {}),
                        "telegram",
                    )
                    message = self._format_report_plain(report_type, event_data)
                    message = self._filter_sensitive_content(message)
                    if self.telegram_notifier.send_notification(message):
                        success = True
                        self._record_notification(f"telegram:{notification_key}")
                except Exception as e:
                    logger.error("Error sending Telegram report: %s", str(e))

        if self.slack_notifier:
            if self._should_send_to_channel("slack", severity, notification_key):
                try:
                    event_data = self._prepare_report_for_channel(
                        report,
                        self.config.get("slack", {}),
                        "slack",
                    )
                    message = self._format_report_plain(report_type, event_data)
                    message = self._filter_sensitive_content(message)
                    if self.slack_notifier.send_notification(message):
                        success = True
                        self._record_notification(f"slack:{notification_key}")
                except Exception as e:
                    logger.error("Error sending Slack report: %s", str(e))

        if self.discord_notifier:
            if self._should_send_to_channel("discord", severity, notification_key):
                try:
                    event_data = self._prepare_report_for_channel(
                        report,
                        self.config.get("discord", {}),
                        "discord",
                    )
                    message = self._format_report_plain(report_type, event_data)
                    message = self._filter_sensitive_content(message)
                    if self.discord_notifier.send_notification(message):
                        success = True
                        self._record_notification(f"discord:{notification_key}")
                except Exception as e:
                    logger.error("Error sending Discord report: %s", str(e))

        if self.webhook_notifier:
            if self._should_send_to_channel("webhook", severity, notification_key):
                try:
                    webhook_payload = self._build_webhook_payload(report_type, payload)
                    if self.webhook_notifier.send_notification(webhook_payload):
                        success = True
                        self._record_notification(f"webhook:{notification_key}")
                except Exception as e:
                    logger.error("Error sending webhook report: %s", str(e))

        return success

    def _build_subject(self, report_type: str, report: Dict) -> str:
        """Build a report subject string.

        Args:
            report_type: Report type (event or action).
            report: Report payload.

        Returns:
            Subject string.
        """
        title = report.get("title")
        if title:
            return title

        event_type = report.get("event_type", "event")
        prefix = "Action Report" if report_type == "action" else "Event Report"
        return f"{prefix}: {event_type}"

    def _build_webhook_payload(self, report_type: str, report: Dict) -> Dict:
        """Build webhook payload wrapper.

        Args:
            report_type: Report type.
            report: Report payload.

        Returns:
            Webhook payload dictionary.
        """
        return {
            "report_type": report_type,
            "report": report,
        }

    def _prepare_report_for_channel(
        self,
        report: Dict,
        channel_config: Dict,
        channel_name: Optional[str] = None,
    ) -> Dict:
        """Prepare a report for a specific channel.

        Args:
            report: Original report payload.
            channel_config: Channel configuration.
            channel_name: Optional notification channel name.

        Returns:
            Sanitized report payload.
        """
        report_copy = copy.deepcopy(report)
        if not channel_config.get("include_system_stats", True):
            report_copy.pop("system_stats", None)
        if not channel_config.get("include_action_details", True):
            report_copy.pop("action", None)
        if not channel_config.get("include_details", True):
            report_copy.pop("details", None)

        if channel_name in {"telegram", "slack", "discord"}:
            self._remove_network_interfaces(report_copy)

        return report_copy

    def _remove_network_interfaces(self, report: Dict) -> None:
        """Remove per-interface network stats from a report in place.

        Args:
            report: Report payload to sanitize.
        """
        system_stats = report.get("system_stats")
        if not isinstance(system_stats, dict):
            return

        network_stats = system_stats.get("network")
        if not isinstance(network_stats, dict):
            return

        network_stats.pop("interfaces", None)

    def _format_report_plain(self, report_type: str, report: Dict) -> str:
        """Format report in plain text.

        Args:
            report_type: Report type (event or action).
            report: Report payload.

        Returns:
            Formatted plain text report.
        """
        title = self._build_subject(report_type, report)
        lines = [title, "=" * len(title)]
        hostname = self._resolve_hostname(report)
        if hostname:
            lines.append(f"Hostname: {hostname}")
        lines.append(f"Timestamp: {self._format_timestamp(report.get('timestamp'))}")
        lines.append(f"Severity: {self._normalize_severity(report.get('severity', 'info'))}")

        if report.get("service"):
            lines.append("\nService:")
            lines.append(self._dict_to_string(report.get("service", {}), indent=1))

        if report.get("resource"):
            lines.append("\nResource:")
            lines.append(self._dict_to_string(report.get("resource", {}), indent=1))

        if report.get("action"):
            lines.append("\nAction:")
            lines.append(self._dict_to_string(report.get("action", {}), indent=1))

        if report.get("details"):
            lines.append("\nDetails:")
            lines.append(str(report.get("details")))

        if report.get("event_type") == "startup_summary":
            lines.extend(self._format_startup_summary_plain(report))

        if report.get("system_stats"):
            lines.extend(
                self._format_system_stats_plain(
                    report.get("system_stats", {}),
                    include_header=report.get("event_type") != "startup_summary",
                )
            )

        return "\n".join(lines).strip()

    def _format_report_html(self, report_type: str, report: Dict) -> str:
        """Format report in HTML.

        Args:
            report_type: Report type (event or action).
            report: Report payload.

        Returns:
            Formatted HTML report.
        """
        title = self._build_subject(report_type, report)
        hostname = self._resolve_hostname(report)
        hostname_line = f"<strong>Hostname:</strong> {hostname}<br>" if hostname else ""
        sections = [f"<h2>{title}</h2>"]
        sections.append(
            f"<p>{hostname_line}"
            f"<strong>Timestamp:</strong> {self._format_timestamp(report.get('timestamp'))}<br>"
            f"<strong>Severity:</strong> {self._normalize_severity(report.get('severity', 'info'))}</p>"
        )

        if report.get("service"):
            sections.append("<h3>Service</h3>")
            sections.append(f"<pre>{self._dict_to_string(report.get('service', {}), indent=1)}</pre>")

        if report.get("resource"):
            sections.append("<h3>Resource</h3>")
            sections.append(f"<pre>{self._dict_to_string(report.get('resource', {}), indent=1)}</pre>")

        if report.get("action"):
            sections.append("<h3>Action</h3>")
            sections.append(f"<pre>{self._dict_to_string(report.get('action', {}), indent=1)}</pre>")

        if report.get("details"):
            sections.append("<h3>Details</h3>")
            sections.append(f"<pre>{report.get('details')}</pre>")

        if report.get("event_type") == "startup_summary":
            sections.extend(self._format_startup_summary_html(report))

        if report.get("system_stats"):
            sections.extend(
                self._format_system_stats_html(
                    report.get("system_stats", {}),
                    include_header=report.get("event_type") != "startup_summary",
                )
            )

        return "\n".join(sections).strip()

    def _format_startup_summary_plain(self, report: Dict) -> List[str]:
        """Format startup-specific summary details for plain text reports."""
        lines = ["\nStartup Summary:"]
        lines.append(f"Version: {report.get('version', 'N/A')}")
        lines.append(f"Startup Time: {report.get('startup_time') or self._format_timestamp(report.get('timestamp'))}")
        lines.append(f"Check Interval: {self._format_display_value(report.get('check_interval', 'N/A'))}")
        lines.append(f"Enabled Channels: {', '.join(report.get('enabled_channels', [])) or 'none'}")
        lines.extend(self._format_system_stats_plain(report.get("system_stats", {}), include_header=True))
        return lines

    def _format_startup_summary_html(self, report: Dict) -> List[str]:
        """Format startup-specific summary details for HTML reports."""
        sections = ["<h3>Startup Summary</h3>"]
        sections.append("<h3>Version</h3>")
        sections.append(f"<pre>{report.get('version', 'N/A')}</pre>")
        sections.append("<h3>Startup Time</h3>")
        sections.append(f"<pre>{report.get('startup_time') or self._format_timestamp(report.get('timestamp'))}</pre>")
        sections.append("<h3>Check Interval</h3>")
        sections.append(f"<pre>{self._format_display_value(report.get('check_interval', 'N/A'))}</pre>")
        sections.append("<h3>Enabled Channels</h3>")
        sections.append(f"<pre>{', '.join(report.get('enabled_channels', [])) or 'none'}</pre>")
        sections.extend(self._format_system_stats_html(report.get("system_stats", {}), include_header=True))
        return sections

    def _format_system_stats_plain(self, system_stats: Dict, include_header: bool = True) -> List[str]:
        """Format system statistics for plain text reports."""
        if not system_stats:
            return []

        lines = ["\nSystem Stats:"] if include_header else []
        for key, value in system_stats.items():
            if key == "top_processes" and isinstance(value, dict):
                lines.extend(self._format_top_processes_plain(value))
                continue

            if key == "memory":
                label = "RAM"
            elif key == "cpu":
                label = "CPU"
            elif key == "disk":
                label = "Disk"
            else:
                label = str(key)
            lines.append(f"\n{label}:")
            if isinstance(value, dict):
                lines.append(self._dict_to_string(value, indent=1))
            else:
                lines.append(self._format_display_value(value))
        return lines

    def _format_system_stats_html(self, system_stats: Dict, include_header: bool = True) -> List[str]:
        """Format system statistics for HTML reports."""
        if not system_stats:
            return []

        sections = ["<h3>System Stats</h3>"] if include_header else []
        for key, value in system_stats.items():
            if key == "top_processes" and isinstance(value, dict):
                sections.extend(self._format_top_processes_html(value))
                continue

            if key == "memory":
                label = "RAM"
            elif key == "cpu":
                label = "CPU"
            elif key == "disk":
                label = "Disk"
            else:
                label = str(key)
            sections.append(f"<h3>{label}</h3>")
            if isinstance(value, dict):
                sections.append(f"<pre>{self._dict_to_string(value, indent=1)}</pre>")
            else:
                sections.append(f"<pre>{self._format_display_value(value)}</pre>")
        return sections

    def _format_top_processes_plain(self, top_processes: Dict[str, Any]) -> List[str]:
        """Format ranked process snapshots for plain text reports."""
        lines: List[str] = []
        lines.extend(
            self._format_top_process_section_plain(
                "Top Processes by CPU %:",
                top_processes.get("cpu_percent", []),
                [("USER", "user"), ("PID", "pid"), ("COMMAND", "command"), ("CPU %", "cpu_percent")],
            )
        )
        lines.extend(
            self._format_top_process_section_plain(
                "Top Processes by CPU Load (cores):",
                top_processes.get("cpu_load", []),
                [("USER", "user"), ("PID", "pid"), ("COMMAND", "command"), ("CPU Load", "cpu_core_load")],
            )
        )
        lines.extend(
            self._format_top_process_section_plain(
                "Top Processes by Memory:",
                top_processes.get("memory", []),
                [
                    ("USER", "user"),
                    ("PID", "pid"),
                    ("COMMAND", "command"),
                    ("RAM MB", "memory_mb"),
                    ("RAM %", "memory_percent"),
                ],
            )
        )
        lines.extend(
            self._format_top_process_section_plain(
                "Top Processes by Disk I/O:",
                top_processes.get("disk_io", []),
                [
                    ("USER", "user"),
                    ("PID", "pid"),
                    ("COMMAND", "command"),
                    ("READ MB/s", "read_mb_per_sec"),
                    ("WRITE MB/s", "write_mb_per_sec"),
                    ("TOTAL MB/s", "total_disk_io_mb_per_sec"),
                ],
            )
        )

        network_stats = top_processes.get("network", {})
        lines.append("\nTop Processes by Network:")
        if isinstance(network_stats, dict) and not network_stats.get("available", True):
            lines.append(str(network_stats.get("reason") or "No process data available."))
        else:
            network_entries = network_stats.get("top", []) if isinstance(network_stats, dict) else []
            lines.extend(
                self._format_top_process_entries_plain(
                    network_entries,
                    [
                        ("USER", "user"),
                        ("PID", "pid"),
                        ("COMMAND", "command"),
                        ("TX Mbps", "sent_mbps"),
                        ("RX Mbps", "recv_mbps"),
                        ("TOTAL Mbps", "total_mbps"),
                    ],
                )
            )

        return lines

    def _format_top_process_section_plain(
        self,
        title: str,
        entries: Any,
        field_map: List[Tuple[str, str]],
    ) -> List[str]:
        """Format a single ranked process section for plain text output."""
        lines = [f"\n{title}"]
        lines.extend(self._format_top_process_entries_plain(entries, field_map))
        return lines

    def _format_top_process_entries_plain(self, entries: Any, field_map: List[Tuple[str, str]]) -> List[str]:
        """Format process entries into single-line plain text rows."""
        if not isinstance(entries, list) or not entries:
            return ["No process data available."]

        formatted_lines: List[str] = []
        for entry in entries[:5]:
            if not isinstance(entry, dict):
                continue
            parts = []
            for label, key in field_map:
                value = entry.get(key)
                if value in (None, ""):
                    continue
                parts.append(f"{label}: {self._format_display_value(value)}")
            if parts:
                formatted_lines.append(" | ".join(parts))

        return formatted_lines or ["No process data available."]

    def _format_top_processes_html(self, top_processes: Dict[str, Any]) -> List[str]:
        """Format ranked process snapshots for HTML reports."""
        sections: List[str] = []
        sections.extend(
            self._format_top_process_section_html(
                "Top Processes by CPU %",
                top_processes.get("cpu_percent", []),
                [("USER", "user"), ("PID", "pid"), ("COMMAND", "command"), ("CPU %", "cpu_percent")],
            )
        )
        sections.extend(
            self._format_top_process_section_html(
                "Top Processes by CPU Load (cores)",
                top_processes.get("cpu_load", []),
                [("USER", "user"), ("PID", "pid"), ("COMMAND", "command"), ("CPU Load", "cpu_core_load")],
            )
        )
        sections.extend(
            self._format_top_process_section_html(
                "Top Processes by Memory",
                top_processes.get("memory", []),
                [
                    ("USER", "user"),
                    ("PID", "pid"),
                    ("COMMAND", "command"),
                    ("RAM MB", "memory_mb"),
                    ("RAM %", "memory_percent"),
                ],
            )
        )
        sections.extend(
            self._format_top_process_section_html(
                "Top Processes by Disk I/O",
                top_processes.get("disk_io", []),
                [
                    ("USER", "user"),
                    ("PID", "pid"),
                    ("COMMAND", "command"),
                    ("READ MB/s", "read_mb_per_sec"),
                    ("WRITE MB/s", "write_mb_per_sec"),
                    ("TOTAL MB/s", "total_disk_io_mb_per_sec"),
                ],
            )
        )

        network_stats = top_processes.get("network", {})
        sections.append("<h4>Top Processes by Network</h4>")
        if isinstance(network_stats, dict) and not network_stats.get("available", True):
            sections.append(
                f"<pre>{html.escape(str(network_stats.get('reason') or 'No process data available.'))}</pre>"
            )
        else:
            network_entries = network_stats.get("top", []) if isinstance(network_stats, dict) else []
            network_field_map: List[Tuple[str, str]] = [
                ("USER", "user"),
                ("PID", "pid"),
                ("COMMAND", "command"),
                ("TX Mbps", "sent_mbps"),
                ("RX Mbps", "recv_mbps"),
                ("TOTAL Mbps", "total_mbps"),
            ]
            sections.append(
                f"<pre>{html.escape(self._join_top_process_entries(network_entries, network_field_map))}</pre>"
            )

        return sections

    def _format_top_process_section_html(
        self,
        title: str,
        entries: Any,
        field_map: List[Tuple[str, str]],
    ) -> List[str]:
        """Format a single ranked process section for HTML output."""
        content = self._join_top_process_entries(entries, field_map)
        return [f"<h4>{html.escape(title)}</h4>", f"<pre>{html.escape(content)}</pre>"]

    def _join_top_process_entries(self, entries: Any, field_map: List[Tuple[str, str]]) -> str:
        """Join process entries into newline-separated rows for HTML blocks."""
        return "\n".join(self._format_top_process_entries_plain(entries, field_map))

    def _format_timestamp(self, timestamp: Optional[float]) -> str:
        """Format a timestamp for reporting.

        Args:
            timestamp: Unix timestamp.

        Returns:
            ISO 8601 formatted time string.
        """
        if not timestamp:
            return "N/A"
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

    def _normalize_severity(self, severity: str) -> str:
        """Normalize severity value.

        Args:
            severity: Severity string.

        Returns:
            Normalized severity.
        """
        return str(severity or "info").lower()

    def _should_send_to_channel(self, channel_name: str, severity: str, notification_key: str) -> bool:
        """Determine if a channel should receive a notification.

        Args:
            channel_name: Channel name.
            severity: Normalized severity.
            notification_key: Notification key.

        Returns:
            True if channel should receive notification, False otherwise.
        """
        channel_config = self.config.get(channel_name, {})
        min_severity = self._normalize_severity(channel_config.get("min_severity", self.default_min_severity))

        if not self._is_severity_allowed(severity, min_severity):
            return False

        rate_limit_config = channel_config.get("rate_limit") or self.rate_limit_config
        channel_key = f"{channel_name}:{notification_key}"
        if not self._check_rate_limit(channel_key, rate_limit_config):
            logger.info("Rate limit exceeded for %s", channel_key)
            return False

        return True

    def _apply_network_defaults(self, channel_config: Dict) -> Dict:
        """Apply shared network defaults to a channel configuration.

        Args:
            channel_config: Channel-specific configuration.

        Returns:
            Updated channel configuration.
        """
        merged_config = dict(channel_config or {})
        merged_config.setdefault("only_ipv4", self.only_ipv4)
        return merged_config

    def _resolve_hostname(self, report: Dict) -> str:
        """Resolve a hostname for report formatting.

        Args:
            report: Report payload.

        Returns:
            Hostname string.
        """
        return report.get("hostname") or self.hostname

    @staticmethod
    def _prepend_hostname(message: str, hostname: str) -> str:
        """Prepend hostname information to a message body.

        Args:
            message: Original message.
            hostname: Hostname value.

        Returns:
            Message with hostname prefix when available.
        """
        if not hostname:
            return message
        return f"Hostname: {hostname}\n\n{message}"

    def _is_severity_allowed(self, severity: str, min_severity: str) -> bool:
        """Check if severity meets minimum level.

        Args:
            severity: Severity value.
            min_severity: Minimum severity.

        Returns:
            True if severity meets minimum, False otherwise.
        """
        severity_rank = self._SEVERITY_RANK.get(severity, 1)
        min_rank = self._SEVERITY_RANK.get(min_severity, 1)
        return severity_rank >= min_rank

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
                        lines.append(f"{'  ' * (indent + 1)}- {self._format_display_value(item)}")
            else:
                lines.append(f"{'  ' * indent}{key}: {self._format_display_value(value)}")
        return "\n".join(lines)

    @staticmethod
    def _format_display_value(value: Any) -> str:
        """Format scalar values for user-facing notification content."""
        if isinstance(value, bool):
            return str(value)

        if isinstance(value, int):
            return f"{value:,}"

        if isinstance(value, float):
            formatted_value = f"{value:,.2f}"
            return formatted_value.rstrip("0").rstrip(".")

        return str(value)

    def _filter_sensitive_content(self, content: str) -> str:
        """Filter sensitive information from content.

        Args:
            content: Content to filter.

        Returns:
            Filtered content.
        """
        if not self.content_filter_config.get("enabled", True):
            return content

        redact_patterns = self.content_filter_config.get("redact_patterns", [])
        redact_replacement = self.content_filter_config.get("redact_replacement", "[REDACTED]")

        filtered_content = content
        for pattern in redact_patterns:
            try:
                filtered_content = re.sub(pattern, redact_replacement, filtered_content, flags=re.IGNORECASE)
            except Exception as e:
                logger.warning(f"Error applying content filter pattern '{pattern}': {str(e)}")

        return filtered_content

    def _filter_dict_content(self, data: Dict[str, Any]) -> Any:
        """Recursively filter sensitive information from dictionaries and lists."""
        if isinstance(data, list):
            filtered_items = []
            for item in data:
                if isinstance(item, (dict, list)):
                    filtered_items.append(self._filter_dict_content(item))
                elif isinstance(item, str):
                    filtered_items.append(self._filter_sensitive_content(item))
                else:
                    filtered_items.append(item)
            return filtered_items

        if not isinstance(data, dict):
            return data

        filtered = {}
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                filtered[key] = self._filter_dict_content(value)
            elif isinstance(value, str):
                filtered[key] = self._filter_sensitive_content(value)
            else:
                filtered[key] = value

        return filtered

    def test_all_channels(self, send_test_message: Optional[bool] = None) -> Dict[str, bool]:
        """Test all notification channels.

        Args:
            send_test_message: Override whether channels should emit a live startup test message.

        Returns:
            Dictionary with channel names and their test results.
        """
        results = {}

        if self.email_notifier:
            logger.info("Testing email notification channel...")
            results["email"] = self.email_notifier.test_connection(send_test_message=send_test_message)

        if self.telegram_notifier:
            logger.info("Testing Telegram notification channel...")
            results["telegram"] = self.telegram_notifier.test_connection(send_test_message=send_test_message)

        if self.webhook_notifier:
            logger.info("Testing webhook notification channel...")
            results["webhook"] = self.webhook_notifier.test_connection(send_test_message=send_test_message)

        if self.slack_notifier:
            logger.info("Testing Slack notification channel...")
            results["slack"] = self.slack_notifier.test_connection(send_test_message=send_test_message)

        if self.discord_notifier:
            logger.info("Testing Discord notification channel...")
            results["discord"] = self.discord_notifier.test_connection(send_test_message=send_test_message)

        return results

    def get_enabled_channels(self) -> List[str]:
        """Get list of enabled notification channels.

        Returns:
            List of enabled channel names.
        """
        channels = []
        if self.email_notifier:
            channels.append("email")
        if self.telegram_notifier:
            channels.append("telegram")
        if self.webhook_notifier:
            channels.append("webhook")
        if self.slack_notifier:
            channels.append("slack")
        if self.discord_notifier:
            channels.append("discord")
        return channels
