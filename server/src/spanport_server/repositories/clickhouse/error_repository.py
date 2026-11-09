"""HTTP errors over time, for the Errors screen: 4xx and 5xx answers per interval, and the
failing requests of one interval with what their code logged.

Built on the same request selection as the APIs list (endpoint_repository). Every query is
bounded by org, project and time, with bound parameters only.
"""

from collections.abc import Sequence
from typing import Any

from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.driver.exceptions import OperationalError

from spanport_server.core.constants import (
    CLIENT_ADDRESS_ATTRIBUTES,
    END_HTTP_STATUS,
    FIRST_CLIENT_ERROR_STATUS,
    LOGS_TABLE,
    MAX_LOGGED_LENGTH,
    NANOS_PER_MILLISECOND,
    SPANS_TABLE,
    STORAGE_UNAVAILABLE_DETAIL,
)
from spanport_server.core.errors import StorageUnavailableError
from spanport_server.repositories.clickhouse.endpoint_repository import (
    INCOMING_SQL,
    TENANT_SQL,
    endpoint_parameters,
    with_service_filter,
)
from spanport_server.repositories.clickhouse.log_search_repository import as_utc
from spanport_server.schemas.endpoint import EndpointQuery
from spanport_server.schemas.errors import (
    ErrorApi,
    ErrorBucket,
    ErrorGroup,
    FailedRequest,
    StatusRange,
)

CLIENT_ERROR_SQL = (
    "http_status >= {first_client_error:UInt16} AND http_status < {first_server_error:UInt16}"
)
SERVER_ERROR_SQL = (
    "http_status >= {first_server_error:UInt16} AND http_status < {end_status:UInt16}"
)
IN_STATUS_RANGE_SQL = "http_status >= {status_first:UInt16} AND http_status < {status_end:UInt16}"
BUCKETS_SQL = (
    "SELECT toStartOfInterval(start_ts, toIntervalSecond({bucket_seconds:UInt32})) AS bucket, "  # noqa: S608
    f"count(), countIf({CLIENT_ERROR_SQL}), countIf({SERVER_ERROR_SQL}) "
    f"FROM ({INCOMING_SQL}) GROUP BY bucket ORDER BY bucket"
)
APIS_SQL = (
    "SELECT service, http_method, route, countIf(http_status >= {first_client_error:UInt16} "  # noqa: S608
    "AND http_status < {end_status:UInt16}) AS errors "
    f"FROM ({INCOMING_SQL}) GROUP BY service, http_method, route HAVING errors > 0 "
    "ORDER BY errors DESC, route LIMIT {limit:UInt32}"
)
WINDOW_TOTAL_SQL = f"SELECT count() FROM ({INCOMING_SQL}) WHERE {IN_STATUS_RANGE_SQL}"  # noqa: S608
GROUPS_SQL = (
    "SELECT http_status, service, http_method, route, count() AS requests "  # noqa: S608
    f"FROM ({INCOMING_SQL}) WHERE {IN_STATUS_RANGE_SQL} "
    "GROUP BY http_status, service, http_method, route "
    "ORDER BY requests DESC, http_status LIMIT {limit:UInt32}"
)
# The newest failing requests, with the caller's address (current attribute name first).
FAILED_SQL = (
    "SELECT trace_id, span_id, start_ts, service, http_method, "  # noqa: S608
    "if(http_route != '', http_route, name), http_status, duration_ns, "
    "if(attributes[{address_key:String}] != '', attributes[{address_key:String}], "
    "if(attributes[{forwarded_key:String}] != '', attributes[{forwarded_key:String}], "
    "attributes[{peer_key:String}])) "
    f"FROM {SPANS_TABLE} WHERE {TENANT_SQL} AND category = {{incoming:String}} "
    "AND start_ts >= {start:DateTime64(6, 'UTC')} AND start_ts < {end:DateTime64(6, 'UTC')} "
    f"AND span_id IN (SELECT span_id FROM ({INCOMING_SQL}) WHERE {IN_STATUS_RANGE_SQL} "
    "ORDER BY start_ts DESC LIMIT {limit:UInt32}) "
    "ORDER BY start_ts DESC"
)
# Each trace's most severe log line (the latest one among equals).
LOGGED_SQL = (
    "SELECT trace_id, substring(argMax(message, (severity_number, ts)), 1, {max_logged:UInt32}) "  # noqa: S608
    f"FROM {LOGS_TABLE} WHERE {TENANT_SQL} "
    "AND ts >= {start:DateTime64(6, 'UTC')} AND ts < {steps_end:DateTime64(6, 'UTC')} "
    "AND trace_id IN {trace_ids:Array(String)} GROUP BY trace_id"
)


