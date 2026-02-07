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

"""Email notification module.

This module provides functionality to send email notifications via SMTP.
"""

import logging
import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Send email notifications via SMTP."""

    def __init__(self, config: Dict):
        """Initialize the email notifier.

        Args:
            config: Email notification configuration dictionary.
        """
        self.config = config
        self.enabled = config.get("enabled", False)
        self.smtp_config = config.get("smtp", {})
        self.from_address = config.get("from_address", "")
        self.from_name = config.get("from_name", "xNetVN Monitor")
        self.to_addresses = config.get("to_addresses", [])
        self.subject_prefix = config.get("subject_prefix", "[xNetVN Monitor]")
        self.hostname = socket.gethostname()

    def send_notification(self, subject: str, message: str, is_html: bool = False) -> bool:
        """Send an email notification.

        Args:
            subject: Email subject.
            message: Email message body.
            is_html: Whether message is HTML format.

        Returns:
            True if email sent successfully, False otherwise.
        """
        if not self.enabled:
            logger.debug("Email notifications are disabled")
            return False

        if not self.to_addresses:
            logger.warning("No recipient addresses configured for email")
            return False

        try:
            # Prepare subject
            full_subject = f"{self.subject_prefix} {subject}"
            if self.config.get("include_hostname", True):
                full_subject += f" [{self.hostname}]"

            # Create message
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{self.from_name} <{self.from_address}>"
            msg["To"] = ", ".join(self.to_addresses)
            msg["Subject"] = full_subject

            # Add message body
            if is_html:
                msg.attach(MIMEText(message, "html"))
            else:
                msg.attach(MIMEText(message, "plain"))

            # Connect to SMTP server and send
            self._send_via_smtp(msg)

            logger.info(f"Email notification sent successfully to {len(self.to_addresses)} recipients")
            return True

        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}", exc_info=True)
            return False

    def _send_via_smtp(self, msg: MIMEMultipart) -> None:
        """Send email via SMTP.

        Args:
            msg: MIME message to send.

        Raises:
            Exception: If email sending fails.
        """
        host = self.smtp_config.get("host", "localhost")
        port = self.smtp_config.get("port", 587)
        username = self.smtp_config.get("username", "")
        password = self.smtp_config.get("password", "")
        use_tls = self.smtp_config.get("use_tls", True)
        use_ssl = self.smtp_config.get("use_ssl", False)
        timeout = self.smtp_config.get("timeout", 30)

        # Create SMTP connection
        if use_ssl:
            smtp = smtplib.SMTP_SSL(host, port, timeout=timeout)
        else:
            smtp = smtplib.SMTP(host, port, timeout=timeout)

        try:
            smtp.ehlo()

            if use_tls and not use_ssl:
                smtp.starttls()
                smtp.ehlo()

            # Authenticate if credentials provided
            if username and password:
                smtp.login(username, password)

            # Send email
            smtp.send_message(msg)

            logger.debug(f"Email sent via SMTP server {host}:{port}")

        finally:
            smtp.quit()

    def send_service_alert(self, service_name: str, status: str, details: str) -> bool:
        """Send a service status alert.

        Args:
            service_name: Name of the service.
            status: Service status (down, restarted, failed).
            details: Detailed information about the service.

        Returns:
            True if notification sent successfully, False otherwise.
        """
        subject = f"Service Alert: {service_name} - {status.upper()}"

        template_format = self.config.get("template", {}).get("format", "plain")
        if template_format == "html":
            message = self._format_html_service_alert(service_name, status, details)
            return self.send_notification(subject, message, is_html=True)
        else:
            message = self._format_plain_service_alert(service_name, status, details)
            return self.send_notification(subject, message, is_html=False)

    def send_resource_alert(self, resource_type: str, details: Dict) -> bool:
        """Send a resource threshold alert.

        Args:
            resource_type: Type of resource (cpu, memory, disk).
            details: Detailed resource information.

        Returns:
            True if notification sent successfully, False otherwise.
        """
        subject = f"Resource Alert: High {resource_type.upper()} Usage"

        template_format = self.config.get("template", {}).get("format", "plain")
        if template_format == "html":
            message = self._format_html_resource_alert(resource_type, details)
            return self.send_notification(subject, message, is_html=True)
        else:
            message = self._format_plain_resource_alert(resource_type, details)
            return self.send_notification(subject, message, is_html=False)

    def _format_plain_service_alert(self, service_name: str, status: str, details: str) -> str:
        """Format plain text service alert message.

        Args:
            service_name: Name of the service.
            status: Service status.
            details: Detailed information.

        Returns:
            Formatted plain text message.
        """
        message = f"""
