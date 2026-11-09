"""Log alert rules and alerts: API requests and responses, and records passed between layers."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from spanport_server.core.constants import (
    ALERT_EMAILS_CEILING,
    ALERT_WINDOW_CEILING_MINUTES,
    DEFAULT_ALERT_CHECK_SECONDS,
    DEFAULT_ALERT_MAX_EMAILS,
    DEFAULT_ALERT_MAX_RULES_PER_PROJECT,
    DEFAULT_ALERT_MAX_WINDOW_MINUTES,
    EMAIL_PATTERN,
    MAX_ALERT_NAME_LENGTH,
    MAX_ALERT_THRESHOLD,
    MAX_EMAIL_LENGTH,
    MAX_QUERY_LENGTH,
    MAX_RESOLUTION_NOTE_LENGTH,
    SINGLE_LINE_PATTERN,
)
from spanport_server.core.ids import UuidV7

EmailAddress = Annotated[str, Field(max_length=MAX_EMAIL_LENGTH, pattern=EMAIL_PATTERN)]


class AlertState(StrEnum):
    """Firing, then acknowledged (someone is on it), then resolved. Never backwards."""

    FIRING = "firing"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AssignOutcome(StrEnum):
    """What assigning an alert did: changed who has it, nothing (same person), or found no
    open alert."""

    ASSIGNED = "assigned"
    UNCHANGED = "unchanged"
    NOT_FOUND = "not_found"


class AlertRuleFields(BaseModel):
    """What a rule watches and who it emails. `query` uses the Logs search syntax."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_ALERT_NAME_LENGTH, pattern=SINGLE_LINE_PATTERN)
    query: str = Field(default="", max_length=MAX_QUERY_LENGTH, pattern=SINGLE_LINE_PATTERN)
    threshold: int = Field(ge=0, le=MAX_ALERT_THRESHOLD)
    # The ceilings only bound the body; the server's own limits (AlertLimits) are checked after.
    window_minutes: int = Field(ge=1, le=ALERT_WINDOW_CEILING_MINUTES)
    email_recipients: list[EmailAddress] = Field(min_length=1, max_length=ALERT_EMAILS_CEILING)
    enabled: bool = True


class AlertLimits(BaseModel):
    """This server's alert settings (SPANPORT_ALERT_*), also sent to the UI for its form."""

    check_seconds: int = DEFAULT_ALERT_CHECK_SECONDS
    max_emails: int = DEFAULT_ALERT_MAX_EMAILS
    max_window_minutes: int = DEFAULT_ALERT_MAX_WINDOW_MINUTES
    max_rules_per_project: int = DEFAULT_ALERT_MAX_RULES_PER_PROJECT


class CreateAlertRuleRequest(AlertRuleFields):
    """A new rule for one project."""

    project_id: UuidV7


class UpdateAlertRuleRequest(AlertRuleFields):
    """A rule's new settings; its project stays the same."""


@dataclass(frozen=True)
class AlertRuleRecord:
    """A stored rule."""

    id: UuidV7
    org_id: UuidV7
    project_id: UuidV7
    name: str
    query: str
    threshold: int
    window_minutes: int
    email_recipients: tuple[str, ...]
    enabled: bool
    created_at: datetime


class AlertRuleItem(BaseModel):
    """A rule as the API shows it."""

    id: UuidV7
    project_id: UuidV7
    name: str
    query: str
    threshold: int
    window_minutes: int
    email_recipients: list[str]
    enabled: bool
    created_at: datetime


def rule_item(record: AlertRuleRecord) -> AlertRuleItem:
    """The API view of a stored rule."""
    return AlertRuleItem(
        id=record.id,
        project_id=record.project_id,
        name=record.name,
        query=record.query,
        threshold=record.threshold,
        window_minutes=record.window_minutes,
        email_recipients=list(record.email_recipients),
        enabled=record.enabled,
        created_at=record.created_at,
    )


class AlertRuleListResponse(BaseModel):
    """A page of rules. Pass `next_cursor` back to get the next page."""

    data: list[AlertRuleItem]
    next_cursor: str | None
    has_more: bool


class AlertEventItem(BaseModel):
    """One alert, with its rule's current settings and who handled it.

    `recovered_at` is when the logs went back within the rule; the alert stays open until a
    person resolves it. `resolved_by` is None with a `resolved_at` only for alerts that closed
    themselves before alerts waited for a person.
    """

    id: UuidV7
    rule_id: UuidV7
    rule_name: str
    query: str
    threshold: int
    window_minutes: int
    state: AlertState
    matched_count: int
    fired_at: datetime
    recovered_at: datetime | None
    assignee_id: UuidV7 | None
    assigned_to: str | None
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    resolved_at: datetime | None
    resolved_by: str | None
    resolution_note: str | None


class AssignAlertRequest(BaseModel):
    """Who should handle the alert."""

    model_config = ConfigDict(extra="forbid")

    user_id: UuidV7


class ResolveAlertRequest(BaseModel):
    """What was found or done; shown in the alert's history."""

    model_config = ConfigDict(extra="forbid")

    note: str = Field(default="", max_length=MAX_RESOLUTION_NOTE_LENGTH)


class AssigneeItem(BaseModel):
    """Someone an alert can be assigned to."""

    id: UuidV7
    name: str
    email: str


class AssigneeView(BaseModel):
    """Someone an alert can be assigned to, as listed. `email` is shown to owners and admins
    only; everyone else gets None.
    """

    id: UuidV7
    name: str
    email: str | None


class AssigneeListResponse(BaseModel):
    """Everyone a project's alerts can be assigned to, by name. One page holds them all."""

    data: list[AssigneeView]
    next_cursor: None = None
    has_more: bool = False


class AlertEventListResponse(BaseModel):
    """A page of alerts, newest first. Pass `next_cursor` back to get older ones."""

    data: list[AlertEventItem]
    next_cursor: str | None
    has_more: bool


@dataclass(frozen=True)
class OpenAlert:
    """The open (firing or acknowledged) alert of a rule, as the check job needs it.
    `recovered_at` is set while its logs are back within the rule.
    """

    id: UuidV7
    state: AlertState
    fired_at: datetime
    recovered_at: datetime | None = None
