from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fakes import (
    FakeApiKeyStore,
    FakeLogSearchStore,
    FakeSessionStore,
    FakeTenantStore,
    FakeUserStore,
)
from fastapi import FastAPI

from spanport_server.core.passwords import hash_password
from spanport_server.dependencies import (
    get_api_key_auth_service,
    get_auth_service,
    get_log_search_service,
)
from spanport_server.main import create_app
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.api_key_auth_service import ApiKeyAuthService
from spanport_server.services.auth_service import AuthService
from spanport_server.services.log_search_service import LogSearchService

pytestmark = pytest.mark.anyio

PASSWORD = "a long enough passphrase"
EMAIL = "sam@example.com"


class Setup:
    def __init__(self, client: httpx.AsyncClient, app: FastAPI, project: ProjectRef) -> None:
        self.client = client
        self.app = app
        self.project = project

    async def login(self) -> httpx.Response:
        return await self.client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )

    def search_body(self) -> dict[str, str]:
        now = datetime.now(UTC)
        return {
            "project_id": str(self.project.project_id),
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        }


@pytest.fixture
async def setup() -> AsyncIterator[Setup]:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    users = FakeUserStore()
    users.add_user(EMAIL, hash_password(PASSWORD), org_id=project.org_id)
    auth = AuthService(users, FakeSessionStore())
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_api_key_auth_service] = lambda: ApiKeyAuthService(
        FakeApiKeyStore()
    )
    app.dependency_overrides[get_log_search_service] = lambda: LogSearchService(
        tenants, FakeLogSearchStore()
    )
    # https: the cookies are Secure, so the client only sends them over https.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://test") as client:
        yield Setup(client, app, project)


async def test_login_sets_a_locked_down_session_cookie_and_a_csrf_cookie(setup: Setup) -> None:
    response = await setup.login()

    assert response.status_code == 200
    assert response.json()["email"] == EMAIL
    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(cookie for cookie in cookies if cookie.startswith("__Host-sp_session="))
    csrf_cookie = next(cookie for cookie in cookies if cookie.startswith("__Host-sp_csrf="))
    assert all(part in session_cookie for part in ("HttpOnly", "Secure", "Path=/", "SameSite=lax"))
    assert "HttpOnly" not in csrf_cookie
    assert all(part in csrf_cookie for part in ("Secure", "Path=/", "SameSite=strict"))
    assert "Domain" not in session_cookie


async def test_wrong_password_is_a_401_that_doesnt_say_which_part_was_wrong(setup: Setup) -> None:
    response = await setup.client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": "wrong password!!"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_login"
    assert "set-cookie" not in response.headers


async def test_too_many_wrong_passwords_is_a_429_with_retry_after(setup: Setup) -> None:
    wrong = {"email": EMAIL, "password": "wrong password!!"}
    for _ in range(5):
        await setup.client.post("/api/v1/auth/login", json=wrong)

    response = await setup.client.post("/api/v1/auth/login", json=wrong)

    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"
    assert int(response.headers["Retry-After"]) > 0


async def test_me_needs_a_session(setup: Setup) -> None:
    signed_out = await setup.client.get("/api/v1/auth/me")
    await setup.login()
    signed_in = await setup.client.get("/api/v1/auth/me")

    assert signed_out.status_code == 401
    assert signed_out.json()["code"] == "not_signed_in"
    assert signed_in.json()["organization"] == "acme"


async def test_signed_in_search_needs_the_csrf_header(setup: Setup) -> None:
    await setup.login()
    csrf = setup.client.cookies["__Host-sp_csrf"]

    without = await setup.client.post("/api/v1/logs/search", json=setup.search_body())
    with_header = await setup.client.post(
        "/api/v1/logs/search", json=setup.search_body(), headers={"X-CSRF-Token": csrf}
    )

    assert without.status_code == 403
    assert without.json()["code"] == "csrf_failed"
    assert with_header.status_code == 200


async def test_logout_revokes_the_session_and_clears_the_cookies(setup: Setup) -> None:
    await setup.login()
    csrf = setup.client.cookies["__Host-sp_csrf"]
    session_token = setup.client.cookies["__Host-sp_session"]

    response = await setup.client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 204
    assert "__Host-sp_session" not in setup.client.cookies
    setup.client.cookies.set("__Host-sp_session", session_token)
    reused = await setup.client.get("/api/v1/auth/me")
    assert reused.status_code == 401


async def test_setup_token_creates_the_owner_once(setup: Setup) -> None:
    fresh = AuthService(FakeUserStore(), FakeSessionStore())
    setup.app.dependency_overrides[get_auth_service] = lambda: fresh
    token = await fresh.issue_setup_token()
    assert token is not None
    form = {
        "token": token,
        "name": "Nitish",
        "email": "owner@example.com",
        "password": PASSWORD,
        "organization": "acme",
    }

    created = await setup.client.post("/api/v1/auth/setup", json=form)
    again = await setup.client.post("/api/v1/auth/setup", json=form)

    assert created.status_code == 201
    assert created.json()["role"] == "owner"
    assert "__Host-sp_session" in setup.client.cookies
    assert again.status_code == 410
    assert again.json()["code"] == "setup_link_invalid"
