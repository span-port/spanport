"""Log search against a real ClickHouse: bounds, filters, paging and counts."""

from datetime import UTC, datetime, timedelta

import pytest
from clickhouse_connect.driver.asyncclient import AsyncClient

from spanport_server.core.ids import new_id
from spanport_server.repositories.clickhouse.log_repository import LogRepository
from spanport_server.repositories.clickhouse.log_search_repository import LogSearchRepository
from spanport_server.repositories.clickhouse.schema_repository import ClickHouseSchemaRepository
from spanport_server.schemas.log_row import LogRow
from spanport_server.schemas.log_search import LogPosition, LogQuery
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.log_query_parser import parse_query

pytestmark = pytest.mark.anyio

NOW = datetime.now(UTC).replace(microsecond=0)
PROJECT = ProjectRef(org_id=new_id(), project_id=new_id())
OTHER_PROJECT = ProjectRef(org_id=new_id(), project_id=new_id())


def row(
    project: ProjectRef,
    minutes_ago: int,
    message: str,
    level: str = "INFO",
    attributes: dict[str, str] | None = None,
) -> LogRow:
    ts = NOW - timedelta(minutes=minutes_ago)
    return LogRow(
        org_id=project.org_id,
        project_id=project.project_id,
        log_id=new_id(),
        ts=ts,
        observed_ts=ts,
        service="hr-portal-api",
        level=level,
        severity_number=0,
        message=message,
        trace_id="",
        span_id="",
        attributes=attributes or {},
        resource_attributes={},
    )


ROWS = [
    row(PROJECT, 1, "Payment failed for order-1042", "ERROR", {"client.ip": "45.142.7.9"}),
    row(PROJECT, 2, "connection reset by peer", "WARN"),
    row(PROJECT, 3, "healthcheck ok", "INFO"),
    row(PROJECT, 4, "deadlock detected", "ERROR"),
    row(PROJECT, 60 * 24 * 3, "three days old", "INFO"),
    row(OTHER_PROJECT, 1, "Payment failed in another org", "ERROR"),
]


@pytest.fixture
async def logs(clickhouse_client: AsyncClient) -> LogSearchRepository:
    schema = ClickHouseSchemaRepository(clickhouse_client)
    for version in schema.available_versions():
        await schema.apply(version)
    await LogRepository(clickhouse_client).insert_logs(ROWS)
    return LogSearchRepository(clickhouse_client)


def last_hour(query_text: str = "", project: ProjectRef = PROJECT) -> LogQuery:
    return LogQuery(
        org_id=project.org_id,
        project_id=project.project_id,
        start=NOW - timedelta(hours=1),
        end=NOW + timedelta(minutes=1),
        condition=parse_query(query_text),
    )


async def messages(logs: LogSearchRepository, query_text: str) -> list[str]:
    found = await logs.search(last_hour(query_text), after=None, limit=100)
    return [item.message for item in found]


async def test_returns_only_this_projects_logs_in_range_newest_first(
    logs: LogSearchRepository,
) -> None:
    assert await messages(logs, "") == [
        "Payment failed for order-1042",
        "connection reset by peer",
        "healthcheck ok",
        "deadlock detected",
    ]


@pytest.mark.parametrize(
    ("query_text", "expected"),
    [
        ("level:error", ["Payment failed for order-1042", "deadlock detected"]),
        ("payment", ["Payment failed for order-1042"]),
        ("timeout OR deadlock", ["deadlock detected"]),
        ('"connection reset"', ["connection reset by peer"]),
        ("-healthcheck level:INFO", []),
        ("ip:45.142.*", ["Payment failed for order-1042"]),
        ("dead*", ["deadlock detected"]),
        ("order-1042", ["Payment failed for order-1042"]),
    ],
)
async def test_filters_match_the_query_language(
    logs: LogSearchRepository, query_text: str, expected: list[str]
) -> None:
    assert await messages(logs, query_text) == expected


async def test_pages_continue_exactly_after_the_cursor(logs: LogSearchRepository) -> None:
    first_page = await logs.search(last_hour(), after=None, limit=2)
    position = LogPosition(ts=first_page[-1].ts, log_id=first_page[-1].log_id)

    second_page = await logs.search(last_hour(), after=position, limit=2)

    assert [item.message for item in first_page + second_page] == await messages(logs, "")


async def test_counts_per_level(logs: LogSearchRepository) -> None:
    assert await logs.count_by_level(last_hour()) == {"ERROR": 2, "WARN": 1, "INFO": 1}


async def test_returned_times_are_utc(logs: LogSearchRepository) -> None:
    [newest, *_] = await logs.search(last_hour(), after=None, limit=1)

    assert newest.ts == NOW - timedelta(minutes=1)
    assert newest.ts.tzinfo is not None
