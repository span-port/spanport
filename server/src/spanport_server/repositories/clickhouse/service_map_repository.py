"""What calls what, for the service map: each service's incoming requests, its calls to
databases, other systems and LLM providers, and its requests to your other services.

Every query is bounded by org, project and time, and uses bound parameters only.
"""

from collections.abc import Sequence
from typing import Any

from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.driver.exceptions import OperationalError

from spanport_server.core.constants import (
    CALLER_SPAN_SLACK,
    DB_NAME_SEPARATOR,
    DB_NAMESPACE_ATTRIBUTES,
    DB_SYSTEM_ATTRIBUTES,
    LLM_PROVIDER_ATTRIBUTES,
    PEER_HOST_ATTRIBUTES,
    PEER_URL_ATTRIBUTES,
    SPANS_TABLE,
    STORAGE_UNAVAILABLE_DETAIL,
    UNNAMED_DATABASE,
)
from spanport_server.core.errors import StorageUnavailableError
from spanport_server.repositories.clickhouse.endpoint_repository import (
    INCOMING_SQL,
    TENANT_SQL,
    endpoint_parameters,
    with_service_filter,
)
from spanport_server.schemas.endpoint import EndpointQuery
from spanport_server.schemas.service_map import (
    CallStats,
    MapRows,
    ServiceEdgeRow,
    ServiceRow,
    StepEdgeRow,
)

IN_RANGE_SQL = "start_ts >= {start:DateTime64(6, 'UTC')} AND start_ts < {end:DateTime64(6, 'UTC')}"
FAILED_SQL = "(status_code = {error_status:String} OR http_status >= {first_server_error:UInt16})"
STATS_SQL = (
    f"count(), countIf({FAILED_SQL}), quantiles({{typical:Float64}}, {{slow:Float64}})(duration_ns)"
)
SERVICES_SQL = (
    "SELECT service, count(), countIf(failed), "  # noqa: S608
    "quantiles({typical:Float64}, {slow:Float64})(duration_ns) "
    f"FROM ({INCOMING_SQL}) GROUP BY service"
)
# Database, outgoing and LLM calls. A call inside another such call (an LLM call's HTTP request)
# is left out, and so is an outgoing call another of your services answered (see SERVICE_CALLS).
# A client span naming a database system is a database call: spans stored before ingest knew
# the current attribute name (db.system.name) were filed as outgoing calls.
STEP_SPANS_SQL = (
    "SELECT trace_id, span_id, parent_span_id, service, name, status_code, "  # noqa: S608
    "if(category = {client:String} AND arrayExists(key -> attributes[key] != '', "
    "{db_system_keys:Array(String)}), {db:String}, category) AS step_category, "
    f"http_status, duration_ns, attributes FROM {SPANS_TABLE} WHERE {TENANT_SQL} "
    f"AND category IN ({{db:String}}, {{client:String}}, {{llm:String}}) AND {IN_RANGE_SQL}"
)
ANSWERED_SQL = (
    f"SELECT trace_id, parent_span_id FROM {SPANS_TABLE} WHERE {TENANT_SQL} "  # noqa: S608
    "AND category = {incoming:String} AND parent_span_id != '' "
    "AND start_ts >= {start:DateTime64(6, 'UTC')} AND start_ts < {steps_end:DateTime64(6, 'UTC')}"
)
# The first attribute with a value, among the keys bound as the given array parameter.
DB_NAMESPACE_SQL = (
    "arrayFirst(value -> value != '', "
    "arrayMap(key -> attributes[key], {db_namespace_keys:Array(String)}))"
)
# e.g. "postgresql · kosha": the database system (or "database"), then its name if known.
DB_TARGET_SQL = (
    "concat(arrayFirst(value -> value != '', arrayConcat("
    "arrayMap(key -> attributes[key], {db_system_keys:Array(String)}), [{unnamed_db:String}])), "
    f"if({DB_NAMESPACE_SQL} != '', concat({{db_separator:String}}, {DB_NAMESPACE_SQL}), ''))"
)
PEER_TARGET_SQL = (
    "arrayFirst(value -> value != '', arrayConcat("
    "arrayMap(key -> attributes[key], {peer_host_keys:Array(String)}), "
    "arrayMap(key -> domain(attributes[key]), {peer_url_keys:Array(String)}), [name]))"
)
LLM_TARGET_SQL = (
    "arrayFirst(value -> value != '', arrayConcat("
    "arrayMap(key -> attributes[key], {llm_provider_keys:Array(String)}), [name]))"
)
STEP_EDGES_SQL = (
    "SELECT service, step_category, "  # noqa: S608
    f"multiIf(step_category = {{db:String}}, {DB_TARGET_SQL}, step_category = {{llm:String}}, "
    f"{LLM_TARGET_SQL}, {PEER_TARGET_SQL}) AS target, {STATS_SQL} "
    f"FROM ({STEP_SPANS_SQL}) "
    f"WHERE (trace_id, parent_span_id) NOT IN (SELECT trace_id, span_id FROM ({STEP_SPANS_SQL})) "
    f"AND (trace_id, span_id) NOT IN ({ANSWERED_SQL}) "
    "GROUP BY service, step_category, target ORDER BY count() DESC LIMIT {limit:UInt32}"
)
# Requests to your services made by another of your services: the request's parent span is in
# the caller.
SERVICE_CALLS_SQL = (
    "SELECT c.service, r.service, count(), countIf(r.failed), "  # noqa: S608
    "quantiles({typical:Float64}, {slow:Float64})(r.duration_ns) "
    f"FROM (SELECT trace_id, parent_span_id, service, duration_ns, {FAILED_SQL} AS failed "
    f"FROM {SPANS_TABLE} WHERE {TENANT_SQL} AND category = {{incoming:String}} "
    f"AND parent_span_id != '' AND {IN_RANGE_SQL}) AS r "
    f"INNER JOIN (SELECT trace_id, span_id, service FROM {SPANS_TABLE} WHERE {TENANT_SQL} "
    "AND start_ts >= {callers_start:DateTime64(6, 'UTC')} "
    "AND start_ts < {end:DateTime64(6, 'UTC')}) AS c "
    "ON r.trace_id = c.trace_id AND r.parent_span_id = c.span_id "
    "WHERE c.service != r.service "
    "GROUP BY c.service, r.service ORDER BY count() DESC LIMIT {limit:UInt32}"
)


