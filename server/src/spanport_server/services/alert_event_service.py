"""Lists a project's alerts and lets people handle them: "I'm on it", assign to someone, and
resolve with a note. Alerts never close themselves; a person resolves each one.
"""

import logging
from datetime import UTC, datetime
from typing import Protocol

from spanport_server.core.constants import (
    MANAGER_ROLES,
    NO_ASSIGNEE_DETAIL,
    NO_OPEN_ALERT_DETAIL,
    NO_PROJECT_DETAIL,
)
from spanport_server.core.errors import (
    DeliveryError,
    InvalidRequestError,
    NotFoundError,
    NotSignedInError,
)
from spanport_server.core.ids import UuidV7
from spanport_server.schemas.alert import (
    AlertEventItem,
    AlertEventListResponse,
    AlertRuleRecord,
    AssigneeItem,
    AssigneeListResponse,
    AssigneeView,
    AssignOutcome,
)
from spanport_server.schemas.auth import Caller
from spanport_server.services.alert_email import assigned_email
from spanport_server.services.alert_notifier import AlertNotifier
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

    async def find_event_rule(self, org_id: UuidV7, event_id: UuidV7) -> AlertRuleRecord | None:
        """The rule that fired this alert, or None when the org has no such alert."""
        ...

    async def acknowledge(
        self, org_id: UuidV7, event_id: UuidV7, user_id: UuidV7, now: datetime
    ) -> bool:
        """Mark a firing alert as handled by (and assigned to) this person; False if none."""
        ...

    async def assign(self, org_id: UuidV7, event_id: UuidV7, user_id: UuidV7) -> AssignOutcome:
        """Give an open alert to this person: ASSIGNED, UNCHANGED (already theirs) or
        NOT_FOUND."""
        ...

    async def resolve(
        self, org_id: UuidV7, event_id: UuidV7, resolved_by: UuidV7, now: datetime, note: str
    ) -> bool:
        """Resolve an open alert with a note; False when none matches."""
        ...


class AssigneeFinder(Protocol):
    """Who a project's alerts can be assigned to."""

    async def list_assignees(self, org_id: UuidV7, project_id: UuidV7) -> list[AssigneeItem]:
        """Everyone the project's alerts can be assigned to, by name."""
        ...

    async def find_assignee(
        self, org_id: UuidV7, project_id: UuidV7, user_id: UuidV7
    ) -> AssigneeItem | None:
        """This person, if the project's alerts can be assigned to them."""
        ...


