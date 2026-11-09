from collections.abc import AsyncIterator

import httpx
import pytest
from fakes import (
    FakeAlertEventStore,
    FakeAlertRuleStore,
    FakeAssigneeStore,
    FakeEmailSender,
    FakeSessionStore,
    FakeStorageStore,
    FakeTenantStore,
    FakeUserStore,
)

from spanport_server.core.passwords import hash_password
from spanport_server.dependencies import (
    get_alert_event_service,
    get_alert_rule_service,
    get_auth_service,
    get_storage_service,
)
from spanport_server.main import create_app
from spanport_server.schemas.auth import Role
from spanport_server.services.alert_event_service import AlertEventService
from spanport_server.services.alert_notifier import AlertNotifier
from spanport_server.services.alert_rule_service import AlertRuleService
from spanport_server.services.auth_service import AuthService
from spanport_server.services.storage_service import StorageService

pytestmark = pytest.mark.anyio

PASSWORD = "a long enough passphrase"


class Browser:
    """A browser that signs in and sends the CSRF header like the UI does."""

    def __init__(self, client: httpx.AsyncClient, project_id: str, email: FakeEmailSender) -> None:
        self.client = client
        self.project_id = project_id
        self.email = email

    async def sign_in(self, email: str) -> None:
        response = await self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        assert response.status_code == 200

    async def send(self, method: str, path: str, body: object = None) -> httpx.Response:
        headers = {"X-CSRF-Token": self.client.cookies["__Host-sp_csrf"]}
        return await self.client.request(method, path, json=body, headers=headers)

    def rule(self, **changes: object) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "name": "Too many errors",
            "query": "level:ERROR",
            "threshold": 20,
            "window_minutes": 5,
            "email_recipients": ["oncall@example.com"],
        } | changes


@pytest.fixture
async def browser() -> AsyncIterator[Browser]:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    users = FakeUserStore()
    for address, role in (
        ("owner@example.com", Role.OWNER),
        ("member@example.com", Role.MEMBER),
        ("viewer@example.com", Role.VIEWER),
    ):
        users.add_user(address, hash_password(PASSWORD), role=role, org_id=project.org_id)
    rules = FakeAlertRuleStore()
    email = FakeEmailSender()
    auth = AuthService(users, FakeSessionStore())
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_alert_rule_service] = lambda: AlertRuleService(
        rules, tenants, AlertNotifier(email)
    )
    app.dependency_overrides[get_storage_service] = lambda: StorageService(
        tenants, FakeStorageStore()
    )
    app.dependency_overrides[get_alert_event_service] = lambda: AlertEventService(
        FakeAlertEventStore(rules), tenants, FakeAssigneeStore(), AlertNotifier(email)
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://test") as client:
        yield Browser(client, str(project.project_id), email)


async def test_owner_creates_lists_tests_and_deletes_a_rule(browser: Browser) -> None:
    await browser.sign_in("owner@example.com")

    created = await browser.send("POST", "/api/v1/alert-rules", browser.rule())
    rule_id = created.json()["id"]
    listing = await browser.client.get(
        "/api/v1/alert-rules", params={"project_id": browser.project_id}
    )
    tested = await browser.send("POST", f"/api/v1/alert-rules/{rule_id}/test")
    deleted = await browser.send("DELETE", f"/api/v1/alert-rules/{rule_id}")

    assert created.status_code == 201
    assert [rule["name"] for rule in listing.json()["data"]] == ["Too many errors"]
    assert tested.status_code == 204
    assert len(browser.email.sent) == 1
    assert deleted.status_code == 204


async def test_a_bad_email_names_the_field_without_echoing_it(browser: Browser) -> None:
    await browser.sign_in("owner@example.com")

    response = await browser.send(
        "POST", "/api/v1/alert-rules", browser.rule(email_recipients=["not-an-email"])
    )

    assert response.status_code == 400
    assert "email_recipients" in response.json()["detail"]
    assert "not-an-email" not in response.text


async def test_a_member_cannot_manage_rules_and_a_viewer_cannot_resolve(browser: Browser) -> None:
    await browser.sign_in("member@example.com")
    member_create = await browser.send("POST", "/api/v1/alert-rules", browser.rule())
    await browser.sign_in("viewer@example.com")
    viewer_resolve = await browser.send(
        "POST", "/api/v1/alert-events/0192f1c4-0000-7000-8000-000000000000/resolve", {"note": ""}
    )
    viewer_assign = await browser.send(
        "POST",
        "/api/v1/alert-events/0192f1c4-0000-7000-8000-000000000000/assign",
        {"user_id": "0192f1c4-0000-7000-8000-000000000001"},
    )
    viewer_list = await browser.client.get(
        "/api/v1/alert-events", params={"project_id": browser.project_id}
    )
    assignees = await browser.client.get(
        "/api/v1/alert-assignees", params={"project_id": browser.project_id}
    )

    assert member_create.status_code == 403
    assert viewer_resolve.json()["code"] == "insufficient_role"
    assert viewer_assign.json()["code"] == "insufficient_role"
    assert viewer_list.status_code == 200
    assert assignees.json() == {"data": [], "next_cursor": None, "has_more": False}


async def test_a_member_resolving_a_missing_alert_gets_404_and_a_long_note_400(
    browser: Browser,
) -> None:
    await browser.sign_in("member@example.com")
    path = "/api/v1/alert-events/0192f1c4-0000-7000-8000-000000000000/resolve"

    missing = await browser.send("POST", path, {"note": "Rotated the key"})
    too_long = await browser.send("POST", path, {"note": "x" * 2001})

    assert missing.status_code == 404
    assert too_long.status_code == 400


async def test_alerts_need_a_session(browser: Browser) -> None:
    response = await browser.client.get(
        "/api/v1/alert-events", params={"project_id": browser.project_id}
    )
    settings = await browser.client.get("/api/v1/alert-settings")

    assert response.status_code == 401
    assert settings.status_code == 401


async def test_only_owners_and_admins_see_storage(browser: Browser) -> None:
    await browser.sign_in("member@example.com")
    member = await browser.client.get("/api/v1/storage")
    await browser.sign_in("owner@example.com")
    owner = await browser.client.get("/api/v1/storage")

    assert member.json()["code"] == "insufficient_role"
    assert owner.status_code == 200
    assert [item["project"] for item in owner.json()["projects"]] == ["hr-portal"]


async def test_anyone_signed_in_reads_the_alert_settings(browser: Browser) -> None:
    await browser.sign_in("viewer@example.com")

    response = await browser.client.get("/api/v1/alert-settings")

    assert response.json() == {
        "check_seconds": 10,
        "max_emails": 10,
        "max_window_minutes": 60,
        "max_rules_per_project": 50,
    }
