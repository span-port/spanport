"""Alert repositories against a real Postgres (skipped without the dev databases)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spanport_server.repositories.postgres.alert_event_repository import AlertEventRepository
from spanport_server.repositories.postgres.alert_rule_repository import AlertRuleRepository
from spanport_server.repositories.postgres.tenant_repository import TenantRepository
from spanport_server.schemas.alert import AlertRuleFields, AlertState
from spanport_server.schemas.tenant import ProjectRef

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
SETTINGS = AlertRuleFields(
    name="Too many errors",
    query="level:ERROR",
    threshold=20,
    window_minutes=5,
    email_recipients=["oncall@example.com"],
)


async def make_project(sessionmaker: async_sessionmaker[AsyncSession]) -> ProjectRef:
    return await TenantRepository(sessionmaker).get_or_create_project(
        "acme", "northwind", "hr-portal", "production"
    )


async def test_due_rules_are_claimed_once_until_their_next_check(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    project = await make_project(postgres_sessionmaker)
    rules = AlertRuleRepository(postgres_sessionmaker)
    rule = await rules.insert_rule(project.org_id, project.project_id, SETTINGS, NOW)

    first = await rules.claim_due_rules(project.org_id, NOW, NOW + timedelta(minutes=1), 10)
    again = await rules.claim_due_rules(project.org_id, NOW, NOW + timedelta(minutes=1), 10)
    later = await rules.claim_due_rules(
        project.org_id, NOW + timedelta(minutes=1), NOW + timedelta(minutes=2), 10
    )

    assert [r.id for r in first] == [rule.id]
    assert again == []
    assert [r.id for r in later] == [rule.id]
    assert await rules.list_org_ids() == [project.org_id]


async def test_one_open_alert_per_rule_then_acknowledge_and_resolve(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    project = await make_project(postgres_sessionmaker)
    rule = await AlertRuleRepository(postgres_sessionmaker).insert_rule(
        project.org_id, project.project_id, SETTINGS, NOW
    )
    alerts = AlertEventRepository(postgres_sessionmaker)

    opened = await alerts.open_alert(project.org_id, rule.id, 21)
    duplicate = await alerts.open_alert(project.org_id, rule.id, 30)
    assert opened is not None
    resolved = await alerts.resolve(project.org_id, opened.id, None, NOW)
    reopened = await alerts.open_alert(project.org_id, rule.id, 25)

    assert duplicate is None
    assert resolved
    assert reopened is not None
    listed = await alerts.list_events(project.org_id, project.project_id, None, 10)
    assert [(a.state, a.matched_count) for a in listed] == [
        (AlertState.FIRING, 25),
        (AlertState.RESOLVED, 21),
    ]
    assert listed[1].resolved_by is None


async def test_rules_and_alerts_go_with_their_project_and_stay_in_their_org(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    project = await make_project(postgres_sessionmaker)
    other = await TenantRepository(postgres_sessionmaker).get_or_create_project(
        "globex", "globex", "tracking", "production"
    )
    rules = AlertRuleRepository(postgres_sessionmaker)
    rule = await rules.insert_rule(project.org_id, project.project_id, SETTINGS, NOW)
    await AlertEventRepository(postgres_sessionmaker).open_alert(project.org_id, rule.id, 21)

    assert await rules.find_rule(other.org_id, rule.id) is None
    assert not await rules.delete_rule(other.org_id, rule.id)
    assert await TenantRepository(postgres_sessionmaker).delete_project(
        project.org_id, project.project_id
    )
    assert await rules.find_rule(project.org_id, rule.id) is None
