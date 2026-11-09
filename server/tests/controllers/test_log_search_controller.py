from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fakes import (
    SAMPLE_ADMIN_KEY,
    SAMPLE_DATA_KEY,
    FakeApiKeyStore,
    FakeEndpointDetailStore,
    FakeEndpointStatsStore,
    FakeErrorStore,
    FakeLogSearchStore,
    FakeServiceMapStore,
    FakeSessionStore,
    FakeSpanSearchStore,
    FakeTenantStore,
    FakeUserStore,
)

from spanport_server.core.ids import new_id
from spanport_server.dependencies import (
    get_api_key_auth_service,
    get_auth_service,
    get_endpoint_detail_service,
    get_endpoint_service,
    get_error_service,
    get_log_export_service,
    get_log_search_service,
    get_service_map_service,
    get_trace_service,
)
from spanport_server.main import create_app
from spanport_server.schemas.api_key import KeyType, Scope
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.api_key_auth_service import ApiKeyAuthService
from spanport_server.services.auth_service import AuthService
from spanport_server.services.endpoint_detail_service import EndpointDetailService
from spanport_server.services.endpoint_service import EndpointService
from spanport_server.services.error_service import ErrorService
from spanport_server.services.log_export_service import LogExportService
from spanport_server.services.log_search_service import LogSearchService
from spanport_server.services.service_map_service import ServiceMapService
from spanport_server.services.trace_service import TraceService

pytestmark = pytest.mark.anyio

NO_SCOPE_KEY = "sp_admin_no-scope-key-000000000000000000000e5f6"
EXPIRED_KEY = "sp_admin_expired-key-0000000000000000000000g7h8"


