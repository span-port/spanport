"""Sends alert emails to a rule's recipients, as HTML with a plain-text fallback."""

from typing import Protocol

from spanport_server.core.constants import EMAIL_NOT_SET_UP_DETAIL
from spanport_server.core.errors import DeliveryError
from spanport_server.schemas.alert import AlertRuleRecord
from spanport_server.services.alert_email import AlertEmail, render_html, render_text


class EmailSender(Protocol):
    """Sends an email with a plain-text and an HTML version."""

    async def send(self, recipients: list[str], subject: str, text: str, html: str) -> None:
        """Send one email to all recipients; DeliveryError on failure."""
        ...


class AlertNotifier:
    """Emails a rule's recipients."""

    def __init__(self, email: EmailSender | None, ui_url: str | None = None) -> None:
        """Create the notifier.

        Args:
            email: The mail client, or None when the server has no SMTP settings.
            ui_url: Where people open the UI (SPANPORT_UI_URL), for links in emails; or None.
        """
        self._email = email
        self._ui_url = ui_url

    @property
    def email_available(self) -> bool:
        """Whether this server can send email."""
        return self._email is not None

    @property
    def ui_url(self) -> str | None:
        """The UI's address for links in emails, or None (no buttons)."""
        return self._ui_url

    async def notify(self, rule: AlertRuleRecord, email: AlertEmail) -> None:
        """Email the alert to every recipient of the rule.

        Raises:
            DeliveryError: Email isn't set up, or the mail server failed.
        """
        if self._email is None:
            raise DeliveryError(EMAIL_NOT_SET_UP_DETAIL)
        await self._email.send(
            list(rule.email_recipients), email.subject, render_text(email), render_html(email)
        )
