from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeServiceMapStore, FakeTenantStore

from spanport_server.core.errors import NotFoundError
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.service_map import (
    CallStats,
    MapRows,
    MapStatus,
    ServiceEdgeRow,
    ServiceMapRequest,
    ServiceRow,
    StepEdgeRow,
)
from spanport_server.services.service_map_service import ServiceMapService, map_status

pytestmark = pytest.mark.anyio

NOW = datetime.now(UTC)
MS = 1_000_000


def stats(calls: int, errors: int = 0, p50_ms: float = 10, p95_ms: float = 20) -> CallStats:
    return CallStats(calls=calls, errors=errors, p50_ns=p50_ms * MS, p95_ns=p95_ms * MS)


def test_red_for_failures_orange_for_much_slower_than_before() -> None:
    assert map_status(stats(100, errors=2), None) == MapStatus.BAD
    assert map_status(stats(100, errors=1), None) == MapStatus.OK
    assert map_status(stats(100, p95_ms=40), 20 * MS) == MapStatus.SLOW
    assert map_status(stats(100, p95_ms=30), 20 * MS) == MapStatus.OK
    assert map_status(stats(0), None) == MapStatus.OK


async def test_the_map_joins_services_databases_and_other_systems() -> None:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "kosha", "backend", "production")
    store = FakeServiceMapStore()
    store.rows = MapRows(
        services=[
            ServiceRow("api", stats(100)),
            ServiceRow("billing", stats(10, errors=5)),
        ],
        steps=[
            StepEdgeRow("api", "db", "postgresql · kosha", stats(300, p50_ms=2, p95_ms=50)),
            StepEdgeRow("billing", "db", "postgresql · kosha", stats(100, p50_ms=6, p95_ms=9)),
            StepEdgeRow("api", "client", "api.mailgun.net", stats(4)),
        ],
        service_calls=[ServiceEdgeRow("api", "billing", stats(10, errors=5))],
    )
    store.previous = MapRows(
        services=[],
        steps=[StepEdgeRow("api", "db", "postgresql · kosha", stats(300, p95_ms=10))],
        service_calls=[],
    )
    service = ServiceMapService(tenants, store)
    request = ServiceMapRequest(
        project_id=project.project_id, start=NOW - timedelta(hours=1), end=NOW
    )

    result = await service.service_map(Caller(org_id=project.org_id, label="user=t"), request)

    nodes = {node.id: node for node in result.nodes}
    database = nodes["db:postgresql · kosha"]
    assert (database.calls, database.p50_ms, database.p95_ms) == (400, 3, 50)
    assert database.called_by == ["api", "billing"]
    assert database.status == MapStatus.SLOW
    assert nodes["external:api.mailgun.net"].kind == "external"
    assert nodes["service:api"].calls_to == ["api.mailgun.net", "billing", "postgresql · kosha"]
    assert nodes["service:billing"].status == MapStatus.BAD
    edges = {(edge.source, edge.target): edge for edge in result.edges}
    assert edges[("service:api", "service:billing")].status == MapStatus.BAD
    assert result.range_seconds == 3600
    current, previous = store.queries
    assert previous.end == current.start


async def test_a_project_the_caller_cant_see_is_not_found() -> None:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "kosha", "backend", "production")
    service = ServiceMapService(tenants, FakeServiceMapStore())
    hidden = Caller(org_id=project.org_id, label="user=x", project_ids=frozenset())
    request = ServiceMapRequest(
        project_id=project.project_id, start=NOW - timedelta(hours=1), end=NOW
    )

    with pytest.raises(NotFoundError):
        await service.service_map(hidden, request)
