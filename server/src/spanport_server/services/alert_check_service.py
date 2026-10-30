"""Checks due log alert rules: counts matching logs and fires or resolves their alerts."""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Protocol

from spanport_server.core.constants import ALERT_CHECK_BATCH, ALERT_CHECK_INTERVAL
from spanport_server.core.errors import DeliveryError, InvalidRequestError, StorageUnavailableError
from spanport_server.core.ids import UuidV7
from spanport_server.schemas.alert import AlertRuleRecord, OpenAlert
from spanport_server.schemas.log_search import LogQuery
from spanport_server.schemas.tenant import ProjectItem
from spanport_server.services.alert_email import AlertEmail, fired_email, resolved_email
from spanport_server.services.alert_notifier import AlertNotifier
from spanport_server.services.alert_rule_service import ProjectFinder
from spanport_server.services.log_query_parser import parse_query

logger = logging.getLogger(__name__)

# fired_email or resolved_email: (rule, project, matched lines, time, UI address) -> the email
type MessageBuilder = Callable[
    [AlertRuleRecord, ProjectItem, int, datetime, str | None], AlertEmail
]


class DueRuleClaimer(Protocol):
    """Hands out rules that are due, so each is checked by one server at a time."""

    async def list_org_ids(self) -> list[UuidV7]:
        """Every organization's id."""
        ...

    async def claim_due_rules(
        self, org_id: UuidV7, now: datetime, next_check_at: datetime, limit: int
    ) -> list[AlertRuleRecord]:
        """Up to `limit` enabled, due rules of the org, now due again at `next_check_at`."""
        ...


class OpenAlertStore(Protocol):
    """A rule's open alert: find, open and resolve it."""

    async def find_open(self, org_id: UuidV7, rule_id: UuidV7) -> OpenAlert | None:
        """The rule's firing or acknowledged alert, or None."""
        ...

    async def open_alert(
        self, org_id: UuidV7, rule_id: UuidV7, matched_count: int
    ) -> OpenAlert | None:
        """A new firing alert, or None when one is already open."""
        ...

    async def resolve(
        self, org_id: UuidV7, event_id: UuidV7, resolved_by: UuidV7 | None, now: datetime
    ) -> bool:
        """Resolve an open alert; False when none matches."""
        ...


class LogCounter(Protocol):
    """Counts stored logs."""

    async def count_by_level(self, query: LogQuery) -> dict[str, int]:
        """Matching logs per level."""
        ...


class AlertCheckService:
    """For each due rule: more than `threshold` matching lines in the window opens an alert
    and emails it; back within the limit resolves it and emails that.
    """

    def __init__(
        self,
        rules: DueRuleClaimer,
        alerts: OpenAlertStore,
        logs: LogCounter,
        projects: ProjectFinder,
        notifier: AlertNotifier,
    ) -> None:
        """Create the service.

        Args:
            rules: Due rules (Postgres).
            alerts: Open alerts (Postgres).
            logs: Log counts (ClickHouse).
            projects: Project names for the emails.
            notifier: Sends the emails.
        """
        self._rules = rules
        self._alerts = alerts
        self._logs = logs
        self._projects = projects
        self._notifier = notifier

    async def check_due_rules(self, now: datetime) -> int:
        """Check every rule that is due, one organization at a time.

        A rule whose logs can't be counted (ClickHouse down) is skipped until its next check;
        its alert state doesn't change.

        Returns:
            How many rules were checked.
        """
        checked = 0
        for org_id in await self._rules.list_org_ids():
            due = await self._rules.claim_due_rules(
                org_id, now, now + ALERT_CHECK_INTERVAL, ALERT_CHECK_BATCH
            )
            for rule in due:
                checked += await self._check_rule(rule, now)
        return checked

    async def _check_rule(self, rule: AlertRuleRecord, now: datetime) -> int:
        """Check one rule; 1 if it was checked, 0 if it had to be skipped."""
        try:
            matched = await self._count(rule, now)
        except (StorageUnavailableError, InvalidRequestError) as error:
            logger.warning("alert check skipped rule=%s reason=%s", rule.id, error.detail)
            return 0
        open_alert = await self._alerts.find_open(rule.org_id, rule.id)
        breaking = matched > rule.threshold
        if breaking and open_alert is None:
            await self._fire(rule, matched, now)
        elif not breaking and open_alert is not None:
            await self._resolve(rule, open_alert, matched, now)
        logger.info(
            "alert rule checked rule=%s project=%s matched=%d threshold=%d firing=%s",
            rule.id,
            rule.project_id,
            matched,
            rule.threshold,
            breaking,
        )
        return 1

    async def _count(self, rule: AlertRuleRecord, now: datetime) -> int:
        """Matching log lines in the rule's window up to now."""
        query = LogQuery(
            org_id=rule.org_id,
            project_id=rule.project_id,
            start=now - timedelta(minutes=rule.window_minutes),
            end=now,
            condition=parse_query(rule.query),
        )
        return sum((await self._logs.count_by_level(query)).values())

    async def _fire(self, rule: AlertRuleRecord, matched: int, now: datetime) -> None:
        alert = await self._alerts.open_alert(rule.org_id, rule.id, matched)
        if alert is None:
            return
        logger.warning(
            "alert firing rule=%s project=%s matched=%d threshold=%d window_minutes=%d",
            rule.id,
            rule.project_id,
            matched,
            rule.threshold,
            rule.window_minutes,
        )
        await self._email(rule, fired_email, matched, alert.fired_at)

    async def _resolve(
        self, rule: AlertRuleRecord, alert: OpenAlert, matched: int, now: datetime
    ) -> None:
        if not await self._alerts.resolve(rule.org_id, alert.id, None, now):
            return
        logger.info("alert resolved itself rule=%s alert=%s matched=%d", rule.id, alert.id, matched)
        await self._email(rule, resolved_email, matched, now)

    async def _email(
        self, rule: AlertRuleRecord, build_message: MessageBuilder, matched: int, at: datetime
    ) -> None:
        """Email the recipients; a failure is logged, the alert stays as recorded."""
        project = await self._projects.find_project(rule.org_id, rule.project_id)
        if project is None:
            return
        try:
            await self._notifier.notify(
                rule, build_message(rule, project, matched, at, self._notifier.ui_url)
            )
        except DeliveryError as error:
            logger.error("alert email failed rule=%s reason=%s", rule.id, error.detail)
