"""Alert emails: what each one says, rendered as HTML (templates/alert_email.html) and plain text.

Every value from users (rule name, search, project) is HTML-escaped, so it can't inject markup.
Emails carry counts and the rule's search, never log lines. With SPANPORT_UI_URL set, they also
link to the alert and to the matching logs.
"""

import functools
import html
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from string import Template
from urllib.parse import urlencode

from spanport_server.core.constants import (
    ALERT_EMAIL_BUTTON_TEMPLATE,
    ALERT_EMAIL_ROW_TEMPLATE,
    ALERT_EMAIL_SUBJECT_PREFIX,
    ALERT_EMAIL_TEMPLATE,
    EMAIL_BUTTON_TEXT_COLOR,
    EMAIL_CODE_FONT,
    EMAIL_FIRING_COLOR,
    EMAIL_RESOLVED_COLOR,
    EMAIL_SECONDARY_BUTTON_COLOR,
    EMAIL_TEST_COLOR,
    EMAIL_TEXT_FONT,
    EMAIL_TIME_FORMAT,
    TEMPLATES_DIR,
    UI_ALERTS_ROUTE,
    UI_LOGS_ROUTE,
    UI_MODE_QUERY,
    UI_PARAM_END,
    UI_PARAM_MODE,
    UI_PARAM_PROJECT,
    UI_PARAM_QUERY,
    UI_PARAM_RANGE,
    UI_PARAM_START,
    UI_RANGE_ABSOLUTE,
)
from spanport_server.schemas.alert import AlertRuleRecord
from spanport_server.schemas.tenant import ProjectItem

OPEN_ALERTS_HINT = "Open Alerts in Spanport to say you're on it or to resolve it."


class EmailKind(StrEnum):
    """Which alert email this is; decides the label and colour."""

    FIRING = "Firing"
    RESOLVED = "Resolved"
    TEST = "Test"


@dataclass(frozen=True)
class Detail:
    """One row of the details table; `code` shows the value in a monospace font."""

    label: str
    value: str
    code: bool = False


@dataclass(frozen=True)
class Link:
    """A button in the HTML email and a plain URL in the text one."""

    label: str
    url: str


@dataclass(frozen=True)
class AlertEmail:
    """One alert email, before rendering."""

    kind: EmailKind
    subject: str
    heading: str
    summary: str
    details: tuple[Detail, ...]
    footer: str
    links: tuple[Link, ...] = ()


def accent_color(kind: EmailKind) -> str:
    """The colour of the strip, label and main button: red firing, green resolved, teal test."""
    match kind:
        case EmailKind.FIRING:
            return EMAIL_FIRING_COLOR
        case EmailKind.RESOLVED:
            return EMAIL_RESOLVED_COLOR
        case EmailKind.TEST:
            return EMAIL_TEST_COLOR


def project_label(project: ProjectItem) -> str:
    """e.g. "northwind · hr-portal · production"."""
    return f"{project.client} · {project.project} · {project.environment}"


def condition_text(rule: AlertRuleRecord) -> str:
    """e.g. "more than 20 lines in 5 minutes"."""
    lines = "line" if rule.threshold == 1 else "lines"
    return f"more than {rule.threshold} {lines} in {rule.window_minutes} minutes"


def rule_details(rule: AlertRuleRecord, project: ProjectItem) -> tuple[Detail, ...]:
    """The rows every alert email shows."""
    return (
        Detail("Alert when", condition_text(rule)),
        Detail("Search", rule.query or "any log", code=bool(rule.query)),
        Detail("Project", project_label(project)),
    )


def alert_links(ui_url: str | None, rule: AlertRuleRecord, at: datetime) -> tuple[Link, ...]:
    """Open alert (the project's Alerts page) and See matching logs (the rule's search over the
    window that ends at `at`). None without a UI address.
    """
    if not ui_url:
        return ()
    project = {UI_PARAM_PROJECT: str(rule.project_id)}
    logs = {
        **project,
        UI_PARAM_RANGE: UI_RANGE_ABSOLUTE,
        UI_PARAM_START: (at - timedelta(minutes=rule.window_minutes)).isoformat(),
        UI_PARAM_END: at.isoformat(),
        UI_PARAM_QUERY: rule.query,
        UI_PARAM_MODE: UI_MODE_QUERY,
    }
    return (
        Link("Open alert", f"{ui_url}{UI_ALERTS_ROUTE}?{urlencode(project)}"),
        Link("See matching logs", f"{ui_url}{UI_LOGS_ROUTE}?{urlencode(logs)}"),
    )


