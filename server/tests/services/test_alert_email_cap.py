from datetime import UTC, datetime

import pytest
from fakes import FakeEmailSender

from spanport_server.core.errors import DeliveryError, EmailCapError, RateLimitedError
from spanport_server.core.ids import UuidV7, new_id
from spanport_server.core.rate_limiter import RateLimiter
from spanport_server.schemas.alert import AlertRuleRecord
from spanport_server.services.alert_email import AlertEmail, EmailKind
from spanport_server.services.alert_notifier import AlertNotifier

pytestmark = pytest.mark.anyio

EMAIL = AlertEmail(
    kind=EmailKind.TEST,
    subject="[Spanport] Test",
    heading="Test",
    summary="A test email.",
    details=(),
    footer="",
)


def rule_of(org_id: UuidV7) -> AlertRuleRecord:
    return AlertRuleRecord(
        id=new_id(),
        org_id=org_id,
        project_id=new_id(),
        name="Too many errors",
        query="level:ERROR",
        threshold=20,
        window_minutes=5,
        email_recipients=("oncall@example.com",),
        enabled=True,
        created_at=datetime.now(UTC),
    )


async def test_an_organization_over_its_hourly_cap_sends_nothing_more() -> None:
    sender = FakeEmailSender()
    limiter = RateLimiter()
    notifier = AlertNotifier(sender, limiter=limiter, emails_per_hour=2)
    capped_org, other_org = new_id(), new_id()

    for _ in range(2):
        await notifier.notify(rule_of(capped_org), EMAIL)
    with pytest.raises(EmailCapError) as capped:
        await notifier.notify(rule_of(capped_org), EMAIL)
    # A notifier built for another request shares the app's counts.
    with pytest.raises(EmailCapError):
        await AlertNotifier(sender, limiter=limiter, emails_per_hour=2).notify(
            rule_of(capped_org), EMAIL
        )
    await notifier.notify(rule_of(other_org), EMAIL)

    assert len(sender.sent) == 3
    assert capped.value.retry_after_seconds == 1800


def test_the_cap_is_a_delivery_failure_to_alert_checks_and_a_429_to_people() -> None:
    error = EmailCapError("cap reached", retry_after_seconds=60)

    assert isinstance(error, DeliveryError)
    assert isinstance(error, RateLimitedError)
    assert (error.status, error.code) == (429, "rate_limited")


async def test_without_email_set_up_nothing_is_counted() -> None:
    limiter = RateLimiter()
    org_id = new_id()

    with pytest.raises(DeliveryError, match="isn't set up"):
        await AlertNotifier(None, limiter=limiter, emails_per_hour=1).notify(rule_of(org_id), EMAIL)
    await AlertNotifier(FakeEmailSender(), limiter=limiter, emails_per_hour=1).notify(
        rule_of(org_id), EMAIL
    )
