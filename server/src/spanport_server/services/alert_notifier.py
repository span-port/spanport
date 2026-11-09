"""Sends alert emails to a rule's recipients, as HTML with a plain-text fallback.

Rule emails (firing, back to normal, tests) are capped per organization per hour
(SPANPORT_ALERT_MAX_EMAILS_PER_HOUR), so a flapping rule can't flood inboxes or the mail server.
"""

import math
from typing import Protocol

from spanport_server.core.constants import (
    ALERT_EMAIL_CAP_DETAIL,
    ALERT_EMAIL_ORG_RATE_KEY,
    DEFAULT_ALERT_MAX_EMAILS_PER_HOUR,
    EMAIL_NOT_SET_UP_DETAIL,
    SECONDS_PER_HOUR,
)
from spanport_server.core.errors import DeliveryError, EmailCapError
from spanport_server.core.rate_limiter import RateLimit, RateLimiter
from spanport_server.schemas.alert import AlertRuleRecord
from spanport_server.services.alert_email import AlertEmail, render_html, render_text


class EmailSender(Protocol):
    """Sends an email with a plain-text and an HTML version."""

    async def send(self, recipients: list[str], subject: str, text: str, html: str) -> None:
        """Send one email to all recipients; DeliveryError on failure."""
        ...


class AlertNotifier:
    """Emails a rule's recipients."""

    def __init__(
        self,
        email: EmailSender | None,
        ui_url: str | None = None,
        limiter: RateLimiter | None = None,
        emails_per_hour: int = DEFAULT_ALERT_MAX_EMAILS_PER_HOUR,
    ) -> None:
        """Create the notifier.

        Args:
            email: The mail client, or None when the server has no SMTP settings.
            ui_url: Where people open the UI (SPANPORT_UI_URL), for links in emails; or None.
            limiter: Where the hourly counts live; the app passes its own, shared by every
                notifier. Without one, this notifier keeps its own counts.
            emails_per_hour: Rule emails per organization per hour.
        """
        self._email = email
        self._ui_url = ui_url
        self._limiter = limiter or RateLimiter()
        self._hourly = RateLimit(requests=emails_per_hour, window_seconds=SECONDS_PER_HOUR)

    @property
    def email_available(self) -> bool:
        """Whether this server can send email."""
        return self._email is not None

    @property
    def ui_url(self) -> str | None:
        """The UI's address for links in emails, or None (no buttons)."""
        return self._ui_url

    async def notify(self, rule: AlertRuleRecord, email: AlertEmail) -> None:
        """Email the alert to every recipient of the rule, within the organization's hourly cap.

        Raises:
            DeliveryError: Email isn't set up, or the mail server failed.
            EmailCapError: The organization reached its hourly cap; nothing was sent.
        """
        if self._email is None:
            raise DeliveryError(EMAIL_NOT_SET_UP_DETAIL)
        wait_seconds = self._limiter.acquire(
            ALERT_EMAIL_ORG_RATE_KEY.format(org_id=rule.org_id), self._hourly
        )
        if wait_seconds:
            raise EmailCapError(
                ALERT_EMAIL_CAP_DETAIL.format(limit=self._hourly.requests),
                retry_after_seconds=math.ceil(wait_seconds),
            )
        await self._send(list(rule.email_recipients), email)

    async def notify_person(self, address: str, email: AlertEmail) -> None:
        """Email one person, e.g. the one an alert was just assigned to.

        Raises:
            DeliveryError: Email isn't set up, or the mail server failed.
        """
        await self._send([address], email)

    async def _send(self, recipients: list[str], email: AlertEmail) -> None:
        if self._email is None:
            raise DeliveryError(EMAIL_NOT_SET_UP_DETAIL)
        await self._email.send(recipients, email.subject, render_text(email), render_html(email))
