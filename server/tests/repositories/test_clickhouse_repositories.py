from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from clickhouse_connect.driver.asyncclient import AsyncClient

from spanport_server.core.ids import UuidV7, new_id
from spanport_server.repositories.clickhouse.endpoint_detail_repository import (
    EndpointDetailRepository,
)
from spanport_server.repositories.clickhouse.endpoint_repository import EndpointRepository
from spanport_server.repositories.clickhouse.error_repository import ErrorRepository
from spanport_server.repositories.clickhouse.log_repository import LogRepository
from spanport_server.repositories.clickhouse.project_data_repository import ProjectDataRepository
from spanport_server.repositories.clickhouse.schema_repository import ClickHouseSchemaRepository
from spanport_server.repositories.clickhouse.service_map_repository import ServiceMapRepository
from spanport_server.repositories.clickhouse.span_repository import SpanRepository
from spanport_server.repositories.clickhouse.span_search_repository import SpanSearchRepository
from spanport_server.repositories.clickhouse.storage_repository import StorageRepository
from spanport_server.schemas.endpoint import EndpointQuery
from spanport_server.schemas.errors import StatusRange
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


async def test_endpoint_sums_split_the_time_by_kind_of_step(
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
        kind="CLIENT",
        category="db",
        duration_ns=10_000_000,
    )
    outgoing = replace(
        database, span_id="00f067aa0ba902b8", category="client", duration_ns=20_000_000
    )
    # A call inside the outgoing one (e.g. its retry): already part of its 20 ms.
    nested = replace(outgoing, span_id="00f067aa0ba902b9", parent_span_id=outgoing.span_id)
    await SpanRepository(clickhouse_client).insert_spans([request, database, outgoing, nested])
    query = EndpointQuery(
        org_id=org_id,
        project_id=project_id,
        start=datetime.now(UTC) - timedelta(hours=1),
        end=datetime.now(UTC) + timedelta(minutes=1),
        service="",
    )
    endpoints = EndpointRepository(clickhouse_client)

    (row,) = await endpoints.endpoint_rows(query, 10)
    totals = await endpoints.endpoint_totals(query)
    other_service = await endpoints.endpoint_rows(replace(query, service="billing"), 10)

    assert (row.route, row.requests, row.errors, row.total_ns) == ("/users/:id", 1, 1, 42_000_000)
    assert (row.db_ns, row.external_ns, row.llm_ns) == (10_000_000, 20_000_000, 0)
    assert (totals.requests, totals.errors) == (1, 1)
    assert other_service == []

    one = replace(query, service="hr-portal-api", http_method="GET", route="/users/:id")
    details = EndpointDetailRepository(clickhouse_client)
    summary = await details.summary_row(one)
    (point,) = await details.timeline(one, 60)
    steps = await details.steps(one, 10)
    (slowest,) = await details.slowest(one, 5)

    assert summary is not None and summary.requests == 1
    assert (point.requests, point.errors) == (1, 1)
    assert await details.statuses(one) == [(500, 1)]
    assert {(step.category, step.calls) for step in steps} == {("db", 1), ("client", 2)}
    assert (slowest.trace_id, slowest.http_status, slowest.error) == (request.trace_id, 500, True)
    assert await details.summary_row(replace(one, route="/other")) is None
    (slow,) = await endpoints.slow_queries(query, 10)
    assert (slow.route, slow.statement, slow.calls, slow.requests) == (
        "/users/:id",
        "GET /users/:id",
        1,
        1,
    )


