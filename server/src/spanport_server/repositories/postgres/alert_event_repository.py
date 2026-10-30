"""Reads and writes alerts (alert_events). Every query is scoped to one organization."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from spanport_server.core.ids import UuidV7, new_id
from spanport_server.models import AlertEvent, AlertRule, User
from spanport_server.schemas.alert import AlertEventItem, AlertState, OpenAlert

OPEN_STATES = (AlertState.FIRING, AlertState.ACKNOWLEDGED)
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
                    select(AlertEvent.id, AlertEvent.state, AlertEvent.created_at).where(
                        AlertEvent.org_id == org_id,
                        AlertEvent.rule_id == rule_id,
                        AlertEvent.state.in_(OPEN_STATES),
                    )
                )
            ).first()
        return (
            None if row is None else OpenAlert(id=row[0], state=AlertState(row[1]), fired_at=row[2])
        )

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

    async def resolve(
        self, org_id: UuidV7, event_id: UuidV7, resolved_by: UuidV7 | None, now: datetime
    ) -> bool:
        """Resolve an open alert; `resolved_by` None means it resolved itself.

        Returns:
            False when the organization has no open alert with this id.
        """
        async with self._sessionmaker.begin() as session:
            updated = await session.scalar(
                update(AlertEvent)
                .where(
                    AlertEvent.org_id == org_id,
                    AlertEvent.id == event_id,
                    AlertEvent.state.in_(OPEN_STATES),
                )
                .values(state=AlertState.RESOLVED, resolved_at=now, resolved_by=resolved_by)
                .returning(AlertEvent.id)
            )
        return updated is not None

    async def find_event_project(self, org_id: UuidV7, event_id: UuidV7) -> UuidV7 | None:
        """The project whose rule fired this alert, or None when the org has no such alert."""
        async with self._sessionmaker() as session:
            return await session.scalar(
                select(AlertRule.project_id)
                .join(AlertEvent, AlertEvent.rule_id == AlertRule.id)
                .where(AlertEvent.org_id == org_id, AlertEvent.id == event_id)
            )

    async def acknowledge(
        self, org_id: UuidV7, event_id: UuidV7, user_id: UuidV7, now: datetime
    ) -> bool:
        """Mark a firing alert as being handled by this person.

        Returns:
            False when the organization has no firing alert with this id.
        """
        async with self._sessionmaker.begin() as session:
            updated = await session.scalar(
                update(AlertEvent)
                .where(
                    AlertEvent.org_id == org_id,
                    AlertEvent.id == event_id,
                    AlertEvent.state == AlertState.FIRING,
                )
                .values(state=AlertState.ACKNOWLEDGED, acknowledged_at=now, acknowledged_by=user_id)
                .returning(AlertEvent.id)
            )
        return updated is not None

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
                AlertEvent.acknowledged_at,
                ACKNOWLEDGER.name,
                AlertEvent.resolved_at,
                RESOLVER.name,
            )
            .join(AlertRule, AlertRule.id == AlertEvent.rule_id)
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
                acknowledged_at=row[9],
                acknowledged_by=row[10],
                resolved_at=row[11],
                resolved_by=row[12],
            )
            for row in rows
        ]
