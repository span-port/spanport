"""Lists a project's alerts and lets people acknowledge ("I'm on it") and resolve them."""

import logging
from datetime import UTC, datetime
from typing import Protocol

from spanport_server.core.constants import NO_OPEN_ALERT_DETAIL, NO_PROJECT_DETAIL
from spanport_server.core.errors import NotFoundError, NotSignedInError
from spanport_server.core.ids import UuidV7
from spanport_server.schemas.alert import AlertEventItem, AlertEventListResponse
from spanport_server.schemas.auth import Caller
from spanport_server.services.alert_rule_service import ProjectFinder
from spanport_server.services.id_cursor import parse_id_cursor

logger = logging.getLogger(__name__)


class AlertEventStore(Protocol):
    """Reads and changes alerts."""

    async def list_events(
        self, org_id: UuidV7, project_id: UuidV7, before_id: UuidV7 | None, limit: int
    ) -> list[AlertEventItem]:
        """Up to `limit` of the project's alerts older than `before_id`, newest first."""
        ...

    async def find_event_project(self, org_id: UuidV7, event_id: UuidV7) -> UuidV7 | None:
        """The project whose rule fired this alert, or None when the org has no such alert."""
        ...

    async def acknowledge(
        self, org_id: UuidV7, event_id: UuidV7, user_id: UuidV7, now: datetime
    ) -> bool:
        """Mark a firing alert as handled by this person; False when none matches."""
        ...

    async def resolve(
        self, org_id: UuidV7, event_id: UuidV7, resolved_by: UuidV7 | None, now: datetime
    ) -> bool:
        """Resolve an open alert; False when none matches."""
        ...


class AlertEventService:
    """Alert history and the two actions people take on an alert."""

    def __init__(self, events: AlertEventStore, projects: ProjectFinder) -> None:
        """Create the service.

        Args:
            events: Alert storage (Postgres).
            projects: Project lookups, so only the caller's organization is visible.
        """
        self._events = events
        self._projects = projects

    async def list_events(
        self, caller: Caller, project_id: UuidV7, cursor: str | None, limit: int
    ) -> AlertEventListResponse:
        """One page of a project's alerts, newest first.

        Raises:
            NotFoundError: The project isn't in the caller's organization.
            InvalidRequestError: The cursor is not valid.
        """
        if not caller.can_see(project_id) or (
            await self._projects.find_project(caller.org_id, project_id) is None
        ):
            raise NotFoundError(NO_PROJECT_DETAIL)
        before_id = parse_id_cursor(cursor) if cursor else None
        rows = await self._events.list_events(caller.org_id, project_id, before_id, limit + 1)
        page = rows[:limit]
        has_more = len(rows) > limit
        logger.info("alerts listed %s project=%s rows=%d", caller.label, project_id, len(page))
        return AlertEventListResponse(
            data=page, next_cursor=str(page[-1].id) if has_more else None, has_more=has_more
        )

    async def acknowledge(self, caller: Caller, event_id: UuidV7) -> None:
        """Say "I'm on it" for a firing alert, so others know someone is handling it.

        Raises:
            NotSignedInError: The caller isn't a signed-in person.
            NotFoundError: No firing alert with this id in the caller's organization.
        """
        user_id = self._person(caller)
        await self._check_visible(caller, event_id)
        if not await self._events.acknowledge(caller.org_id, event_id, user_id, datetime.now(UTC)):
            raise NotFoundError(NO_OPEN_ALERT_DETAIL)
        logger.info("alert acknowledged %s id=%s", caller.label, event_id)

    async def resolve(self, caller: Caller, event_id: UuidV7) -> None:
        """Resolve an open alert by hand. If the logs still break the rule, it fires again.

        Raises:
            NotSignedInError: The caller isn't a signed-in person.
            NotFoundError: No open alert with this id in the caller's organization.
        """
        user_id = self._person(caller)
        await self._check_visible(caller, event_id)
        if not await self._events.resolve(caller.org_id, event_id, user_id, datetime.now(UTC)):
            raise NotFoundError(NO_OPEN_ALERT_DETAIL)
        logger.info("alert resolved %s id=%s", caller.label, event_id)

    async def _check_visible(self, caller: Caller, event_id: UuidV7) -> None:
        """An alert of a project the caller may not see answers like one that doesn't exist."""
        if caller.project_ids is None:
            return
        project_id = await self._events.find_event_project(caller.org_id, event_id)
        if project_id is None or not caller.can_see(project_id):
            raise NotFoundError(NO_OPEN_ALERT_DETAIL)

    def _person(self, caller: Caller) -> UuidV7:
        """Who is acting; alerts record a person, never a key."""
        if caller.user_id is None:
            raise NotSignedInError("Sign in to acknowledge or resolve alerts.")
        return caller.user_id
