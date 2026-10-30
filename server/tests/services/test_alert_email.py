from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

from spanport_server.core.ids import new_id
from spanport_server.schemas.alert import AlertRuleRecord
from spanport_server.schemas.tenant import ProjectItem
from spanport_server.services.alert_email import (
    fired_email,
    render_html,
    render_text,
    resolved_email,
    send_test_email,
)

FIRED_AT = datetime(2026, 10, 30, 14, 21, tzinfo=UTC)
PROJECT = ProjectItem(id=new_id(), client="northwind", project="hr-portal", environment="prod")


def rule(name: str = "Too many errors", query: str = "level:ERROR") -> AlertRuleRecord:
    return AlertRuleRecord(
        id=new_id(),
        org_id=new_id(),
        project_id=PROJECT.id,
        name=name,
        query=query,
        threshold=20,
        window_minutes=5,
        email_recipients=("oncall@example.com",),
        enabled=True,
        created_at=FIRED_AT,
    )


def test_a_firing_email_says_what_matched_where_and_since_when() -> None:
    email = fired_email(rule(), PROJECT, 37, FIRED_AT)
    html = render_html(email)
    text = render_text(email)

    assert email.subject == "[Spanport] Firing: Too many errors"
    for part in ("Firing", "37 lines", "level:ERROR", "northwind · hr-portal · prod"):
        assert part in html
        assert part in text
    assert "2026-10-30 14:21 UTC" in text
    assert "#e5484d" in html  # red strip and label


def test_resolved_and_test_emails_use_their_own_label_and_colour() -> None:
    resolved = render_html(resolved_email(rule(), PROJECT, 3, FIRED_AT))
    tested = render_html(send_test_email(rule(), PROJECT, FIRED_AT))

    assert "Resolved" in resolved and "#30a46c" in resolved
    assert "Test" in tested and "#12a594" in tested


def test_names_and_searches_typed_by_users_cannot_inject_html() -> None:
    hostile = rule(name="<script>alert(1)</script>", query='message:"<b>x</b>"')

    html = render_html(fired_email(hostile, PROJECT, 25, FIRED_AT))

    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<b>x</b>" not in html


def test_an_empty_search_reads_as_any_log() -> None:
    assert "Search: any log" in render_text(send_test_email(rule(query=""), PROJECT, FIRED_AT))


def test_with_a_ui_address_the_email_links_to_the_alert_and_the_matching_logs() -> None:
    alert_rule = rule()
    email = fired_email(alert_rule, PROJECT, 37, FIRED_AT, "https://spanport.acme.com")

    open_alert, matching_logs = email.links
    query = parse_qs(urlsplit(matching_logs.url).query)
    assert open_alert.url == f"https://spanport.acme.com/alerts?project={PROJECT.id}"
    assert urlsplit(matching_logs.url).path == "/logs"
    assert query["query"] == ["level:ERROR"]
    assert query["mode"] == ["query"]
    assert query["range"] == ["absolute"]
    assert query["start"] == ["2026-10-30T14:16:00+00:00"]
    assert query["end"] == ["2026-10-30T14:21:00+00:00"]
    html = render_html(email)
    assert ">Open alert</a>" in html and ">See matching logs</a>" in html
    assert "&amp;mode=query" in html  # the href is escaped
    assert f"Open alert: https://spanport.acme.com/alerts?project={PROJECT.id}" in render_text(
        email
    )


def test_without_a_ui_address_there_are_no_buttons() -> None:
    email = fired_email(rule(), PROJECT, 37, FIRED_AT)

    assert email.links == ()
    assert "<a " not in render_html(email)
