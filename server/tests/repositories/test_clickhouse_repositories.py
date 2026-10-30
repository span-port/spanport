from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from clickhouse_connect.driver.asyncclient import AsyncClient

from spanport_server.core.ids import UuidV7, new_id
from spanport_server.repositories.clickhouse.log_repository import LogRepository
from spanport_server.repositories.clickhouse.project_data_repository import ProjectDataRepository
from spanport_server.repositories.clickhouse.schema_repository import ClickHouseSchemaRepository
from spanport_server.repositories.clickhouse.span_repository import SpanRepository
from spanport_server.repositories.clickhouse.span_search_repository import SpanSearchRepository
from spanport_server.schemas.log_row import LogRow
from spanport_server.schemas.span_row import SpanRow
from spanport_server.schemas.trace import RequestQuery

pytestmark = pytest.mark.anyio


def sample_row(message: str) -> LogRow:
    return LogRow(
        org_id=new_id(),
        project_id=new_id(),
        log_id=new_id(),
        ts=datetime.now(UTC),
        observed_ts=datetime.now(UTC),
        service="hr-portal-api",
        level="ERROR",
        severity_number=17,
        message=message,
        trace_id="0af7651916cd43dd8448eb211c80319c",
        span_id="b7ad6b7169203331",
        attributes={"user.id": "u-42"},
        resource_attributes={"service.name": "hr-portal-api"},
    )


async def test_migrations_apply_and_revert(clickhouse_client: AsyncClient) -> None:
    schema = ClickHouseSchemaRepository(clickhouse_client)
    versions = schema.available_versions()

    for version in versions:
        await schema.apply(version)
    assert await schema.applied_versions() == versions
    assert await clickhouse_client.command("EXISTS TABLE logs") == 1
    assert await clickhouse_client.command("EXISTS TABLE spans") == 1

    for version in reversed(versions):
        await schema.revert(version)
    assert await schema.applied_versions() == []
    assert await clickhouse_client.command("EXISTS TABLE logs") == 0
    assert await clickhouse_client.command("EXISTS TABLE spans") == 0


async def test_inserted_logs_can_be_read_back(clickhouse_client: AsyncClient) -> None:
    schema = ClickHouseSchemaRepository(clickhouse_client)
    for version in schema.available_versions():
        await schema.apply(version)
    row = sample_row("Payment failed for order 1042")

    await LogRepository(clickhouse_client).insert_logs([row])

    result = await clickhouse_client.query(
        "SELECT log_id, project_id, level, message, attributes FROM logs "
        "WHERE org_id = {org_id:UUID}",
        parameters={"org_id": row.org_id},
    )
    assert result.result_rows == [
        (row.log_id, row.project_id, "ERROR", row.message, {"user.id": "u-42"})
    ]


async def test_deleting_a_projects_logs_leaves_other_projects_alone(
    clickhouse_client: AsyncClient,
) -> None:
    schema = ClickHouseSchemaRepository(clickhouse_client)
    for version in schema.available_versions():
        await schema.apply(version)
    deleted, kept = sample_row("goes"), sample_row("stays")
    logs = LogRepository(clickhouse_client)
    await logs.insert_logs([deleted, kept])

    await logs.delete_project_logs(deleted.org_id, deleted.project_id)

    result = await clickhouse_client.query("SELECT message FROM logs ORDER BY message")
    assert result.result_rows == [("stays",)]


async def test_request_search_filters_and_a_trace_reads_back(
    clickhouse_client: AsyncClient,
) -> None:
    schema = ClickHouseSchemaRepository(clickhouse_client)
    for version in schema.available_versions():
        await schema.apply(version)
    org_id, project_id = new_id(), new_id()
    request = sample_span("GET /users/:id", org_id, project_id)
    database = replace(
        request,
        span_id="00f067aa0ba902b7",
        parent_span_id=request.span_id,
        name="SELECT users",
        kind="CLIENT",
        category="db",
        http_route="",
        http_status=0,
    )
    await SpanRepository(clickhouse_client).insert_spans([request, database])
    spans = SpanSearchRepository(clickhouse_client)
    window = datetime.now(UTC) - timedelta(hours=1)
    query = RequestQuery(
        org_id=org_id,
        project_id=project_id,
        start=window,
        end=datetime.now(UTC) + timedelta(minutes=1),
        service="",
        route="/users",
        min_duration_ns=0,
        errors_only=True,
    )

    found = await spans.search_requests(query, None, 10)
    too_slow = await spans.search_requests(replace(query, min_duration_ns=10**12), None, 10)
    trace = await spans.trace_spans(org_id, project_id, request.trace_id, window, 10)

    assert [(item.name, item.http_status, item.error) for item in found] == [
        ("GET /users/:id", 500, True)
    ]
    assert too_slow == []
    assert {span.category for span in trace} == {"incoming_request", "db"}


def sample_span(name: str, org_id: UuidV7, project_id: UuidV7) -> SpanRow:
    start = datetime.now(UTC)
    return SpanRow(
        org_id=org_id,
        project_id=project_id,
        trace_id="0af7651916cd43dd8448eb211c80319c",
        span_id=new_id().hex[:16],
        parent_span_id="",
        service="hr-portal-api",
        name=name,
        kind="SERVER",
        category="incoming_request",
        start_ts=start,
        end_ts=start + timedelta(milliseconds=42),
        duration_ns=42_000_000,
        status_code="ERROR",
        status_message="",
        http_method="GET",
        http_route="/users/:id",
        http_status=500,
        attributes={"http.route": "/users/:id"},
        resource_attributes={"service.name": "hr-portal-api"},
    )


async def test_spans_are_stored_and_deleted_with_their_project(
    clickhouse_client: AsyncClient,
) -> None:
    schema = ClickHouseSchemaRepository(clickhouse_client)
    for version in schema.available_versions():
        await schema.apply(version)
    log = sample_row("goes")
    deleted = sample_span("GET /users/:id", log.org_id, log.project_id)
    kept = sample_span("kept", new_id(), new_id())
    await LogRepository(clickhouse_client).insert_logs([log])
    await SpanRepository(clickhouse_client).insert_spans([deleted, kept])

    stored = await clickhouse_client.query(
        "SELECT name, category, duration_ns, http_route, http_status FROM spans "
        "WHERE org_id = {org_id:UUID}",
        parameters={"org_id": deleted.org_id},
    )
    await ProjectDataRepository(clickhouse_client).delete_project_data(
        deleted.org_id, deleted.project_id
    )

    assert stored.result_rows == [
        ("GET /users/:id", "incoming_request", 42_000_000, "/users/:id", 500)
    ]
    assert (await clickhouse_client.query("SELECT name FROM spans")).result_rows == [("kept",)]
    assert (await clickhouse_client.query("SELECT count() FROM logs")).result_rows == [(0,)]
