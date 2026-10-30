"""Searches and counts rows of the ClickHouse logs table.

Every query is bounded by org, project and time range, and uses bound parameters only.
"""

from datetime import UTC, datetime
from typing import Any

from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.driver.exceptions import OperationalError

from spanport_server.core.constants import LOGS_TABLE, STORAGE_UNAVAILABLE_DETAIL
from spanport_server.core.errors import StorageUnavailableError
from spanport_server.repositories.clickhouse.log_query_compiler import compile_condition
from spanport_server.schemas.log_search import LogItem, LogPosition, LogQuery

SEARCH_COLUMNS = "log_id, ts, service, level, message, trace_id, span_id, attributes"
# The bounds every query has: tenant, project and time range.
BOUNDS_SQL = (
    "org_id = {org_id:UUID} AND project_id = {project_id:UUID} "
    "AND ts >= {start:DateTime64(6, 'UTC')} AND ts < {end:DateTime64(6, 'UTC')}"
)
# Continue strictly after the last row of the previous page (rows sort by ts, log_id).
AFTER_SQL = "(ts, log_id) < ({after_ts:DateTime64(6, 'UTC')}, {after_id:UUID})"
# Built only from fixed names and {placeholder} markers; every value is a bound parameter.
SEARCH_SQL = (
    f"SELECT {SEARCH_COLUMNS} FROM {LOGS_TABLE} WHERE {{where}} "  # noqa: S608
    "ORDER BY ts DESC, log_id DESC LIMIT {limit:UInt32}"
)
COUNT_SQL = f"SELECT level, count() FROM {LOGS_TABLE} WHERE {{where}} GROUP BY level"  # noqa: S608


def where_clause(query: LogQuery, after: LogPosition | None) -> tuple[str, dict[str, Any]]:
    """The WHERE text and its parameters: bounds, optional page position, optional condition."""
    parts = [BOUNDS_SQL]
    parameters: dict[str, Any] = {
        "org_id": query.org_id,
        "project_id": query.project_id,
        "start": query.start,
        "end": query.end,
    }
    if after is not None:
        parts.append(AFTER_SQL)
        parameters.update(after_ts=after.ts, after_id=after.log_id)
    if query.condition is not None:
        compiled = compile_condition(query.condition)
        parts.append(f"({compiled.sql})")
        parameters.update(compiled.parameters)
    return " AND ".join(parts), parameters


def as_utc(moment: datetime) -> datetime:
    """ClickHouse may return naive datetimes for UTC columns; make them explicitly UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


class LogSearchRepository:
    """logs table reads."""

    def __init__(self, client: AsyncClient) -> None:
        """Create the repository.

        Args:
            client: ClickHouse client.
        """
        self._client = client

    async def search(self, query: LogQuery, after: LogPosition | None, limit: int) -> list[LogItem]:
        """Matching logs, newest first.

        Args:
            query: Org, project, time range and condition.
            after: Continue after this row; None for the first page.
            limit: Most rows to return.

        Returns:
            Up to `limit` rows.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        where, parameters = where_clause(query, after)
        parameters["limit"] = limit
        try:
            result = await self._client.query(
                SEARCH_SQL.replace("{where}", where), parameters=parameters
            )
        except OperationalError as error:
            raise StorageUnavailableError(STORAGE_UNAVAILABLE_DETAIL) from error
        return [
            LogItem(
                log_id=log_id,
                ts=as_utc(ts),
                service=service,
                level=level,
                message=message,
                trace_id=trace_id,
                span_id=span_id,
                attributes=attributes,
            )
            for log_id, ts, service, level, message, trace_id, span_id, attributes in (
                result.result_rows
            )
        ]

    async def count_by_level(self, query: LogQuery) -> dict[str, int]:
        """How many logs match, per level.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        where, parameters = where_clause(query, after=None)
        try:
            result = await self._client.query(
                COUNT_SQL.replace("{where}", where), parameters=parameters
            )
        except OperationalError as error:
            raise StorageUnavailableError(STORAGE_UNAVAILABLE_DETAIL) from error
        return {level: count for level, count in result.result_rows}
