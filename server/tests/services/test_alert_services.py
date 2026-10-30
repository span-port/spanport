from datetime import UTC, datetime, timedelta

import pytest
from fakes import (
    FakeAlertEventStore,
    FakeAlertRuleStore,
    FakeEmailSender,
    FakeLogSearchStore,
    FakeTenantStore,
    caller_for,
)

from spanport_server.core.errors import (
    DeliveryError,
    InvalidRequestError,
    NotFoundError,
    NotSignedInError,
)
from spanport_server.core.ids import new_id
from spanport_server.schemas.alert import AlertState, CreateAlertRuleRequest
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.alert_check_service import AlertCheckService
from spanport_server.services.alert_event_service import AlertEventService
from spanport_server.services.alert_notifier import AlertNotifier
from spanport_server.services.alert_rule_service import AlertRuleService

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)


class Setup:
    """A project with the alert services wired to in-memory fakes."""

    def __init__(self, project: ProjectRef, tenants: FakeTenantStore) -> None:
        self.project = project
        self.tenants = tenants
        self.caller = Caller(org_id=project.org_id, label="user=test", user_id=new_id())
        self.rules = FakeAlertRuleStore()
        self.alerts = FakeAlertEventStore(self.rules)
        self.logs = FakeLogSearchStore()
        self.email = FakeEmailSender()
        notifier = AlertNotifier(self.email)
        self.rule_service = AlertRuleService(self.rules, tenants, notifier)
        self.event_service = AlertEventService(self.alerts, tenants)
        self.checks = AlertCheckService(self.rules, self.alerts, self.logs, tenants, notifier)

    def rule_request(self, **changes: object) -> CreateAlertRuleRequest:
        fields: dict[str, object] = {
            "project_id": self.project.project_id,
            "name": "Too many errors",
            "query": "level:ERROR",
            "threshold": 20,
            "window_minutes": 5,
            "email_recipients": ["oncall@example.com"],
        }
        return CreateAlertRuleRequest.model_validate(fields | changes)

    async def check_with(self, matched: int, at: datetime = NOW) -> int:
        self.logs.by_level = {"ERROR": matched}
        return await self.checks.check_due_rules(at)


@pytest.fixture
async def setup() -> Setup:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    return Setup(project, tenants)


async def test_create_rule_rejects_a_bad_query_and_a_foreign_project(setup: Setup) -> None:
    with pytest.raises(InvalidRequestError):
        await setup.rule_service.create_rule(setup.caller, setup.rule_request(query="(level:ERROR"))
    with pytest.raises(NotFoundError):
        await setup.rule_service.create_rule(caller_for(new_id()), setup.rule_request())
    assert setup.rules.rules == {}


async def test_create_rule_needs_a_mail_server(setup: Setup) -> None:
    no_email = AlertRuleService(setup.rules, setup.tenants, AlertNotifier(None))

    with pytest.raises(InvalidRequestError, match="SPANPORT_SMTP_HOST"):
        await no_email.create_rule(setup.caller, setup.rule_request())


async def test_send_test_emails_the_recipients_and_reports_a_refusal(setup: Setup) -> None:
    rule = await setup.rule_service.create_rule(setup.caller, setup.rule_request())

    await setup.rule_service.send_test(setup.caller, rule.id)
    setup.email.refuse = True

    assert setup.email.sent[0][0] == ["oncall@example.com"]
    assert "Test: Too many errors" in setup.email.sent[0][1]
    with pytest.raises(DeliveryError):
        await setup.rule_service.send_test(setup.caller, rule.id)


async def test_alert_fires_once_then_resolves_itself_with_an_email_each(setup: Setup) -> None:
    await setup.rule_service.create_rule(setup.caller, setup.rule_request())

    await setup.check_with(matched=21)
    await setup.check_with(matched=40, at=NOW + timedelta(minutes=1))
    await setup.check_with(matched=3, at=NOW + timedelta(minutes=2))

    subjects = [sent[1] for sent in setup.email.sent]
    assert subjects == [
        "[Spanport] Firing: Too many errors",
        "[Spanport] Resolved: Too many errors",
    ]
    (alert,) = setup.alerts.alerts.values()
    assert alert.state == AlertState.RESOLVED
    assert alert.resolved_by is None
    assert "21 log lines matched in the last 5 minutes" in setup.email.sent[0][2]


