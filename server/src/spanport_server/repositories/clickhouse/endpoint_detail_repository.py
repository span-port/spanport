"""One endpoint in detail, for the API detail page: its requests over time, status codes, the
steps it makes and its slowest requests.

Built on the same request selection as the APIs list (endpoint_repository), narrowed to one
service, method and route. Every query is bounded by org, project and time, with bound
parameters only.
"""

from collections.abc import Sequence
from typing import Any

from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.driver.exceptions import OperationalError

from spanport_server.core.constants import (
    NANOS_PER_MILLISECOND,
    SPANS_TABLE,
    STORAGE_UNAVAILABLE_DETAIL,
)
from spanport_server.core.errors import StorageUnavailableError
from spanport_server.repositories.clickhouse.endpoint_repository import (
    ENDPOINTS_SQL,
    INCOMING_SQL,
    TENANT_SQL,
    endpoint_parameters,
    with_service_filter,
)
from spanport_server.repositories.clickhouse.log_search_repository import as_utc
from spanport_server.schemas.endpoint import (
    EndpointQuery,
    EndpointRow,
    SlowRequest,
    StepRow,
    TimelineRow,
)

TIMELINE_SQL = (
    "SELECT toStartOfInterval(start_ts, toIntervalSecond({bucket_seconds:UInt32})) AS bucket, "  # noqa: S608
    "count(), countIf(failed), quantile({slow:Float64})(duration_ns) "
    f"FROM ({INCOMING_SQL}) GROUP BY bucket ORDER BY bucket"
)
STATUS_SQL = (
    "SELECT http_status, count() AS requests "  # noqa: S608
    f"FROM ({INCOMING_SQL}) GROUP BY http_status ORDER BY http_status"
)
SLOWEST_SQL = (
    "SELECT trace_id, span_id, start_ts, duration_ns, http_status, failed "  # noqa: S608
    f"FROM ({INCOMING_SQL}) ORDER BY duration_ns DESC LIMIT {{limit:UInt32}}"
)
# Every step (other than the request itself) in the same trace and service as the requests.
STEP_SPANS_SQL = (
    "SELECT trace_id, service, category, name, duration_ns "  # noqa: S608
    f"FROM {SPANS_TABLE} WHERE {TENANT_SQL} AND category != {{incoming:String}} "
    "AND start_ts >= {start:DateTime64(6, 'UTC')} "
    "AND start_ts < {steps_end:DateTime64(6, 'UTC')}"
)
STEPS_SQL = (
    "SELECT s.category, s.name, count(), avg(s.duration_ns), "  # noqa: S608
    "quantile({slow:Float64})(s.duration_ns), sum(s.duration_ns) AS total_ns "
    f"FROM ({STEP_SPANS_SQL}) AS s "
    f"INNER JOIN (SELECT DISTINCT trace_id, service FROM ({INCOMING_SQL})) AS r "
    "ON s.trace_id = r.trace_id AND s.service = r.service "
    "GROUP BY s.category, s.name ORDER BY total_ns DESC LIMIT {limit:UInt32}"
)


class EndpointDetailRepository:
    """spans table reads for one endpoint."""

    def __init__(self, client: AsyncClient) -> None:
        """Create the repository.

        Args:
            client: ClickHouse client.
        """
        self._client = client

    async def summary_row(self, query: EndpointQuery) -> EndpointRow | None:
        """The endpoint's sums, as on the APIs list; None when it had no requests.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        rows = await self._rows(ENDPOINTS_SQL, query, {"limit": 1})
        if not rows:
            return None
        service, method, route, requests, errors, quantiles, total, db, external, llm = rows[0]
        return EndpointRow(
            service=service,
            http_method=method,
            route=route,
            requests=requests,
            errors=errors,
            p50_ns=quantiles[0],
            p95_ns=quantiles[1],
            p99_ns=quantiles[2],
            total_ns=total,
            db_ns=db,
            external_ns=external,
            llm_ns=llm,
        )

    async def timeline(self, query: EndpointQuery, bucket_seconds: int) -> list[TimelineRow]:
        """Requests, failures and slow-5% time per interval, oldest first (empty ones left out).

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        rows = await self._rows(TIMELINE_SQL, query, {"bucket_seconds": bucket_seconds})
        return [
            TimelineRow(at=as_utc(at), requests=requests, errors=errors, p95_ns=p95)
            for at, requests, errors, p95 in rows
        ]

    async def statuses(self, query: EndpointQuery) -> list[tuple[int, int]]:
        """(HTTP status, requests) pairs, by status.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        return [(status, requests) for status, requests in await self._rows(STATUS_SQL, query)]

    async def steps(self, query: EndpointQuery, limit: int) -> list[StepRow]:
        """The steps the endpoint's requests make, most total time first.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        rows = await self._rows(STEPS_SQL, query, {"limit": limit})
        return [
            StepRow(
                category=category, name=name, calls=calls, avg_ns=avg, p95_ns=p95, total_ns=total
            )
            for category, name, calls, avg, p95, total in rows
        ]

    async def slowest(self, query: EndpointQuery, limit: int) -> list[SlowRequest]:
        """The endpoint's slowest requests, slowest first.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        rows = await self._rows(SLOWEST_SQL, query, {"limit": limit})
        return [
            SlowRequest(
                trace_id=trace_id,
                span_id=span_id,
                start_ts=as_utc(start_ts),
                duration_ms=duration_ns / NANOS_PER_MILLISECOND,
                http_status=status,
                error=bool(failed),
            )
            for trace_id, span_id, start_ts, duration_ns, status, failed in rows
        ]

    async def _rows(
        self, sql: str, query: EndpointQuery, extra: dict[str, Any] | None = None
    ) -> list[Sequence[Any]]:
        parameters = endpoint_parameters(query) | (extra or {})
        try:
            result = await self._client.query(
                with_service_filter(sql, query), parameters=parameters
            )
        except OperationalError as error:
            raise StorageUnavailableError(STORAGE_UNAVAILABLE_DETAIL) from error
        return list(result.result_rows)
