"""Reads the ClickHouse spans table: incoming requests for the list, and one trace's spans.

Every query is bounded by org, project and time, and uses bound parameters only.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.driver.exceptions import OperationalError

from spanport_server.core.constants import (
    FIRST_SERVER_ERROR_STATUS,
    NANOS_PER_MILLISECOND,
    SPAN_CATEGORY_INCOMING,
    SPAN_STATUS_ERROR,
    SPANS_TABLE,
    STORAGE_UNAVAILABLE_DETAIL,
)
from spanport_server.core.errors import StorageUnavailableError
from spanport_server.core.ids import UuidV7
from spanport_server.repositories.clickhouse.log_search_repository import as_utc
from spanport_server.schemas.trace import RequestItem, RequestQuery, SpanPosition, StoredSpan

REQUEST_COLUMNS = (
    "trace_id, span_id, service, name, http_method, http_route, http_status, status_code, "
    "start_ts, duration_ns"
)
SPAN_COLUMNS = (
    "span_id, parent_span_id, service, name, kind, category, start_ts, duration_ns, "
    "status_code, status_message, http_method, http_route, http_status, attributes"
)
REQUEST_BOUNDS_SQL = (
    "org_id = {org_id:UUID} AND project_id = {project_id:UUID} "
    "AND category = {category:String} "
    "AND start_ts >= {start:DateTime64(6, 'UTC')} AND start_ts < {end:DateTime64(6, 'UTC')}"
)
SERVICE_SQL = "service = {service:String}"
ROUTE_SQL = (
    "(positionCaseInsensitive(http_route, {route:String}) > 0 "
    "OR positionCaseInsensitive(name, {route:String}) > 0)"
)
MIN_DURATION_SQL = "duration_ns >= {min_duration_ns:UInt64}"
ERRORS_SQL = "(status_code = {error_status:String} OR http_status >= {first_server_error:UInt16})"
AFTER_SQL = "(start_ts, span_id) < ({after_ts:DateTime64(6, 'UTC')}, {after_span:String})"
# Built only from fixed names and {placeholder} markers; every value is a bound parameter.
REQUESTS_SQL = (
    f"SELECT {REQUEST_COLUMNS} FROM {SPANS_TABLE} WHERE {{where}} "  # noqa: S608
    "ORDER BY start_ts DESC, span_id DESC LIMIT {limit:UInt32}"
)
TRACE_SQL = (
    f"SELECT {SPAN_COLUMNS} FROM {SPANS_TABLE} "  # noqa: S608
    "WHERE org_id = {org_id:UUID} AND project_id = {project_id:UUID} "
    "AND trace_id = {trace_id:String} AND start_ts >= {since:DateTime64(6, 'UTC')} "
    "ORDER BY start_ts LIMIT {limit:UInt32}"
)


def requests_where(query: RequestQuery, after: SpanPosition | None) -> tuple[str, dict[str, Any]]:
    """The WHERE text and parameters: bounds, then each filter that is set."""
    parts = [REQUEST_BOUNDS_SQL]
    parameters: dict[str, Any] = {
        "org_id": query.org_id,
        "project_id": query.project_id,
        "category": SPAN_CATEGORY_INCOMING,
        "start": query.start,
        "end": query.end,
    }
    if query.service:
        parts.append(SERVICE_SQL)
        parameters["service"] = query.service
    if query.route:
        parts.append(ROUTE_SQL)
        parameters["route"] = query.route
    if query.min_duration_ns:
        parts.append(MIN_DURATION_SQL)
        parameters["min_duration_ns"] = query.min_duration_ns
    if query.errors_only:
        parts.append(ERRORS_SQL)
        parameters.update(
            error_status=SPAN_STATUS_ERROR, first_server_error=FIRST_SERVER_ERROR_STATUS
        )
    if after is not None:
        parts.append(AFTER_SQL)
        parameters.update(after_ts=after.ts, after_span=after.span_id)
    return " AND ".join(parts), parameters


class SpanSearchRepository:
    """spans table reads."""

    def __init__(self, client: AsyncClient) -> None:
        """Create the repository.

        Args:
            client: ClickHouse client.
        """
        self._client = client

    async def search_requests(
        self, query: RequestQuery, after: SpanPosition | None, limit: int
    ) -> list[RequestItem]:
        """Matching incoming requests, newest first, after `after`.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        where, parameters = requests_where(query, after)
        parameters["limit"] = limit
        rows = await self._rows(REQUESTS_SQL.replace("{where}", where), parameters)
        return [
            RequestItem(
                trace_id=trace_id,
                span_id=span_id,
                service=service,
                name=name,
                http_method=http_method,
                http_route=http_route,
                http_status=http_status,
                error=status_code == SPAN_STATUS_ERROR or http_status >= FIRST_SERVER_ERROR_STATUS,
                start_ts=as_utc(start_ts),
                duration_ms=duration_ns / NANOS_PER_MILLISECOND,
            )
            for (
                trace_id,
                span_id,
                service,
                name,
                http_method,
                http_route,
                http_status,
                status_code,
                start_ts,
                duration_ns,
            ) in rows
        ]

    async def trace_spans(
        self, org_id: UuidV7, project_id: UuidV7, trace_id: str, since: datetime, limit: int
    ) -> list[StoredSpan]:
        """Up to `limit` spans of one trace in one project, oldest first.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        parameters = {
            "org_id": org_id,
            "project_id": project_id,
            "trace_id": trace_id,
            "since": since,
            "limit": limit,
        }
        rows = await self._rows(TRACE_SQL, parameters)
        return [
            StoredSpan(
                span_id=row[0],
                parent_span_id=row[1],
                service=row[2],
                name=row[3],
                kind=row[4],
                category=row[5],
                start_ts=as_utc(row[6]),
                duration_ns=row[7],
                status_code=row[8],
                status_message=row[9],
                http_method=row[10],
                http_route=row[11],
                http_status=row[12],
                attributes=row[13],
            )
            for row in rows
        ]

    async def _rows(self, sql: str, parameters: dict[str, Any]) -> list[Sequence[Any]]:
        try:
            result = await self._client.query(sql, parameters=parameters)
        except OperationalError as error:
            raise StorageUnavailableError(STORAGE_UNAVAILABLE_DETAIL) from error
        return list(result.result_rows)
