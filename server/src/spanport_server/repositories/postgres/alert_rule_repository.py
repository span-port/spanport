"""Reads and writes log alert rules. Every query on rules is scoped to one organization."""

from datetime import datetime
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spanport_server.core.ids import UuidV7, new_id
from spanport_server.models import AlertRule, Organization
from spanport_server.schemas.alert import AlertRuleFields, AlertRuleRecord

RULE_COLUMNS = (
    AlertRule.id,
    AlertRule.org_id,
    AlertRule.project_id,
    AlertRule.name,
    AlertRule.query,
    AlertRule.threshold,
    AlertRule.window_minutes,
    AlertRule.email_recipients,
    AlertRule.enabled,
    AlertRule.created_at,
)
# The columns a rule's settings write; the same names as the request fields.
SETTINGS_FIELDS = set(AlertRuleFields.model_fields)


def settings_values(settings: AlertRuleFields) -> dict[str, Any]:
    """Column values for a rule's settings (a create request also carries project_id)."""
    return settings.model_dump(include=SETTINGS_FIELDS)


def to_rule_record(row: Any) -> AlertRuleRecord:
    """A row of RULE_COLUMNS as the record services use."""
    values = row._mapping
    return AlertRuleRecord(
        id=values[AlertRule.id],
        org_id=values[AlertRule.org_id],
        project_id=values[AlertRule.project_id],
        name=values[AlertRule.name],
        query=values[AlertRule.query],
        threshold=values[AlertRule.threshold],
        window_minutes=values[AlertRule.window_minutes],
        email_recipients=tuple(values[AlertRule.email_recipients]),
        enabled=values[AlertRule.enabled],
        created_at=values[AlertRule.created_at],
    )


class AlertRuleRepository:
    """alert_rules table access."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Create the repository.

        Args:
            sessionmaker: Opens Postgres sessions.
        """
        self._sessionmaker = sessionmaker

    async def list_rules(
        self, org_id: UuidV7, project_id: UuidV7, after_id: UuidV7 | None, limit: int
    ) -> list[AlertRuleRecord]:
        """One page of a project's rules, oldest first.

        Args:
            org_id: The organization.
            project_id: The project.
            after_id: Continue after this rule id; None for the first page.
            limit: Most rows to return.
        """
        query = (
            select(*RULE_COLUMNS)
            .where(AlertRule.org_id == org_id, AlertRule.project_id == project_id)
            .order_by(AlertRule.id)
            .limit(limit)
        )
        if after_id is not None:
            query = query.where(AlertRule.id > after_id)
        async with self._sessionmaker() as session:
            return [to_rule_record(row) for row in await session.execute(query)]

    async def find_rule(self, org_id: UuidV7, rule_id: UuidV7) -> AlertRuleRecord | None:
        """One rule of this organization, or None."""
        async with self._sessionmaker() as session:
            row = (
                await session.execute(
                    select(*RULE_COLUMNS).where(AlertRule.org_id == org_id, AlertRule.id == rule_id)
                )
            ).first()
        return None if row is None else to_rule_record(row)

    async def insert_rule(
        self,
        org_id: UuidV7,
        project_id: UuidV7,
        settings: AlertRuleFields,
        next_check_at: datetime,
    ) -> AlertRuleRecord:
        """Store a new rule, first checked at `next_check_at`."""
        async with self._sessionmaker.begin() as session:
            row = (
                await session.execute(
                    insert(AlertRule)
                    .values(
                        id=new_id(),
                        org_id=org_id,
                        project_id=project_id,
                        next_check_at=next_check_at,
                        **settings_values(settings),
                    )
                    .returning(*RULE_COLUMNS)
                )
            ).one()
        return to_rule_record(row)

    async def update_rule(
        self,
        org_id: UuidV7,
        rule_id: UuidV7,
        settings: AlertRuleFields,
        next_check_at: datetime,
    ) -> AlertRuleRecord | None:
        """Replace a rule's settings; it is checked again at `next_check_at`.

        Returns:
            The updated rule, or None when the organization has no such rule.
        """
        async with self._sessionmaker.begin() as session:
            row = (
                await session.execute(
                    update(AlertRule)
                    .where(AlertRule.org_id == org_id, AlertRule.id == rule_id)
                    .values(next_check_at=next_check_at, **settings_values(settings))
                    .returning(*RULE_COLUMNS)
                )
            ).first()
        return None if row is None else to_rule_record(row)

    async def delete_rule(self, org_id: UuidV7, rule_id: UuidV7) -> bool:
        """Delete a rule and (by cascade) its alerts. False when there is no such rule."""
        async with self._sessionmaker.begin() as session:
            deleted = await session.scalar(
                delete(AlertRule)
                .where(AlertRule.org_id == org_id, AlertRule.id == rule_id)
                .returning(AlertRule.id)
            )
        return deleted is not None

    async def list_org_ids(self) -> list[UuidV7]:
        """Every organization's id, so the check job can claim rules one organization at a time."""
        async with self._sessionmaker() as session:
            return list(await session.scalars(select(Organization.id).order_by(Organization.id)))

    async def claim_due_rules(
        self, org_id: UuidV7, now: datetime, next_check_at: datetime, limit: int
    ) -> list[AlertRuleRecord]:
        """Take up to `limit` enabled rules that are due and move their next check forward.

        Rows locked by another server are skipped, so two servers never check the same rule.

        Args:
            org_id: The organization.
            now: Rules due at or before this time are taken.
            next_check_at: When the taken rules are due again.
            limit: Most rules to take.
        """
        async with self._sessionmaker.begin() as session:
            due_ids = list(
                await session.scalars(
                    select(AlertRule.id)
                    .where(
                        AlertRule.org_id == org_id,
                        AlertRule.enabled,
                        AlertRule.next_check_at <= now,
                    )
                    .order_by(AlertRule.next_check_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            if not due_ids:
                return []
            rows = await session.execute(
                update(AlertRule)
                .where(AlertRule.org_id == org_id, AlertRule.id.in_(due_ids))
                .values(next_check_at=next_check_at)
                .returning(*RULE_COLUMNS)
            )
            return [to_rule_record(row) for row in rows]
