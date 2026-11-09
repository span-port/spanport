from collections.abc import AsyncIterator

import httpx
import pytest
from fakes import (
    SAMPLE_ADMIN_KEY,
    FakeApiKeyStore,
    FakeLogWriter,
    FakeSessionStore,
    FakeTenantStore,
    FakeUserStore,
)

from spanport_server.core.request_limits import ApiLimits
from spanport_server.dependencies import (
    get_api_key_auth_service,
    get_auth_service,
    get_project_service,
)
from spanport_server.main import create_app
from spanport_server.schemas.api_key import KeyType, Scope
from spanport_server.services.api_key_auth_service import ApiKeyAuthService
from spanport_server.services.auth_service import AuthService
from spanport_server.services.project_service import ProjectService

pytestmark = pytest.mark.anyio

OTHER_ADMIN_KEY = "sp_admin_another-admin-key-000000000000000000000x7y8"


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    keys = FakeApiKeyStore()
    for raw_key in (SAMPLE_ADMIN_KEY, OTHER_ADMIN_KEY):
        keys.add_key(raw_key, KeyType.ADMIN, scopes=(Scope.PROJECTS_READ,), org_id=project.org_id)
    app = create_app()
    app.state.api_limits = ApiLimits(per_minute=2, public_per_minute=1)
    app.dependency_overrides[get_api_key_auth_service] = lambda: ApiKeyAuthService(keys)
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        FakeUserStore(), FakeSessionStore()
    )
    app.dependency_overrides[get_project_service] = lambda: ProjectService(tenants, FakeLogWriter())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def admin(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


async def test_a_caller_over_the_limit_gets_429_with_retry_after(
    client: httpx.AsyncClient,
) -> None:
    allowed = [
        await client.get("/api/v1/projects", headers=admin(SAMPLE_ADMIN_KEY)) for _ in range(2)
    ]
    refused = await client.get("/api/v1/projects", headers=admin(SAMPLE_ADMIN_KEY))
    another_key = await client.get("/api/v1/projects", headers=admin(OTHER_ADMIN_KEY))

    assert [response.status_code for response in allowed] == [200, 200]
    assert refused.status_code == 429
    assert refused.headers["content-type"] == "application/problem+json"
    assert refused.headers["Retry-After"] == "30"
    assert refused.json()["code"] == "rate_limited"
    assert another_key.status_code == 200


async def test_health_is_never_limited(client: httpx.AsyncClient) -> None:
    statuses = [(await client.get("/health")).status_code for _ in range(5)]

    assert statuses == [200] * 5


async def test_api_docs_are_off_by_default(client: httpx.AsyncClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert (await client.get(path)).status_code == 404


async def test_api_docs_are_served_when_the_setting_is_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPANPORT_API_DOCS", "true")
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200


async def test_sign_in_is_limited_per_client_address(client: httpx.AsyncClient) -> None:
    body = {"email": "nobody@example.com", "password": "a long enough passphrase"}

    first = await client.post("/api/v1/auth/login", json=body)
    second = await client.post("/api/v1/auth/login", json=body)

    assert first.status_code == 401
    assert second.status_code == 429
    assert second.json()["code"] == "rate_limited"