Service Monitoring Alert
========================

Service: {service_name}
Status: {status.upper()}
Server: {self.hostname}

Details:
{details}

--
xNetVN Monitor Daemon
"""
        return message.strip()

    def _format_html_service_alert(self, service_name: str, status: str, details: str) -> str:
        """Format HTML service alert message.

        Args:
            service_name: Name of the service.
            status: Service status.
            details: Detailed information.

        Returns:
            Formatted HTML message.
        """
        status_color = {
            "down": "#d9534f",
            "restarted": "#f0ad4e",
            "failed": "#d9534f",
            "recovered": "#5cb85c",
        }.get(status.lower(), "#5bc0de")

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: {status_color}; color: white; padding: 20px; text-align: center; }}
        .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
        .footer {{ text-align: center; padding: 10px; color: #666; font-size: 12px; }}
        .info-row {{ margin: 10px 0; }}
        .label {{ font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Service Monitoring Alert</h2>
        </div>
        <div class="content">
            <div class="info-row">
                <span class="label">Service:</span> {service_name}
            </div>
            <div class="info-row">
                <span class="label">Status:</span> {status.upper()}
            </div>
            <div class="info-row">
                <span class="label">Server:</span> {self.hostname}
            </div>
            <hr>
            <div class="info-row">
                <span class="label">Details:</span>
                <pre>{details}</pre>
            </div>
        </div>
        <div class="footer">
            xNetVN Monitor Daemon
        </div>
    </div>
</body>
</html>
"""
        return html.strip()

    def _format_plain_resource_alert(self, resource_type: str, details: Dict) -> str:
        """Format plain text resource alert message.

        Args:
            resource_type: Type of resource.
            details: Resource details.

        Returns:
            Formatted plain text message.
        """
        message = f"""
Resource Monitoring Alert
=========================

Resource Type: {resource_type.upper()}
Server: {self.hostname}

Details:
{self._dict_to_string(details)}

--
xNetVN Monitor Daemon
"""
        return message.strip()

    def _format_html_resource_alert(self, resource_type: str, details: Dict) -> str:
        """Format HTML resource alert message.

        Args:
            resource_type: Type of resource.
            details: Resource details.

        Returns:
            Formatted HTML message.
        """
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #f0ad4e; color: white; padding: 20px; text-align: center; }}
        .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
        .footer {{ text-align: center; padding: 10px; color: #666; font-size: 12px; }}
        .info-row {{ margin: 10px 0; }}
        .label {{ font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Resource Monitoring Alert</h2>
        </div>
        <div class="content">
            <div class="info-row">
                <span class="label">Resource Type:</span> {resource_type.upper()}
            </div>
            <div class="info-row">
                <span class="label">Server:</span> {self.hostname}
            </div>
            <hr>
            <div class="info-row">
                <span class="label">Details:</span>
                <pre>{self._dict_to_string(details)}</pre>
            </div>
        </div>
        <div class="footer">
            xNetVN Monitor Daemon
        </div>
    </div>
</body>
</html>
"""
        return html.strip()

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

    def test_connection(self) -> bool:
        """Test SMTP connection.

        Returns:
            True if connection successful, False otherwise.
        """
        if not self.enabled:
            logger.info("Email notifications are disabled")
            return False

        try:
            host = self.smtp_config.get("host", "localhost")
            port = self.smtp_config.get("port", 587)
            use_ssl = self.smtp_config.get("use_ssl", False)
            timeout = self.smtp_config.get("timeout", 30)

            if use_ssl:
                smtp = smtplib.SMTP_SSL(host, port, timeout=timeout)
            else:
                smtp = smtplib.SMTP(host, port, timeout=timeout)

            smtp.ehlo()
            smtp.quit()

            logger.info(f"Email SMTP connection test successful to {host}:{port}")
            return True

        except Exception as e:
            logger.error(f"Email SMTP connection test failed: {str(e)}")
            return False
