from collections.abc import AsyncIterator

import httpx
import pytest
from fakes import (
    FakeApiKeyStore,
    FakeLogWriter,
    FakeSessionStore,
    FakeTenantStore,
    FakeUserStore,
)

from spanport_server.core.passwords import hash_password
from spanport_server.dependencies import (
    get_api_key_service,
    get_auth_service,
    get_project_service,
)
from spanport_server.main import create_app
from spanport_server.schemas.auth import Role
from spanport_server.services.api_key_service import ApiKeyService
from spanport_server.services.auth_service import AuthService
from spanport_server.services.project_service import ProjectService

pytestmark = pytest.mark.anyio

PASSWORD = "a long enough passphrase"


class Browser:
    """A signed-in browser: sends the CSRF header like the UI does."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def sign_in(self, email: str) -> None:
        response = await self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        assert response.status_code == 200

    async def post(self, path: str, body: object = None) -> httpx.Response:
        headers = {"X-CSRF-Token": self.client.cookies["__Host-sp_csrf"]}
        return await self.client.post(path, json=body, headers=headers)


@pytest.fixture
async def browser() -> AsyncIterator[Browser]:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    users = FakeUserStore()
    for email, role in (("owner@example.com", Role.OWNER), ("member@example.com", Role.MEMBER)):
        users.add_user(email, hash_password(PASSWORD), role=role, org_id=project.org_id)
    auth = AuthService(users, FakeSessionStore())
    keys = ApiKeyService(tenants, FakeApiKeyStore())
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_api_key_service] = lambda: keys
    app.dependency_overrides[get_project_service] = lambda: ProjectService(tenants, FakeLogWriter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://test") as client:
        yield Browser(client)


async def test_owner_creates_a_project_then_a_data_key_shown_only_once(browser: Browser) -> None:
    await browser.sign_in("owner@example.com")

    project = await browser.post(
        "/api/v1/projects",
        {"client": "globex", "project": "tracking-api", "environment": "production"},
    )
    duplicate = await browser.post(
        "/api/v1/projects",
        {"client": "globex", "project": "tracking-api", "environment": "production"},
    )
    created = await browser.post(
        "/api/v1/api-keys",
        {"name": "tracking-prod", "key_type": "ingest", "project_id": project.json()["id"]},
    )
    listing = await browser.client.get("/api/v1/api-keys")

    assert project.status_code == 201
    assert duplicate.status_code == 409
    assert created.status_code == 201
    raw_key = created.json()["key"]
    assert raw_key.startswith("sp_ingest_")
    assert listing.status_code == 200
    assert listing.json()["data"][0]["name"] == "tracking-prod"
    assert raw_key not in listing.text


async def test_revoking_twice_is_a_404(browser: Browser) -> None:
    await browser.sign_in("owner@example.com")
    created = await browser.post(
        "/api/v1/api-keys", {"name": "ci", "key_type": "admin", "scopes": ["logs:read"]}
    )
    key_id = created.json()["item"]["id"]

    first = await browser.post(f"/api/v1/api-keys/{key_id}/revoke")
    second = await browser.post(f"/api/v1/api-keys/{key_id}/revoke")

    assert first.status_code == 204
    assert second.status_code == 404


async def test_members_and_signed_out_people_cannot_manage(browser: Browser) -> None:
    signed_out = await browser.client.get("/api/v1/api-keys")
    await browser.sign_in("member@example.com")
    member_list = await browser.client.get("/api/v1/api-keys")
    member_create = await browser.post(
        "/api/v1/projects", {"client": "globex", "project": "x", "environment": "production"}
    )

    assert signed_out.status_code == 401
    assert member_list.status_code == 403
    assert member_list.json()["code"] == "insufficient_role"
    assert member_create.status_code == 403


async def test_project_names_must_be_slugs(browser: Browser) -> None:
    await browser.sign_in("owner@example.com")

    response = await browser.post(
        "/api/v1/projects", {"client": "Globex Ltd", "project": "x", "environment": "production"}
    )

    assert response.status_code == 400
    assert "client" in response.json()["detail"]
    assert "Globex Ltd" not in response.text
