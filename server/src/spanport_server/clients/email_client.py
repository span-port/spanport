"""Sends alert emails through the SMTP server set in SPANPORT_SMTP_* (stdlib smtplib)."""

import asyncio
import logging
import re
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage

from spanport_server.core.config import Settings
from spanport_server.core.constants import (
    EMAIL_PATTERN,
    MAX_EMAIL_LENGTH,
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

logger = logging.getLogger(__name__)

PLAIN_ADDRESS = re.compile(EMAIL_PATTERN)


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


def is_plain_address(address: str) -> bool:
    """Whether `address` is exactly one plain address (no display name, list or comment).

    Rules saved before addresses were checked this strictly may still hold such values.
    """
    return len(address) <= MAX_EMAIL_LENGTH and PLAIN_ADDRESS.fullmatch(address) is not None


def one_line(text: str) -> str:
    """`text` with every run of whitespace, CR and LF included, as one space (header-safe)."""
    return " ".join(text.split())


@dataclass
class SendOutcome:
    """How many recipients got the email, and the mail server's refusals of the others."""

    delivered: int = 0
    refusals: list[smtplib.SMTPException] = field(default_factory=list)


class EmailClient:
    """One SMTP server; each send opens a connection, so a broken one never lingers."""

    def __init__(self, settings: Settings) -> None:
        """Create the client. Use only when `settings.smtp_host` is set.

        Args:
            settings: Server settings with the SMTP host, port, login and sender address.
        """
        self._settings = settings

    async def send(self, recipients: list[str], subject: str, text: str, html: str) -> None:
        """Send the email to each recipient as its own message, so nobody sees the others:
        HTML, with the plain text for clients that don't show HTML (multipart/alternative).

        Args:
            recipients: Addresses to send to; any that isn't one plain address is skipped.
            subject: The subject line; line breaks become spaces.
            text: The plain-text version.
            html: The HTML version.

        Raises:
            DeliveryError: The mail server can't be reached, or refused the message for at
                least one recipient; the detail says which setting to check.
        """
        addresses = [address for address in recipients if is_plain_address(address)]
        skipped = len(recipients) - len(addresses)
        messages = [self._message(address, subject, text, html) for address in addresses]
        try:
            # smtplib blocks, so it runs in a thread instead of stalling the event loop.
            outcome = await asyncio.to_thread(self._send_blocking, messages)
        except (smtplib.SMTPException, OSError) as error:
            logger.warning(
                "alert email not sent recipients=%d reason=%s", len(addresses), type(error).__name__
            )
            raise DeliveryError(failure_detail(error)) from error
        logger.info(
            "alert email sent recipients=%d delivered=%d refused=%d skipped=%d",
            len(recipients),
            outcome.delivered,
            len(outcome.refusals),
            skipped,
        )
        if outcome.refusals:
            first = outcome.refusals[0]
            raise DeliveryError(failure_detail(first)) from first

    def _message(self, address: str, subject: str, text: str, html: str) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self._settings.smtp_from
        message["To"] = address
        message["Subject"] = one_line(subject)
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        return message

    def _send_blocking(self, messages: list[EmailMessage]) -> SendOutcome:
        """Send every message over one connection; a recipient the server refuses doesn't
        stop the others. Connection and login failures raise."""
        settings = self._settings
        if settings.smtp_host is None:
            raise DeliveryError("Email isn't set up on this server.")
        outcome = SendOutcome()
        with self._connect(settings.smtp_host) as connection:
            if settings.smtp_starttls and settings.smtp_port != SMTPS_PORT:
                # A verifying context: the server's certificate and host name are checked
                # before the password is sent.
                connection.starttls(context=ssl.create_default_context())
            if settings.smtp_username and settings.smtp_password:
                connection.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            for message in messages:
                try:
                    connection.send_message(message, to_addrs=[str(message["To"])])
                    outcome.delivered += 1
                except (smtplib.SMTPRecipientsRefused, smtplib.SMTPResponseException) as refusal:
                    outcome.refusals.append(refusal)
        return outcome

    def _connect(self, host: str) -> smtplib.SMTP:
        """Port 465 is TLS from the start (SMTP over SSL); any other port starts plain."""
        port = self._settings.smtp_port
        if port == SMTPS_PORT:
            return smtplib.SMTP_SSL(
                host, port, timeout=NOTIFY_TIMEOUT_SECONDS, context=ssl.create_default_context()
            )
        return smtplib.SMTP(host, port, timeout=NOTIFY_TIMEOUT_SECONDS)
