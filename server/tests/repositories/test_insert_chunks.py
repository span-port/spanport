"""Insert batching and error mapping, with a stand-in client (no database needed)."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast

import pytest
from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.driver.exceptions import DataError, OperationalError

from spanport_server.core.errors import InvalidRequestError, StorageUnavailableError
from spanport_server.core.ids import new_id
from spanport_server.repositories.clickhouse.log_repository import LogRepository
from spanport_server.repositories.clickhouse.span_repository import SpanRepository
from spanport_server.schemas.log_row import LogRow
from spanport_server.schemas.span_row import SpanRow

pytestmark = pytest.mark.anyio
NOW = datetime(2026, 11, 9, tzinfo=UTC)


class RecordingClient:
    """Records each insert's row count and settings; can fail with a given error."""

    def __init__(self, error: Exception | None = None) -> None:
        self.inserts: list[tuple[int, dict[str, int]]] = []
        self.error = error

    async def insert(
        self,
        table: str,
        data: Sequence[Sequence[object]],
        column_names: Sequence[str],
        settings: dict[str, int],
    ) -> None:
        if self.error is not None:
            raise self.error
        self.inserts.append((len(data), settings))


def log_rows(count: int) -> list[LogRow]:
    org_id, project_id = new_id(), new_id()
    return [
        LogRow(org_id, project_id, new_id(), NOW, NOW, "api", "INFO", 9, "m", "", "", {}, {})
        for _ in range(count)
    ]


def span_rows(count: int) -> list[SpanRow]:
    org_id, project_id = new_id(), new_id()
    span = SpanRow(
        org_id=org_id,
        project_id=project_id,
        trace_id="t",
        span_id="s",
        parent_span_id="",
        service="api",
        name="GET /",
        kind="SERVER",
        category="incoming_request",
        start_ts=NOW,
        end_ts=NOW,
        duration_ns=0,
        status_code="UNSET",
        status_message="",
        http_method="GET",
        http_route="/",
        http_status=200,
        attributes={},
        resource_attributes={},
    )
    return [span] * count


async def test_logs_are_inserted_in_chunks_of_1000_without_read_limits() -> None:
    client = RecordingClient()

    await LogRepository(cast(AsyncClient, client)).insert_logs(log_rows(2_500))

    assert [rows for rows, _ in client.inserts] == [1_000, 1_000, 500]
    settings = client.inserts[0][1]
    assert settings["wait_for_async_insert"] == 1
    assert (settings["max_execution_time"], settings["max_memory_usage"]) == (0, 0)


async def test_spans_are_inserted_in_chunks_of_1000() -> None:
    client = RecordingClient()

    await SpanRepository(cast(AsyncClient, client)).insert_spans(span_rows(1_001))

    assert [rows for rows, _ in client.inserts] == [1_000, 1]


@pytest.mark.parametrize(
    "error", [DataError("bad"), OverflowError("too big for UInt8")], ids=["data", "overflow"]
)
async def test_a_value_storage_cant_hold_is_a_bad_request(error: Exception) -> None:
    client = RecordingClient(error)

    with pytest.raises(InvalidRequestError):
        await LogRepository(cast(AsyncClient, client)).insert_logs(log_rows(1))


async def test_an_outage_is_still_storage_unavailable() -> None:
    client = RecordingClient(OperationalError("connection refused"))

    with pytest.raises(StorageUnavailableError):
        await SpanRepository(cast(AsyncClient, client)).insert_spans(span_rows(1))