class AlertEventService:
    """Alert history and the actions people take on an alert."""

    def __init__(
        self,
        events: AlertEventStore,
        projects: ProjectFinder,
        assignees: AssigneeFinder,
        notifier: AlertNotifier,
    ) -> None:
        """Create the service.

        Args:
            events: Alert storage (Postgres).
            projects: Project lookups, so only the caller's organization is visible.
            assignees: Who alerts can be assigned to.
            notifier: Emails the person an alert is assigned to.
        """
        self._events = events
        self._projects = projects
        self._assignees = assignees
        self._notifier = notifier

    async def list_events(
        self, caller: Caller, project_id: UuidV7, cursor: str | None, limit: int
    ) -> AlertEventListResponse:
        """One page of a project's alerts, newest first.

        Raises:
            NotFoundError: The project isn't in the caller's organization.
            InvalidRequestError: The cursor is not valid.
        """
        await self._check_project(caller, project_id)
        before_id = parse_id_cursor(cursor) if cursor else None
        rows = await self._events.list_events(caller.org_id, project_id, before_id, limit + 1)
        page = rows[:limit]
        has_more = len(rows) > limit
        logger.info("alerts listed %s project=%s rows=%d", caller.label, project_id, len(page))
        return AlertEventListResponse(
            data=page, next_cursor=str(page[-1].id) if has_more else None, has_more=has_more
        )

    async def list_assignees(self, caller: Caller, project_id: UuidV7) -> AssigneeListResponse:
        """Everyone the project's alerts can be assigned to. Only owners and admins see their
        emails; members and viewers get names only.

        Raises:
            NotFoundError: The project isn't in the caller's organization.
        """
        await self._check_project(caller, project_id)
        people = await self._assignees.list_assignees(caller.org_id, project_id)
        with_emails = caller.role in MANAGER_ROLES
        logger.info(
            "alert assignees listed %s project=%s rows=%d emails=%s",
            caller.label,
            project_id,
            len(people),
            with_emails,
        )
        return AssigneeListResponse(
            data=[
                AssigneeView(
                    id=person.id, name=person.name, email=person.email if with_emails else None
                )
                for person in people
            ]
        )

    async def acknowledge(self, caller: Caller, event_id: UuidV7) -> None:
        """Say "I'm on it" for a firing alert: it is assigned to the caller.

        Raises:
            NotSignedInError: The caller isn't a signed-in person.
            NotFoundError: No firing alert with this id in the caller's organization.
        """
        user_id = self._person(caller)
        await self._visible_rule(caller, event_id)
        if not await self._events.acknowledge(caller.org_id, event_id, user_id, datetime.now(UTC)):
            raise NotFoundError(NO_OPEN_ALERT_DETAIL)
        logger.info("alert acknowledged %s id=%s", caller.label, event_id)

    async def assign(self, caller: Caller, event_id: UuidV7, assignee_id: UuidV7) -> None:
        """Give an open alert to someone, who is emailed (unless it's the caller, or the alert
        was already theirs, so repeating the call never re-sends the email).

        A failed email is logged; the alert stays assigned.

        Raises:
            NotSignedInError: The caller isn't a signed-in person.
            NotFoundError: No open alert with this id in the caller's organization.
            InvalidRequestError: That person can't be assigned this project's alerts.
        """
        user_id = self._person(caller)
        rule = await self._visible_rule(caller, event_id)
        assignee = await self._assignees.find_assignee(caller.org_id, rule.project_id, assignee_id)
        if assignee is None:
            raise InvalidRequestError(NO_ASSIGNEE_DETAIL)
        outcome = await self._events.assign(caller.org_id, event_id, assignee.id)
        if outcome == AssignOutcome.NOT_FOUND:
            raise NotFoundError(NO_OPEN_ALERT_DETAIL)
        logger.info(
            "alert assigned %s id=%s assignee=%s outcome=%s",
            caller.label,
            event_id,
            assignee.id,
            outcome,
        )
        if outcome == AssignOutcome.ASSIGNED and assignee.id != user_id:
            await self._email_assignee(caller, rule, assignee, user_id)

    async def resolve(self, caller: Caller, event_id: UuidV7, note: str) -> None:
        """Resolve an open alert with a note on what was found. If the logs still break the
        rule, it fires again.

        Raises:
            NotSignedInError: The caller isn't a signed-in person.
            NotFoundError: No open alert with this id in the caller's organization.
        """
        user_id = self._person(caller)
        await self._visible_rule(caller, event_id)
        resolved = await self._events.resolve(
            caller.org_id, event_id, user_id, datetime.now(UTC), note.strip()
        )
        if not resolved:
            raise NotFoundError(NO_OPEN_ALERT_DETAIL)
        logger.info("alert resolved %s id=%s note=%s", caller.label, event_id, bool(note.strip()))

    async def _email_assignee(
        self, caller: Caller, rule: AlertRuleRecord, assignee: AssigneeItem, user_id: UuidV7
    ) -> None:
        """Tell the assignee; a failure is logged, never raised."""
        project = await self._projects.find_project(caller.org_id, rule.project_id)
        assigner = await self._assignees.find_assignee(caller.org_id, rule.project_id, user_id)
        if project is None:
            return
        email = assigned_email(
            rule,
            project,
            assigner.name if assigner else "Someone",
            datetime.now(UTC),
            self._notifier.ui_url,
        )
        try:
            await self._notifier.notify_person(assignee.email, email)
        except DeliveryError as error:
            logger.warning("alert assignment email failed rule=%s reason=%s", rule.id, error.detail)

    async def _check_project(self, caller: Caller, project_id: UuidV7) -> None:
        """A project the caller may not see answers like one that doesn't exist."""
        if not caller.can_see(project_id) or (
            await self._projects.find_project(caller.org_id, project_id) is None
        ):
            raise NotFoundError(NO_PROJECT_DETAIL)

    async def _visible_rule(self, caller: Caller, event_id: UuidV7) -> AlertRuleRecord:
        """The alert's rule; an alert of a project the caller may not see doesn't exist."""
        rule = await self._events.find_event_rule(caller.org_id, event_id)
        if rule is None or not caller.can_see(rule.project_id):
            raise NotFoundError(NO_OPEN_ALERT_DETAIL)
        return rule

    def _person(self, caller: Caller) -> UuidV7:
        """Who is acting; alerts record a person, never a key."""
        if caller.user_id is None:
            raise NotSignedInError("Sign in to acknowledge, assign or resolve alerts.")
        return caller.user_id
