"""Lists, creates, changes, deletes and tests a project's log alert rules."""

import logging
from datetime import UTC, datetime
from typing import Protocol

from spanport_server.core.constants import (
    EMAIL_NOT_SET_UP_DETAIL,
    NO_ALERT_RULE_DETAIL,
    NO_PROJECT_DETAIL,
)
from spanport_server.core.errors import DeliveryError, InvalidRequestError, NotFoundError
from spanport_server.core.ids import UuidV7
from spanport_server.schemas.alert import (
    AlertRuleFields,
    AlertRuleItem,
    AlertRuleListResponse,
    AlertRuleRecord,
    CreateAlertRuleRequest,
    UpdateAlertRuleRequest,
    rule_item,
)
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.tenant import ProjectItem
from spanport_server.services.alert_email import send_test_email
from spanport_server.services.alert_notifier import AlertNotifier
from spanport_server.services.id_cursor import parse_id_cursor
from spanport_server.services.log_query_parser import parse_query

logger = logging.getLogger(__name__)


class AlertRuleStore(Protocol):
    """Reads and writes alert rules."""

    async def list_rules(
        self, org_id: UuidV7, project_id: UuidV7, after_id: UuidV7 | None, limit: int
    ) -> list[AlertRuleRecord]:
        """Up to `limit` of the project's rules after `after_id`, ordered by id."""
        ...

    async def find_rule(self, org_id: UuidV7, rule_id: UuidV7) -> AlertRuleRecord | None:
        """One rule of the organization, or None."""
        ...

    async def insert_rule(
        self,
        org_id: UuidV7,
        project_id: UuidV7,
        settings: AlertRuleFields,
        next_check_at: datetime,
    ) -> AlertRuleRecord:
        """The new rule."""
        ...

    async def update_rule(
        self,
        org_id: UuidV7,
        rule_id: UuidV7,
        settings: AlertRuleFields,
        next_check_at: datetime,
    ) -> AlertRuleRecord | None:
        """The changed rule, or None when there is no such rule."""
        ...

    async def delete_rule(self, org_id: UuidV7, rule_id: UuidV7) -> bool:
        """Delete the rule and its alerts; False when there is no such rule."""
        ...


class ProjectFinder(Protocol):
    """Finds a project of an organization."""

    async def find_project(self, org_id: UuidV7, project_id: UuidV7) -> ProjectItem | None:
        """The project, or None when the organization has no such project."""
        ...


class AlertRuleService:
    """Owners and admins manage rules; everyone signed in can list them."""

    def __init__(
        self, rules: AlertRuleStore, projects: ProjectFinder, notifier: AlertNotifier
    ) -> None:
        """Create the service.

        Args:
            rules: Rule storage (Postgres).
            projects: Project lookups, so a rule only ever belongs to the caller's org.
            notifier: Sends test messages and tells whether email is set up.
        """
        self._rules = rules
        self._projects = projects
        self._notifier = notifier

    async def list_rules(
        self, caller: Caller, project_id: UuidV7, cursor: str | None, limit: int
    ) -> AlertRuleListResponse:
        """One page of a project's rules.

        Raises:
            NotFoundError: The project isn't in the caller's organization.
            InvalidRequestError: The cursor is not valid.
        """
        await self._project(caller, project_id)
        after_id = parse_id_cursor(cursor) if cursor else None
        rows = await self._rules.list_rules(caller.org_id, project_id, after_id, limit + 1)
        page = rows[:limit]
        has_more = len(rows) > limit
        logger.info("alert rules listed %s project=%s rows=%d", caller.label, project_id, len(page))
        return AlertRuleListResponse(
            data=[rule_item(rule) for rule in page],
            next_cursor=str(page[-1].id) if has_more else None,
            has_more=has_more,
        )

    async def create_rule(self, caller: Caller, request: CreateAlertRuleRequest) -> AlertRuleItem:
        """Add a rule to a project. It is first checked within a minute.

        Raises:
            NotFoundError: The project isn't in the caller's organization.
            InvalidRequestError: Bad query, or email isn't set up on this server.
        """
        await self._project(caller, request.project_id)
        self._check_settings(request)
        rule = await self._rules.insert_rule(
            caller.org_id, request.project_id, request, datetime.now(UTC)
        )
        self._log_saved("created", caller, rule)
        return rule_item(rule)

    async def update_rule(
        self, caller: Caller, rule_id: UuidV7, request: UpdateAlertRuleRequest
    ) -> AlertRuleItem:
        """Change a rule; it is checked again within a minute.

        Raises:
            NotFoundError: No such rule in the caller's organization.
            InvalidRequestError: As for create_rule.
        """
        self._check_settings(request)
        rule = await self._rules.update_rule(caller.org_id, rule_id, request, datetime.now(UTC))
        if rule is None:
            raise NotFoundError(NO_ALERT_RULE_DETAIL)
        self._log_saved("updated", caller, rule)
        return rule_item(rule)

    async def delete_rule(self, caller: Caller, rule_id: UuidV7) -> None:
        """Delete a rule and its alert history.

        Raises:
            NotFoundError: No such rule in the caller's organization.
        """
        if not await self._rules.delete_rule(caller.org_id, rule_id):
            raise NotFoundError(NO_ALERT_RULE_DETAIL)
        logger.info("alert rule deleted %s id=%s", caller.label, rule_id)

    async def send_test(self, caller: Caller, rule_id: UuidV7) -> None:
        """Email a test message to the rule's recipients, so a wrong address shows up now.

        Raises:
            NotFoundError: No such rule in the caller's organization.
            DeliveryError: Email isn't set up or the mail server refused the message.
        """
        rule = await self._find(caller, rule_id)
        project = await self._project(caller, rule.project_id)
        try:
            await self._notifier.notify(
                rule, send_test_email(rule, project, datetime.now(UTC), self._notifier.ui_url)
            )
        except DeliveryError as error:
            logger.warning(
                "alert test failed %s rule=%s emails=%d reason=%s",
                caller.label,
                rule_id,
                len(rule.email_recipients),
                error.detail,
            )
            raise
        logger.info(
            "alert test sent %s rule=%s emails=%d",
            caller.label,
            rule_id,
            len(rule.email_recipients),
        )

    def _check_settings(self, settings: AlertRuleFields) -> None:
        """Reject a rule that can't work: a bad query, or no mail server to send with."""
        parse_query(settings.query)
        if not self._notifier.email_available:
            raise InvalidRequestError(EMAIL_NOT_SET_UP_DETAIL)

    async def _find(self, caller: Caller, rule_id: UuidV7) -> AlertRuleRecord:
        rule = await self._rules.find_rule(caller.org_id, rule_id)
        if rule is None:
            raise NotFoundError(NO_ALERT_RULE_DETAIL)
        return rule

    async def _project(self, caller: Caller, project_id: UuidV7) -> ProjectItem:
        project = await self._projects.find_project(caller.org_id, project_id)
        if project is None or not caller.can_see(project_id):
            raise NotFoundError(NO_PROJECT_DETAIL)
        return project

    def _log_saved(self, action: str, caller: Caller, rule: AlertRuleRecord) -> None:
        logger.info(
            "alert rule %s %s id=%s project=%s threshold=%d window_minutes=%d emails=%d enabled=%s",
            action,
            caller.label,
            rule.id,
            rule.project_id,
            rule.threshold,
            rule.window_minutes,
            len(rule.email_recipients),
            rule.enabled,
        )