def error_parameters(query: EndpointQuery) -> dict[str, Any]:
    """The endpoint parameters plus the status bounds the error queries use."""
    return endpoint_parameters(query) | {
        "first_client_error": FIRST_CLIENT_ERROR_STATUS,
        "end_status": END_HTTP_STATUS,
    }


class ErrorRepository:
    """spans and logs table reads for HTTP errors."""

    def __init__(self, client: AsyncClient) -> None:
        """Create the repository.

        Args:
            client: ClickHouse client.
        """
        self._client = client

    async def buckets(self, query: EndpointQuery, bucket_seconds: int) -> list[ErrorBucket]:
        """Requests, 4xx and 5xx per interval, oldest first (empty ones left out).

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        rows = await self._rows(BUCKETS_SQL, query, {"bucket_seconds": bucket_seconds})
        return [
            ErrorBucket(
                at=as_utc(at), requests=requests, client_errors=client, server_errors=server
            )
            for at, requests, client, server in rows
        ]

    async def failing_apis(self, query: EndpointQuery, limit: int) -> list[ErrorApi]:
        """The APIs with any 4xx or 5xx, most errors first.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        rows = await self._rows(APIS_SQL, query, {"limit": limit})
        return [
            ErrorApi(service=service, http_method=method, route=route, errors=errors)
            for service, method, route, errors in rows
        ]

    async def window_total(self, query: EndpointQuery, statuses: StatusRange) -> int:
        """How many requests answered a status in the range.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        rows = await self._rows(WINDOW_TOTAL_SQL, query, status_parameters(statuses))
        return int(rows[0][0])

    async def groups(
        self, query: EndpointQuery, statuses: StatusRange, limit: int
    ) -> list[ErrorGroup]:
        """Failing requests per status and API, most first.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        extra = status_parameters(statuses) | {"limit": limit}
        rows = await self._rows(GROUPS_SQL, query, extra)
        return [
            ErrorGroup(status=status, service=service, http_method=method, route=route, requests=n)
            for status, service, method, route, n in rows
        ]

    async def failed_requests(
        self, query: EndpointQuery, statuses: StatusRange, limit: int
    ) -> list[FailedRequest]:
        """The newest failing requests, without what they logged (see `logged_lines`).

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        address_key, forwarded_key, peer_key = CLIENT_ADDRESS_ATTRIBUTES
        extra = status_parameters(statuses) | {
            "limit": limit,
            "address_key": address_key,
            "forwarded_key": forwarded_key,
            "peer_key": peer_key,
        }
        return [failed_request(row) for row in await self._rows(FAILED_SQL, query, extra)]

    async def logged_lines(self, query: EndpointQuery, trace_ids: list[str]) -> dict[str, str]:
        """Each trace's most severe log line in the project, by trace id.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        if not trace_ids:
            return {}
        extra = {"trace_ids": trace_ids, "max_logged": MAX_LOGGED_LENGTH}
        return {
            trace_id: message for trace_id, message in await self._rows(LOGGED_SQL, query, extra)
        }

    async def _rows(
        self, sql: str, query: EndpointQuery, extra: dict[str, Any]
    ) -> list[Sequence[Any]]:
        parameters = error_parameters(query) | extra
        try:
            result = await self._client.query(
                with_service_filter(sql, query), parameters=parameters
            )
        except OperationalError as error:
            raise StorageUnavailableError(STORAGE_UNAVAILABLE_DETAIL) from error
        return list(result.result_rows)


def status_parameters(statuses: StatusRange) -> dict[str, int]:
    """The bound parameters of a status range."""
    return {"status_first": statuses.first, "status_end": statuses.end}


def failed_request(row: Sequence[Any]) -> FailedRequest:
    """A FAILED_SQL row, without what the request logged (see `logged_lines`)."""
    trace_id, span_id, start_ts, service, method, route, status, duration_ns, client_ip = row
    return FailedRequest(
        trace_id=trace_id,
        span_id=span_id,
        start_ts=as_utc(start_ts),
        service=service,
        http_method=method,
        route=route,
        http_status=status,
        duration_ms=duration_ns / NANOS_PER_MILLISECOND,
        client_ip=client_ip,
        logged="",
    )
