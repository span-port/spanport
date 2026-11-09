"""Reads and writes alerts (alert_events). Every query is scoped to one organization."""

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from spanport_server.core.ids import UuidV7, new_id
from spanport_server.models import AlertEvent, AlertRule, User
from spanport_server.repositories.postgres.alert_rule_repository import RULE_COLUMNS, to_rule_record
from spanport_server.schemas.alert import AlertEventItem, AlertRuleRecord, AlertState, OpenAlert

OPEN_STATES = (AlertState.FIRING, AlertState.ACKNOWLEDGED)
ASSIGNEE = aliased(User)
ACKNOWLEDGER = aliased(User)
RESOLVER = aliased(User)


class AlertEventRepository:
    """alert_events table access."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Create the repository.

        Args:
            sessionmaker: Opens Postgres sessions.
        """
        self._sessionmaker = sessionmaker

    async def find_open(self, org_id: UuidV7, rule_id: UuidV7) -> OpenAlert | None:
        """The rule's firing or acknowledged alert, or None."""
        async with self._sessionmaker() as session:
            row = (
                await session.execute(
                    select(
                        AlertEvent.id,
                        AlertEvent.state,
                        AlertEvent.created_at,
                        AlertEvent.recovered_at,
                    ).where(
                        AlertEvent.org_id == org_id,
                        AlertEvent.rule_id == rule_id,
                        AlertEvent.state.in_(OPEN_STATES),
                    )
                )
            ).first()
        if row is None:
            return None
        return OpenAlert(id=row[0], state=AlertState(row[1]), fired_at=row[2], recovered_at=row[3])

    async def open_alert(
        self, org_id: UuidV7, rule_id: UuidV7, matched_count: int
    ) -> OpenAlert | None:
        """Start a firing alert for the rule.

        Returns:
            The new alert, or None when the rule already has an open one (a unique index
            allows one), e.g. another server opened it a moment earlier.
        """
        async with self._sessionmaker.begin() as session:
            row = (
                await session.execute(
                    insert(AlertEvent)
                    .values(
                        id=new_id(),
                        org_id=org_id,
                        rule_id=rule_id,
                        state=AlertState.FIRING,
                        matched_count=matched_count,
                    )
                    .on_conflict_do_nothing()
                    .returning(AlertEvent.id, AlertEvent.created_at)
                )
            ).first()
        return (
            None if row is None else OpenAlert(id=row[0], state=AlertState.FIRING, fired_at=row[1])
        )

    async def mark_recovered(self, org_id: UuidV7, event_id: UuidV7, now: datetime) -> bool:
        """Note that an open alert's logs are back within its rule; it stays open.

        Returns:
            False when it isn't open or was already marked.
        """
        return await self._update_open(
            org_id, event_id, {"recovered_at": now}, AlertEvent.recovered_at.is_(None)
        )

    async def mark_breaking_again(
        self, org_id: UuidV7, event_id: UuidV7, matched_count: int
    ) -> bool:
        """An open alert that had gone back to normal breaks its rule again.

        Returns:
            False when it isn't open or wasn't back to normal.
        """
        return await self._update_open(
            org_id,
            event_id,
            {"recovered_at": None, "matched_count": matched_count},
            AlertEvent.recovered_at.is_not(None),
        )

    async def assign(self, org_id: UuidV7, event_id: UuidV7, user_id: UuidV7) -> bool:
        """Give an open alert to this person.

        Returns:
            False when the organization has no open alert with this id.
        """
        return await self._update_open(org_id, event_id, {"assigned_to": user_id})

    async def acknowledge(
        self, org_id: UuidV7, event_id: UuidV7, user_id: UuidV7, now: datetime
    ) -> bool:
        """Mark a firing alert as being handled by this person, and assign it to them.

        Returns:
            False when the organization has no firing alert with this id.
        """
        values = {
            "state": AlertState.ACKNOWLEDGED,
            "acknowledged_at": now,
            "acknowledged_by": user_id,
            "assigned_to": user_id,
        }
        return await self._update_open(
            org_id, event_id, values, AlertEvent.state == AlertState.FIRING
        )

    async def resolve(
        self, org_id: UuidV7, event_id: UuidV7, resolved_by: UuidV7, now: datetime, note: str
    ) -> bool:
        """Resolve an open alert, with what the person found or did.

        Returns:
            False when the organization has no open alert with this id.
        """
        values = {
            "state": AlertState.RESOLVED,
            "resolved_at": now,
            "resolved_by": resolved_by,
            "resolution_note": note or None,
        }
        return await self._update_open(org_id, event_id, values)

    async def find_event_rule(self, org_id: UuidV7, event_id: UuidV7) -> AlertRuleRecord | None:
        """The rule that fired this alert, or None when the org has no such alert."""
        async with self._sessionmaker() as session:
            row = (
                await session.execute(
                    select(*RULE_COLUMNS)
                    .join(AlertEvent, AlertEvent.rule_id == AlertRule.id)
                    .where(AlertEvent.org_id == org_id, AlertEvent.id == event_id)
                )
            ).first()
        return None if row is None else to_rule_record(row)

    async def list_events(
        self, org_id: UuidV7, project_id: UuidV7, before_id: UuidV7 | None, limit: int
    ) -> list[AlertEventItem]:
        """One page of a project's alerts, newest first, with who handled them.

        Args:
            org_id: The organization.
            project_id: The project whose rules fired them.
            before_id: Continue with alerts older than this id; None for the first page.
            limit: Most rows to return.
        """
        query = (
            select(
                AlertEvent.id,
                AlertEvent.rule_id,
                AlertRule.name,
                AlertRule.query,
                AlertRule.threshold,
                AlertRule.window_minutes,
                AlertEvent.state,
                AlertEvent.matched_count,
                AlertEvent.created_at,
                AlertEvent.recovered_at,
                AlertEvent.assigned_to,
                ASSIGNEE.name,
                AlertEvent.acknowledged_at,
                ACKNOWLEDGER.name,
                AlertEvent.resolved_at,
                RESOLVER.name,
                AlertEvent.resolution_note,
            )
            .join(AlertRule, AlertRule.id == AlertEvent.rule_id)
            .outerjoin(ASSIGNEE, ASSIGNEE.id == AlertEvent.assigned_to)
            .outerjoin(ACKNOWLEDGER, ACKNOWLEDGER.id == AlertEvent.acknowledged_by)
            .outerjoin(RESOLVER, RESOLVER.id == AlertEvent.resolved_by)
            .where(AlertEvent.org_id == org_id, AlertRule.project_id == project_id)
            .order_by(AlertEvent.id.desc())
            .limit(limit)
        )
        if before_id is not None:
            query = query.where(AlertEvent.id < before_id)
        async with self._sessionmaker() as session:
            rows = (await session.execute(query)).all()
        return [
            AlertEventItem(
                id=row[0],
                rule_id=row[1],
                rule_name=row[2],
                query=row[3],
                threshold=row[4],
                window_minutes=row[5],
                state=AlertState(row[6]),
                matched_count=row[7],
                fired_at=row[8],
                recovered_at=row[9],
                assignee_id=row[10],
                assigned_to=row[11],
                acknowledged_at=row[12],
                acknowledged_by=row[13],
                resolved_at=row[14],
                resolved_by=row[15],
                resolution_note=row[16],
            )
            for row in rows
        ]

    async def _update_open(
        self, org_id: UuidV7, event_id: UuidV7, values: dict[str, Any], *conditions: Any
    ) -> bool:
        """Change an open alert of the org; False when none matches (and the conditions)."""
        async with self._sessionmaker.begin() as session:
            updated = await session.scalar(
                update(AlertEvent)
                .where(
                    AlertEvent.org_id == org_id,
                    AlertEvent.id == event_id,
                    AlertEvent.state.in_(OPEN_STATES),
                    *conditions,
                )
                .values(**values)
                .returning(AlertEvent.id)
            )
        return updated is not None