async def test_http_errors_per_interval_and_one_intervals_failing_requests(
    clickhouse_client: AsyncClient,
) -> None:
    schema = ClickHouseSchemaRepository(clickhouse_client)
    for version in schema.available_versions():
        await schema.apply(version)
    log = sample_row("database timeout")
    failed = replace(
        sample_span("GET /users/:id", log.org_id, log.project_id),
        trace_id=log.trace_id,
        attributes={"client.address": "10.0.0.7"},
    )
    not_found = replace(failed, trace_id="1" * 32, span_id="00f067aa0ba902b7", http_status=404)
    fine = replace(failed, trace_id="2" * 32, span_id="00f067aa0ba902b8", http_status=200)
    await SpanRepository(clickhouse_client).insert_spans([failed, not_found, fine])
    await LogRepository(clickhouse_client).insert_logs(
        [log, replace(log, log_id=new_id(), level="INFO", severity_number=9, message="started")]
    )
    query = EndpointQuery(
        org_id=log.org_id,
        project_id=log.project_id,
        start=datetime.now(UTC) - timedelta(hours=1),
        end=datetime.now(UTC) + timedelta(minutes=1),
        service="",
    )
    errors = ErrorRepository(clickhouse_client)

    (point,) = await errors.buckets(query, 3600)
    (api,) = await errors.failing_apis(query, 10)
    server_only = StatusRange(500, 600)
    (group,) = await errors.groups(query, server_only, 10)
    (request,) = await errors.failed_requests(query, server_only, 10)

    assert (point.requests, point.client_errors, point.server_errors) == (3, 1, 1)
    assert (api.route, api.errors) == ("/users/:id", 2)
    assert await errors.window_total(query, StatusRange(400, 600)) == 2
    assert (group.status, group.route, group.requests) == (500, "/users/:id", 1)
    assert (request.http_status, request.client_ip) == (500, "10.0.0.7")
    assert await errors.logged_lines(query, [log.trace_id]) == {log.trace_id: "database timeout"}
    assert await errors.logged_lines(query, []) == {}


async def test_service_map_rows_name_what_each_service_calls(
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
        kind="CLIENT",
        category="db",
        http_status=0,
        status_code="UNSET",
        attributes={"db.system.name": "postgresql", "db.namespace": "kosha"},
    )
    # Stored before ingest knew db.system.name: filed as an outgoing call to "localhost".
    filed_as_outgoing = replace(
        database,
        span_id="00f067aa0ba902c1",
        category="client",
        attributes=database.attributes | {"server.address": "localhost"},
    )
    billing_call = replace(
        database,
        span_id="00f067aa0ba902b8",
        category="client",
        attributes={"server.address": "billing.internal"},
    )
    billing = replace(
        request,
        span_id="00f067aa0ba902b9",
        parent_span_id=billing_call.span_id,
        service="billing",
        http_status=200,
        status_code="UNSET",
    )
    mail = replace(
        database,
        span_id="00f067aa0ba902c0",
        category="client",
        attributes={"url.full": "https://api.mailgun.net/v3/messages"},
    )
    await SpanRepository(clickhouse_client).insert_spans(
        [request, database, filed_as_outgoing, billing_call, billing, mail]
    )
    query = EndpointQuery(
        org_id=org_id,
        project_id=project_id,
        start=datetime.now(UTC) - timedelta(hours=1),
        end=datetime.now(UTC) + timedelta(minutes=1),
        service="",
    )

    rows = await ServiceMapRepository(clickhouse_client).map_rows(query, 10)

    assert {(row.service, row.stats.calls, row.stats.errors) for row in rows.services} == {
        ("hr-portal-api", 1, 1),
        ("billing", 1, 0),
    }
    assert {(row.service, row.category, row.target, row.stats.calls) for row in rows.steps} == {
        ("hr-portal-api", "db", "postgresql · kosha", 2),
        ("hr-portal-api", "client", "api.mailgun.net", 1),
    }
    assert [(row.caller, row.callee) for row in rows.service_calls] == [
        ("hr-portal-api", "billing")
    ]


async def test_storage_counts_rows_per_project_of_one_org_and_sizes_rows(
    clickhouse_client: AsyncClient,
) -> None:
    schema = ClickHouseSchemaRepository(clickhouse_client)
    for version in schema.available_versions():
        await schema.apply(version)
    mine, other_org = sample_row("one"), sample_row("someone else's")
    second = replace(mine, log_id=new_id(), message="two")
    await LogRepository(clickhouse_client).insert_logs([mine, second, other_org])
    storage = StorageRepository(clickhouse_client)

    (rows,) = await storage.log_rows(mine.org_id)
    span_rows = await storage.span_rows(mine.org_id)

    assert (rows.project_id, rows.rows) == (mine.project_id, 2)
    assert rows.oldest <= rows.newest
    assert span_rows == []
    assert await storage.bytes_per_row("logs") > 0
    assert await storage.bytes_per_row("spans") == 0


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
