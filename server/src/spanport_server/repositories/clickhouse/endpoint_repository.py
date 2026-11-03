"""Per-endpoint sums over the ClickHouse spans table, for the APIs screen.

Every query is bounded by org, project and time, and uses bound parameters only.
"""

from collections.abc import Sequence
from typing import Any

from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.driver.exceptions import OperationalError

from spanport_server.core.constants import (
    FIRST_SERVER_ERROR_STATUS,
    LAYER_SPAN_SLACK,
    QUANTILE_SLOW,
    QUANTILE_SLOWEST,
    QUANTILE_TYPICAL,
    SPAN_CATEGORY_CLIENT,
    SPAN_CATEGORY_DB,
    SPAN_CATEGORY_INCOMING,
    SPAN_CATEGORY_LLM,
    SPAN_STATUS_ERROR,
    SPANS_TABLE,
    STORAGE_UNAVAILABLE_DETAIL,
)
from spanport_server.core.errors import StorageUnavailableError
from spanport_server.schemas.endpoint import EndpointQuery, EndpointRow, TotalsRow

TENANT_SQL = "org_id = {org_id:UUID} AND project_id = {project_id:UUID}"
SERVICE_SQL = " AND service = {service:String}"
# Built only from fixed names and {placeholder} markers; every value is a bound parameter.
# An endpoint is the route when the framework reported one, else the span name.
INCOMING_SQL = (
    "SELECT trace_id, service, http_method, if(http_route != '', http_route, name) AS route, "  # noqa: S608
    "(status_code = {error_status:String} OR http_status >= {first_server_error:UInt16}) "
    "AS failed, duration_ns "
    f"FROM {SPANS_TABLE} WHERE {TENANT_SQL} AND category = {{incoming:String}} "
    "AND start_ts >= {start:DateTime64(6, 'UTC')} AND start_ts < {end:DateTime64(6, 'UTC')}"
    "{service_filter}"
)
# Database, outgoing and LLM steps of the same requests.
STEPS_SQL = (
    "SELECT trace_id, span_id, parent_span_id, service, category, duration_ns "  # noqa: S608
    f"FROM {SPANS_TABLE} WHERE {TENANT_SQL} "
    "AND category IN ({db:String}, {client:String}, {llm:String}) "
    "AND start_ts >= {start:DateTime64(6, 'UTC')} "
    "AND start_ts < {steps_end:DateTime64(6, 'UTC')}"
)
# Per trace and service. A step inside another such step (an LLM call's HTTP request) is
# skipped, so its time isn't counted twice.
LAYERS_SQL = (
    "SELECT trace_id, service, "  # noqa: S608
    "sumIf(duration_ns, category = {db:String}) AS db_ns, "
    "sumIf(duration_ns, category = {client:String}) AS external_ns, "
    "sumIf(duration_ns, category = {llm:String}) AS llm_ns "
    f"FROM ({STEPS_SQL}) "
    f"WHERE (trace_id, parent_span_id) NOT IN (SELECT trace_id, span_id FROM ({STEPS_SQL})) "
    "GROUP BY trace_id, service"
)
ENDPOINTS_SQL = (
    "SELECT r.service, r.http_method, r.route, count() AS requests, countIf(r.failed), "  # noqa: S608
    "quantiles({typical:Float64}, {slow:Float64}, {slowest:Float64})(r.duration_ns), "
    "sum(r.duration_ns), sum(l.db_ns), sum(l.external_ns), sum(l.llm_ns) "
    f"FROM ({INCOMING_SQL}) AS r "
    f"LEFT JOIN ({LAYERS_SQL}) AS l ON l.trace_id = r.trace_id AND l.service = r.service "
    "GROUP BY r.service, r.http_method, r.route "
    "ORDER BY requests DESC, r.route LIMIT {limit:UInt32}"
)
TOTALS_SQL = (
    "SELECT count(), countIf(failed), "  # noqa: S608
    "if(count() = 0, 0, quantile({slow:Float64})(duration_ns)) "
    f"FROM ({INCOMING_SQL})"
)


def endpoint_parameters(query: EndpointQuery) -> dict[str, Any]:
    """Every bound parameter the queries use."""
    parameters: dict[str, Any] = {
        "org_id": query.org_id,
        "project_id": query.project_id,
        "start": query.start,
        "end": query.end,
        "steps_end": query.end + LAYER_SPAN_SLACK,
        "incoming": SPAN_CATEGORY_INCOMING,
        "db": SPAN_CATEGORY_DB,
        "client": SPAN_CATEGORY_CLIENT,
        "llm": SPAN_CATEGORY_LLM,
        "error_status": SPAN_STATUS_ERROR,
        "first_server_error": FIRST_SERVER_ERROR_STATUS,
        "typical": QUANTILE_TYPICAL,
        "slow": QUANTILE_SLOW,
        "slowest": QUANTILE_SLOWEST,
    }
    if query.service:
        parameters["service"] = query.service
    return parameters


def with_service_filter(sql: str, query: EndpointQuery) -> str:
    """The SQL with the service condition in place, or none when no service is chosen."""
    return sql.replace("{service_filter}", SERVICE_SQL if query.service else "")


class EndpointRepository:
    """spans table sums per endpoint."""

    def __init__(self, client: AsyncClient) -> None:
        """Create the repository.

        Args:
            client: ClickHouse client.
        """
        self._client = client

    async def endpoint_rows(self, query: EndpointQuery, limit: int) -> list[EndpointRow]:
        """Up to `limit` endpoints, most requests first, with their step times.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        parameters = endpoint_parameters(query) | {"limit": limit}
        rows = await self._rows(with_service_filter(ENDPOINTS_SQL, query), parameters)
        return [
            EndpointRow(
                service=service,
                http_method=http_method,
                route=route,
                requests=requests,
                errors=errors,
                p50_ns=quantiles[0],
                p95_ns=quantiles[1],
                p99_ns=quantiles[2],
                total_ns=total_ns,
                db_ns=db_ns,
                external_ns=external_ns,
                llm_ns=llm_ns,
            )
            for (
                service,
                http_method,
                route,
                requests,
                errors,
                quantiles,
                total_ns,
                db_ns,
                external_ns,
                llm_ns,
            ) in rows
        ]

    async def endpoint_totals(self, query: EndpointQuery) -> TotalsRow:
        """Every request in the range: count, failures and the slow-5% time.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        rows = await self._rows(with_service_filter(TOTALS_SQL, query), endpoint_parameters(query))
        requests, errors, p95_ns = rows[0]
        return TotalsRow(requests=requests, errors=errors, p95_ns=p95_ns)

    async def _rows(self, sql: str, parameters: dict[str, Any]) -> list[Sequence[Any]]:
        try:
            result = await self._client.query(sql, parameters=parameters)
        except OperationalError as error:
            raise StorageUnavailableError(STORAGE_UNAVAILABLE_DETAIL) from error
        return list(result.result_rows)