def fired_email(
    rule: AlertRuleRecord,
    project: ProjectItem,
    matched: int,
    fired_at: datetime,
    ui_url: str | None = None,
) -> AlertEmail:
    """The email for an alert that just started firing."""
    return AlertEmail(
        kind=EmailKind.FIRING,
        subject=f"{ALERT_EMAIL_SUBJECT_PREFIX} Firing: {rule.name}",
        heading=rule.name,
        summary=f"{matched} log lines matched in the last {rule.window_minutes} minutes.",
        details=(
            Detail("Matched", f"{matched} lines"),
            *rule_details(rule, project),
            Detail("Since", fired_at.strftime(EMAIL_TIME_FORMAT)),
        ),
        footer=OPEN_ALERTS_HINT,
        links=alert_links(ui_url, rule, fired_at),
    )


def resolved_email(
    rule: AlertRuleRecord,
    project: ProjectItem,
    matched: int,
    resolved_at: datetime,
    ui_url: str | None = None,
) -> AlertEmail:
    """The email for an alert that resolved itself."""
    return AlertEmail(
        kind=EmailKind.RESOLVED,
        subject=f"{ALERT_EMAIL_SUBJECT_PREFIX} Resolved: {rule.name}",
        heading=rule.name,
        summary=(
            f"Back within the limit: {matched} log lines in the last {rule.window_minutes} minutes."
        ),
        details=(
            *rule_details(rule, project),
            Detail("Resolved", resolved_at.strftime(EMAIL_TIME_FORMAT)),
        ),
        footer="Nothing to do. The alert resolved itself.",
        links=alert_links(ui_url, rule, resolved_at),
    )


def send_test_email(
    rule: AlertRuleRecord, project: ProjectItem, sent_at: datetime, ui_url: str | None = None
) -> AlertEmail:
    """The email for "Send test"."""
    return AlertEmail(
        kind=EmailKind.TEST,
        subject=f"{ALERT_EMAIL_SUBJECT_PREFIX} Test: {rule.name}",
        heading=rule.name,
        summary="This is a test. If you can read it, this alert reaches you at this address.",
        details=rule_details(rule, project),
        footer="Real alerts look like this, with the number of matching lines and when it started.",
        links=alert_links(ui_url, rule, sent_at),
    )


@functools.cache
def load_template(name: str) -> Template:
    """A template from the templates folder, read once."""
    return Template((TEMPLATES_DIR / name).read_text(encoding="utf-8"))


def render_buttons(email: AlertEmail) -> str:
    """The links as buttons: the first in the alert's colour, the rest dark."""
    button = load_template(ALERT_EMAIL_BUTTON_TEMPLATE)
    return "".join(
        button.substitute(
            href=html.escape(link.url),
            label=html.escape(link.label),
            background=accent_color(email.kind) if index == 0 else EMAIL_SECONDARY_BUTTON_COLOR,
            color=EMAIL_BUTTON_TEXT_COLOR,
        )
        for index, link in enumerate(email.links)
    )


def render_html(email: AlertEmail) -> str:
    """The email as HTML, every value escaped."""
    row = load_template(ALERT_EMAIL_ROW_TEMPLATE)
    rows = "".join(
        row.substitute(
            label=html.escape(detail.label),
            value=html.escape(detail.value),
            font=EMAIL_CODE_FONT if detail.code else EMAIL_TEXT_FONT,
        )
        for detail in email.details
    )
    return load_template(ALERT_EMAIL_TEMPLATE).substitute(
        subject=html.escape(email.subject),
        accent=accent_color(email.kind),
        label=html.escape(email.kind.value),
        heading=html.escape(email.heading),
        summary=html.escape(email.summary),
        rows=rows,
        buttons=render_buttons(email),
        footer=html.escape(email.footer),
    )


def render_text(email: AlertEmail) -> str:
    """The same email as plain text, for clients that don't show HTML."""
    lines = [f"{email.kind.value}: {email.heading}", "", email.summary, ""]
    lines += [f"{detail.label}: {detail.value}" for detail in email.details]
    if email.links:
        lines += ["", *(f"{link.label}: {link.url}" for link in email.links)]
    lines += ["", email.footer]
    return "\n".join(lines)