class Setup:
    def __init__(self, client: httpx.AsyncClient, project: ProjectRef) -> None:
        self.client = client
        self.project = project

    def body(self, **overrides: object) -> dict[str, object]:
        now = datetime.now(UTC)
        fields: dict[str, object] = {
            "project_id": str(self.project.project_id),
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        }
        return fields | overrides

    async def post(
        self, path: str, body: object, key: str | None = SAMPLE_ADMIN_KEY
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        return await self.client.post(path, json=body, headers=headers)


@pytest.fixture
async def setup() -> AsyncIterator[Setup]:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    keys = FakeApiKeyStore()
    keys.add_key(SAMPLE_ADMIN_KEY, KeyType.ADMIN, scopes=(Scope.LOGS_READ,), org_id=project.org_id)
    keys.add_key(SAMPLE_DATA_KEY, org_id=project.org_id)
    keys.add_key(NO_SCOPE_KEY, KeyType.ADMIN, org_id=project.org_id)
    keys.add_key(
        EXPIRED_KEY,
        KeyType.ADMIN,
        scopes=(Scope.LOGS_READ,),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        org_id=project.org_id,
    )
    store = FakeLogSearchStore()
    store.by_level = {"ERROR": 2}
    app = create_app()
    app.dependency_overrides[get_api_key_auth_service] = lambda: ApiKeyAuthService(keys)
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        FakeUserStore(), FakeSessionStore()
    )
    app.dependency_overrides[get_log_search_service] = lambda: LogSearchService(tenants, store)
    app.dependency_overrides[get_log_export_service] = lambda: LogExportService(tenants, store)
    app.dependency_overrides[get_trace_service] = lambda: TraceService(
        tenants, FakeSpanSearchStore()
    )
    app.dependency_overrides[get_endpoint_service] = lambda: EndpointService(
        tenants, FakeEndpointStatsStore()
    )
    app.dependency_overrides[get_endpoint_detail_service] = lambda: EndpointDetailService(
        tenants, FakeEndpointDetailStore()
    )
    app.dependency_overrides[get_error_service] = lambda: ErrorService(tenants, FakeErrorStore())
    app.dependency_overrides[get_service_map_service] = lambda: ServiceMapService(
        tenants, FakeServiceMapStore()
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield Setup(client, project)


async def test_search_returns_a_page(setup: Setup) -> None:
    response = await setup.post("/api/v1/logs/search", setup.body())

    assert response.status_code == 200
    assert response.json() == {"data": [], "next_cursor": None, "has_more": False}


async def test_trace_search_and_a_missing_trace(setup: Setup) -> None:
    searched = await setup.post("/api/v1/traces/search", setup.body(errors_only=True))
    missing = await setup.client.get(
        f"/api/v1/traces/{'a' * 32}",
        params={"project_id": str(setup.project.project_id)},
        headers={"Authorization": f"Bearer {SAMPLE_ADMIN_KEY}"},
    )
    unauthenticated = await setup.post("/api/v1/traces/search", setup.body(), key=None)

    assert searched.status_code == 200
    assert searched.json() == {"data": [], "next_cursor": None, "has_more": False}
    assert missing.status_code == 404
    assert unauthenticated.status_code == 401


async def test_endpoint_summary_needs_a_reader_and_a_valid_body(setup: Setup) -> None:
    summary = await setup.post("/api/v1/endpoints/summary", setup.body(service="api"))
    unknown_field = await setup.post("/api/v1/endpoints/summary", setup.body(filters=[]))
    unauthenticated = await setup.post("/api/v1/endpoints/summary", setup.body(), key=None)

    assert summary.json() == {
        "totals": {"requests": 0, "errors": 0, "p95_ms": 0, "previous_p95_ms": None},
        "data": [],
        "slow_queries": [],
        "next_cursor": None,
        "has_more": False,
    }
    assert unknown_field.status_code == 400
    assert unauthenticated.status_code == 401


async def test_endpoint_detail_needs_a_route_and_answers_for_a_quiet_endpoint(
    setup: Setup,
) -> None:
    path = "/api/v1/endpoints/detail"
    body = setup.body(service="api", http_method="GET", route="/users/:id")

    detail = await setup.post(path, body)
    no_route = await setup.post(path, setup.body(service="api"))

    assert detail.json() == {
        "summary": None,
        "bucket_seconds": 60,
        "timeline": [],
        "statuses": [],
        "steps": [],
        "slowest": [],
    }
    assert no_route.status_code == 400


async def test_errors_summary_and_window_need_a_reader_and_a_valid_body(setup: Setup) -> None:
    summary = await setup.post("/api/v1/errors/summary", setup.body())
    window = await setup.post("/api/v1/errors/window", setup.body(show="5xx"))
    bad_show = await setup.post("/api/v1/errors/window", setup.body(show="3xx"))
    route_alone = await setup.post("/api/v1/errors/summary", setup.body(route="/users/:id"))
    unauthenticated = await setup.post("/api/v1/errors/summary", setup.body(), key=None)

    assert summary.json() == {
        "bucket_seconds": 60,
        "buckets": [],
        "totals": {"requests": 0, "client_errors": 0, "server_errors": 0, "worst_server": None},
        "apis": [],
    }
    assert window.json() == {"total": 0, "groups": [], "requests": []}
    assert [bad_show.status_code, route_alone.status_code] == [400, 400]
    assert unauthenticated.status_code == 401


async def test_service_map_needs_a_reader_and_a_valid_body(setup: Setup) -> None:
    mapped = await setup.post("/api/v1/service-map", setup.body())
    unknown_field = await setup.post("/api/v1/service-map", setup.body(service="api"))
    unauthenticated = await setup.post("/api/v1/service-map", setup.body(), key=None)

    assert mapped.json() == {"range_seconds": 3600.0, "nodes": [], "edges": []}
    assert [unknown_field.status_code, unauthenticated.status_code] == [400, 401]


async def test_export_downloads_a_named_file(setup: Setup) -> None:
    response = await setup.post("/api/v1/logs/export", setup.body(format="ndjson"))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    disposition = response.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="spanport-logs-northwind-hr-portal-')
    assert disposition.endswith('.ndjson"')


async def test_export_rejects_an_unknown_format(setup: Setup) -> None:
    response = await setup.post("/api/v1/logs/export", setup.body(format="xlsx"))

    assert response.status_code == 400
    assert "format" in response.json()["detail"]


async def test_counts_returns_totals(setup: Setup) -> None:
    response = await setup.post("/api/v1/logs/counts", setup.body())

    assert response.status_code == 200
    assert response.json() == {"total": 2, "by_level": {"ERROR": 2}}


@pytest.mark.parametrize(
    ("key", "status", "code"),
    [
        (None, 401, "not_signed_in"),
        (SAMPLE_DATA_KEY, 401, "invalid_key"),
        (EXPIRED_KEY, 401, "invalid_key"),
        (NO_SCOPE_KEY, 403, "insufficient_scope"),
    ],
    ids=["no-key-no-session", "data-key", "expired", "no-logs-read-scope"],
)
async def test_only_signed_in_people_or_admin_keys_with_logs_read_may_search(
    setup: Setup, key: str | None, status: int, code: str
) -> None:
    response = await setup.post("/api/v1/logs/search", setup.body(), key=key)

    assert response.status_code == status
    assert response.json()["code"] == code


async def test_key_is_checked_before_the_body_is_read(setup: Setup) -> None:
    oversized = {"query": "x" * (70 * 1024)}

    response = await setup.post("/api/v1/logs/search", oversized, key=None)

    assert response.status_code == 401


async def test_body_over_64_kb_is_refused(setup: Setup) -> None:
    response = await setup.post("/api/v1/logs/search", setup.body(padding="x" * (70 * 1024)))

    assert response.status_code == 413


async def test_non_json_body_is_refused(setup: Setup) -> None:
    response = await setup.client.post(
        "/api/v1/logs/search",
        content=b"query=timeout",
        headers={"Authorization": f"Bearer {SAMPLE_ADMIN_KEY}", "Content-Type": "text/plain"},
    )

    assert response.status_code == 415


async def test_validation_errors_name_the_field_but_never_echo_the_value(setup: Setup) -> None:
    response = await setup.post(
        "/api/v1/logs/search", setup.body(limit=9999, unknown="secret-customer-name")
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "limit" in detail
    assert "unknown" in detail
    assert "secret-customer-name" not in response.text
    assert "9999" not in response.text


async def test_bad_uuid_error_doesnt_quote_any_of_the_value(setup: Setup) -> None:
    response = await setup.post("/api/v1/logs/search", setup.body(project_id="acme-zqx"))

    assert response.status_code == 400
    assert response.json()["detail"] == "project_id: Input should be a valid UUID"


async def test_invalid_query_is_a_400_with_the_position(setup: Setup) -> None:
    response = await setup.post("/api/v1/logs/search", setup.body(query="(timeout"))

    assert response.status_code == 400
    assert "missing closing bracket" in response.json()["detail"]


async def test_project_of_another_org_is_404(setup: Setup) -> None:
    response = await setup.post("/api/v1/logs/search", setup.body(project_id=str(new_id())))

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