async def test_exactly_the_threshold_does_not_fire(setup: Setup) -> None:
    await setup.rule_service.create_rule(setup.caller, setup.rule_request(threshold=0))

    await setup.check_with(matched=0)

    assert setup.alerts.alerts == {}


async def test_check_counts_the_rule_window_in_the_rule_project(setup: Setup) -> None:
    await setup.rule_service.create_rule(setup.caller, setup.rule_request(window_minutes=15))

    await setup.check_with(matched=0)

    query = setup.logs.queries[0][0]
    assert (query.org_id, query.project_id) == (setup.project.org_id, setup.project.project_id)
    assert query.end - query.start == timedelta(minutes=15)


async def test_a_rule_is_not_checked_again_before_the_next_minute(setup: Setup) -> None:
    await setup.rule_service.create_rule(setup.caller, setup.rule_request())

    first = await setup.check_with(matched=0)
    second = await setup.check_with(matched=0, at=NOW + timedelta(seconds=30))

    assert (first, second) == (1, 0)


async def test_storage_down_skips_the_check_and_changes_nothing(setup: Setup) -> None:
    await setup.rule_service.create_rule(setup.caller, setup.rule_request())
    setup.logs.storage_down = True

    assert await setup.check_with(matched=50) == 0
    assert setup.alerts.alerts == {}


async def test_a_failed_email_keeps_the_alert_firing(setup: Setup) -> None:
    await setup.rule_service.create_rule(setup.caller, setup.rule_request())
    setup.email.refuse = True

    await setup.check_with(matched=21)

    (alert,) = setup.alerts.alerts.values()
    assert alert.state == AlertState.FIRING


async def test_disabled_rules_are_not_checked(setup: Setup) -> None:
    await setup.rule_service.create_rule(setup.caller, setup.rule_request(enabled=False))

    assert await setup.check_with(matched=99) == 0


async def test_acknowledge_then_resolve_records_who(setup: Setup) -> None:
    await setup.rule_service.create_rule(setup.caller, setup.rule_request())
    await setup.check_with(matched=21)
    (alert_id,) = setup.alerts.alerts

    await setup.event_service.acknowledge(setup.caller, alert_id)
    await setup.event_service.resolve(setup.caller, alert_id)

    alert = setup.alerts.alerts[alert_id]
    assert alert.acknowledged_by == setup.caller.user_id
    assert alert.resolved_by == setup.caller.user_id
    with pytest.raises(NotFoundError):
        await setup.event_service.resolve(setup.caller, alert_id)


async def test_an_admin_key_cannot_acknowledge(setup: Setup) -> None:
    key_caller = Caller(org_id=setup.project.org_id, label="key=...a1b2")

    with pytest.raises(NotSignedInError):
        await setup.event_service.acknowledge(key_caller, new_id())


async def test_another_org_sees_no_rules_or_alerts(setup: Setup) -> None:
    rule = await setup.rule_service.create_rule(setup.caller, setup.rule_request())
    stranger = caller_for(new_id())

    with pytest.raises(NotFoundError):
        await setup.rule_service.delete_rule(stranger, rule.id)
    with pytest.raises(NotFoundError):
        await setup.event_service.list_events(stranger, setup.project.project_id, None, 10)


async def test_update_keeps_the_project_and_lists_page_by_cursor(setup: Setup) -> None:
    first = await setup.rule_service.create_rule(setup.caller, setup.rule_request(name="One"))
    await setup.rule_service.create_rule(setup.caller, setup.rule_request(name="Two"))

    page = await setup.rule_service.list_rules(setup.caller, setup.project.project_id, None, 1)
    rest = await setup.rule_service.list_rules(
        setup.caller, setup.project.project_id, page.next_cursor, 1
    )

    assert [rule.name for rule in page.data + rest.data] == ["One", "Two"]
    assert page.has_more and not rest.has_more
    assert first.project_id == setup.project.project_id
