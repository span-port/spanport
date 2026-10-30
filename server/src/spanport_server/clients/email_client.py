"""Sends alert emails through the SMTP server set in SPANPORT_SMTP_* (stdlib smtplib)."""

import asyncio
import smtplib
from email.message import EmailMessage

from spanport_server.core.config import Settings
from spanport_server.core.constants import (
    NOTIFY_TIMEOUT_SECONDS,
    SMTP_DISCONNECTED_DETAIL,
    SMTP_LOGIN_DETAIL,
    SMTP_OTHER_DETAIL,
    SMTP_RECIPIENTS_DETAIL,
    SMTP_SENDER_DETAIL,
    SMTP_UNREACHABLE_DETAIL,
    SMTPS_PORT,
)
from spanport_server.core.errors import DeliveryError


def failure_detail(error: Exception) -> str:
    """What went wrong with the mail server and which setting to check; never the password."""
    match error:
        case smtplib.SMTPServerDisconnected():
            return SMTP_DISCONNECTED_DETAIL
        case smtplib.SMTPAuthenticationError():
            return SMTP_LOGIN_DETAIL
        case smtplib.SMTPRecipientsRefused():
            return SMTP_RECIPIENTS_DETAIL
        case smtplib.SMTPSenderRefused():
            return SMTP_SENDER_DETAIL
        case smtplib.SMTPException():
            return SMTP_OTHER_DETAIL.format(reason=type(error).__name__)
        case _:
            # OSError: unknown host, connection refused or timed out.
            return SMTP_UNREACHABLE_DETAIL


class EmailClient:
    """One SMTP server; each send opens a connection, so a broken one never lingers."""

    def __init__(self, settings: Settings) -> None:
        """Create the client. Use only when `settings.smtp_host` is set.

        Args:
            settings: Server settings with the SMTP host, port, login and sender address.
        """
        self._settings = settings

    async def send(self, recipients: list[str], subject: str, text: str, html: str) -> None:
        """Send one email to every recipient: HTML, with the plain text for clients that
        don't show HTML (multipart/alternative).

        Raises:
            DeliveryError: The mail server can't be reached or refused the message; the detail
                says which setting to check.
        """
        message = EmailMessage()
        message["From"] = self._settings.smtp_from
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        try:
            # smtplib blocks, so it runs in a thread instead of stalling the event loop.
            await asyncio.to_thread(self._send_blocking, message)
        except (smtplib.SMTPException, OSError) as error:
            raise DeliveryError(failure_detail(error)) from error

    def _send_blocking(self, message: EmailMessage) -> None:
        settings = self._settings
        if settings.smtp_host is None:
            raise DeliveryError("Email isn't set up on this server.")
        with self._connect(settings.smtp_host) as connection:
            if settings.smtp_starttls and settings.smtp_port != SMTPS_PORT:
                connection.starttls()
            if settings.smtp_username and settings.smtp_password:
                connection.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            connection.send_message(message)

    def _connect(self, host: str) -> smtplib.SMTP:
        """Port 465 is TLS from the start (SMTP over SSL); any other port starts plain."""
        port = self._settings.smtp_port
        if port == SMTPS_PORT:
            return smtplib.SMTP_SSL(host, port, timeout=NOTIFY_TIMEOUT_SECONDS)
        return smtplib.SMTP(host, port, timeout=NOTIFY_TIMEOUT_SECONDS)
