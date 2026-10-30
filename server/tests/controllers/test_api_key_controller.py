from collections.abc import AsyncIterator

import httpx
import pytest
from fakes import SAMPLE_DATA_KEY, FakeApiKeyStore

from spanport_server.dependencies import get_api_key_auth_service
from spanport_server.main import create_app
from spanport_server.services.api_key_auth_service import ApiKeyAuthService

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    keys = FakeApiKeyStore()
    keys.add_key(SAMPLE_DATA_KEY)
    app = create_app()
    app.dependency_overrides[get_api_key_auth_service] = lambda: ApiKeyAuthService(keys)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


async def test_valid_data_key_is_confirmed_without_revealing_it(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/api-keys/current", headers={"Authorization": f"Bearer {SAMPLE_DATA_KEY}"}
    )

    assert response.status_code == 200
    assert response.json() == {"key_type": "ingest", "last_four": "a1b2"}
    assert SAMPLE_DATA_KEY not in response.text


@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer sp_ingest_unknown-key", "Bearer sp_admin_other-type"],
    ids=["missing", "unknown", "wrong-type"],
)
async def test_invalid_key_gets_401(client: httpx.AsyncClient, authorization: str | None) -> None:
    headers = {"Authorization": authorization} if authorization else {}

    response = await client.get("/api/v1/api-keys/current", headers=headers)

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_key"
