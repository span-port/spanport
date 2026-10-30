from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
from fakes import (
    SAMPLE_ADMIN_KEY,
    FakeApiKeyStore,
    FakeLogSearchStore,
    FakeLogWriter,
    FakeSessionStore,
    FakeTenantStore,
    FakeUserStore,
)

from spanport_server.controllers.log_tail_controller import server_sent_events
from spanport_server.core.ids import new_id
from spanport_server.dependencies import (
    get_api_key_auth_service,
    get_auth_service,
    get_log_tail_service,
    get_project_service,
)
from spanport_server.main import create_app
from spanport_server.schemas.api_key import KeyType, Scope
from spanport_server.schemas.log_search import LogItem
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.api_key_auth_service import ApiKeyAuthService
from spanport_server.services.auth_service import AuthService
from spanport_server.services.log_tail_service import LogTailService
from spanport_server.services.project_service import ProjectService

pytestmark = pytest.mark.anyio

LOGS_ONLY_KEY = "sp_admin_logs-only-key-000000000000000000000k9l0"


class Setup:
    def __init__(self, client: httpx.AsyncClient, project: ProjectRef) -> None:
        self.client = client
        self.project = project


@pytest.fixture
async def setup() -> AsyncIterator[Setup]:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    keys = FakeApiKeyStore()
    keys.add_key(
        SAMPLE_ADMIN_KEY,
        KeyType.ADMIN,
        scopes=(Scope.LOGS_READ, Scope.PROJECTS_READ),
        org_id=project.org_id,
    )
    keys.add_key(LOGS_ONLY_KEY, KeyType.ADMIN, scopes=(Scope.LOGS_READ,), org_id=project.org_id)
    app = create_app()
    app.dependency_overrides[get_api_key_auth_service] = lambda: ApiKeyAuthService(keys)
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        FakeUserStore(), FakeSessionStore()
    )
    app.dependency_overrides[get_project_service] = lambda: ProjectService(tenants, FakeLogWriter())
    app.dependency_overrides[get_log_tail_service] = lambda: LogTailService(
        tenants, FakeLogSearchStore()
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield Setup(client, project)


def admin(key: str = SAMPLE_ADMIN_KEY) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


async def test_lists_projects_with_client_and_environment(setup: Setup) -> None:
    response = await setup.client.get("/api/v1/projects", headers=admin())

    assert response.status_code == 200
    assert response.json() == {
        "data": [
            {
                "id": str(setup.project.project_id),
                "client": "northwind",
                "project": "hr-portal",
                "environment": "production",
                "archived": False,
            }
        ],
        "next_cursor": None,
        "has_more": False,
    }


async def test_projects_need_the_projects_read_scope(setup: Setup) -> None:
    response = await setup.client.get("/api/v1/projects", headers=admin(LOGS_ONLY_KEY))

    assert response.status_code == 403
    assert response.json()["code"] == "insufficient_scope"


async def test_bad_query_parameter_is_a_400_without_the_value(setup: Setup) -> None:
    response = await setup.client.get("/api/v1/projects?limit=99999", headers=admin())

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_request"
    assert "limit" in response.json()["detail"]
    assert "99999" not in response.text


async def test_tail_rejects_a_foreign_project_before_streaming(setup: Setup) -> None:
    response = await setup.client.post(
        "/api/v1/logs/tail", json={"project_id": str(new_id())}, headers=admin()
    )

    assert response.status_code == 404


async def test_tail_needs_an_admin_key(setup: Setup) -> None:
    response = await setup.client.post(
        "/api/v1/logs/tail", json={"project_id": str(setup.project.project_id)}
    )

    assert response.status_code == 401


async def batches_of(*batches: list[LogItem]) -> AsyncIterator[list[LogItem]]:
    for batch in batches:
        yield batch


async def test_sse_frames_carry_each_non_empty_batch_as_a_logs_event() -> None:
    item = LogItem(
        log_id=new_id(),
        ts=datetime(2026, 10, 29, 7, 0, tzinfo=UTC),
        service="api",
        level="ERROR",
        message="boom",
        trace_id="",
        span_id="",
        attributes={},
    )

    frames = b"".join([frame async for frame in server_sent_events(batches_of([], [item]))])

    assert frames.startswith(b": connected\n\nevent: logs\ndata: [")
    assert b'"message":"boom"' in frames
    assert frames.endswith(b"\n\n")


async def test_the_stream_sends_a_byte_at_once_even_with_no_logs_yet() -> None:
    """Proxies hold the headers until the first byte; without it the UI stays on Connecting."""
    frames = server_sent_events(batches_of([]))

    assert await anext(frames) == b": connected\n\n"
