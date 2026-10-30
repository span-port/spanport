"""Log alert rules and alerts: API requests and responses, and records passed between layers."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from spanport_server.core.constants import (
    EMAIL_PATTERN,
    MAX_ALERT_EMAILS,
    MAX_ALERT_NAME_LENGTH,
    MAX_ALERT_THRESHOLD,
    MAX_ALERT_WINDOW_MINUTES,
    MAX_EMAIL_LENGTH,
    MAX_QUERY_LENGTH,
)
from spanport_server.core.ids import UuidV7

EmailAddress = Annotated[str, Field(max_length=MAX_EMAIL_LENGTH, pattern=EMAIL_PATTERN)]


class AlertState(StrEnum):
    """Firing, then acknowledged (someone is on it), then resolved. Never backwards."""

    FIRING = "firing"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AlertRuleFields(BaseModel):
    """What a rule watches and who it emails. `query` uses the Logs search syntax."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_ALERT_NAME_LENGTH)
    query: str = Field(default="", max_length=MAX_QUERY_LENGTH)
    threshold: int = Field(ge=0, le=MAX_ALERT_THRESHOLD)
    window_minutes: int = Field(ge=1, le=MAX_ALERT_WINDOW_MINUTES)
    email_recipients: list[EmailAddress] = Field(min_length=1, max_length=MAX_ALERT_EMAILS)
    enabled: bool = True


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

    `resolved_by` is None with a `resolved_at` when the alert resolved itself.
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
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    resolved_at: datetime | None
    resolved_by: str | None


class AlertEventListResponse(BaseModel):
    """A page of alerts, newest first. Pass `next_cursor` back to get older ones."""

    data: list[AlertEventItem]
    next_cursor: str | None
    has_more: bool


@dataclass(frozen=True)
class OpenAlert:
    """The open (firing or acknowledged) alert of a rule, as the check job needs it."""

    id: UuidV7
    state: AlertState
    fired_at: datetime