def call_stats(calls: int, errors: int, quantiles: Sequence[float]) -> CallStats:
    """A row's count, failures and (p50, p95) as CallStats."""
    return CallStats(calls=calls, errors=errors, p50_ns=quantiles[0], p95_ns=quantiles[1])


class ServiceMapRepository:
    """spans table reads for the service map."""

    def __init__(self, client: AsyncClient) -> None:
        """Create the repository.

        Args:
            client: ClickHouse client.
        """
        self._client = client

    async def map_rows(self, query: EndpointQuery, limit: int) -> MapRows:
        """Each service's requests, and up to `limit` lines of each kind (most calls first).

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        parameters = endpoint_parameters(query) | {
            "limit": limit,
            "callers_start": query.start - CALLER_SPAN_SLACK,
            "db_system_keys": list(DB_SYSTEM_ATTRIBUTES),
            "db_namespace_keys": list(DB_NAMESPACE_ATTRIBUTES),
            "unnamed_db": UNNAMED_DATABASE,
            "db_separator": DB_NAME_SEPARATOR,
            "peer_host_keys": list(PEER_HOST_ATTRIBUTES),
            "peer_url_keys": list(PEER_URL_ATTRIBUTES),
            "llm_provider_keys": list(LLM_PROVIDER_ATTRIBUTES),
        }
        services = await self._rows(with_service_filter(SERVICES_SQL, query), parameters)
        steps = await self._rows(STEP_EDGES_SQL, parameters)
        service_calls = await self._rows(SERVICE_CALLS_SQL, parameters)
        return MapRows(
            services=[
                ServiceRow(service=service, stats=call_stats(calls, errors, quantiles))
                for service, calls, errors, quantiles in services
            ],
            steps=[
                StepEdgeRow(
                    service=service,
                    category=category,
                    target=target,
                    stats=call_stats(calls, errors, quantiles),
                )
                for service, category, target, calls, errors, quantiles in steps
            ],
            service_calls=[
                ServiceEdgeRow(
                    caller=caller, callee=callee, stats=call_stats(calls, errors, quantiles)
                )
                for caller, callee, calls, errors, quantiles in service_calls
            ],
        )

    async def _rows(self, sql: str, parameters: dict[str, Any]) -> list[Sequence[Any]]:
        try:
            result = await self._client.query(sql, parameters=parameters)
        except OperationalError as error:
            raise StorageUnavailableError(STORAGE_UNAVAILABLE_DETAIL) from error
        return list(result.result_rows)
