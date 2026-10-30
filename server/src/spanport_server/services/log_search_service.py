"""Searches and counts a project's logs for a signed-in person or an admin key."""

import logging
import time
from datetime import UTC, datetime
from typing import Protocol

from spanport_server.core.constants import LOG_RETENTION
from spanport_server.core.errors import InvalidRequestError, NotFoundError
from spanport_server.core.ids import UuidV7
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.log_search import (
    LogCountsResponse,
    LogFilterRequest,
    LogItem,
    LogPosition,
    LogQuery,
    LogSearchRequest,
    LogSearchResponse,
)
from spanport_server.services.log_cursor import decode_cursor, encode_cursor
from spanport_server.services.log_query_parser import build_condition

logger = logging.getLogger(__name__)


class ProjectLookup(Protocol):
    """Checks that a project belongs to an organization."""

    async def project_exists(self, org_id: UuidV7, project_id: UuidV7) -> bool:
        """Whether the project exists in this organization."""
        ...


class LogSearchStore(Protocol):
    """Reads stored logs."""

    async def search(self, query: LogQuery, after: LogPosition | None, limit: int) -> list[LogItem]:
        """Up to `limit` matching logs, newest first, after `after`."""
        ...

    async def count_by_level(self, query: LogQuery) -> dict[str, int]:
        """Matching logs per level."""
        ...


class LogSearchService:
    """Applies the search rules: own org only, last 7 days only, newest first, bounded pages."""

    def __init__(self, projects: ProjectLookup, logs: LogSearchStore) -> None:
        """Create the service.

        Args:
            projects: Project ownership checks (Postgres).
            logs: Stored logs (ClickHouse).
        """
        self._projects = projects
        self._logs = logs

    async def search(self, caller: Caller, request: LogSearchRequest) -> LogSearchResponse:
        """Return one page of matching logs, newest first.

        Args:
            caller: The signed-in person or admin key; it decides the organization.
            request: Project, range, filters, query, page size and cursor.

        Returns:
            The page, and a cursor for the next one when there are more.

        Raises:
            NotFoundError: The project isn't in the caller's organization.
            InvalidRequestError: Bad range, query or cursor.
            StorageUnavailableError: ClickHouse is down.
        """
        started = time.perf_counter()
        query = await self._bounded_query(caller, request)
        after = decode_cursor(request.cursor) if request.cursor else None
        # One extra row tells whether another page exists.
        rows = await self._logs.search(query, after, request.limit + 1)
        page = rows[: request.limit]
        has_more = len(rows) > request.limit
        next_cursor = (
            encode_cursor(LogPosition(ts=page[-1].ts, log_id=page[-1].log_id)) if has_more else None
        )
        logger.info(
            "log search %s project=%s range_minutes=%d filters=%d query=%s page=%s rows=%d "
            "duration_ms=%d",
            caller.label,
            request.project_id,
            (query.end - query.start).total_seconds() // 60,
            len(request.filters),
            bool(request.query),
            after is not None,
            len(page),
            (time.perf_counter() - started) * 1000,
        )
        return LogSearchResponse(data=page, next_cursor=next_cursor, has_more=has_more)

    async def counts(self, caller: Caller, request: LogFilterRequest) -> LogCountsResponse:
        """Count matching logs, in total and per level.

        Raises:
            NotFoundError: The project isn't in the caller's organization.
            InvalidRequestError: Bad range or query.
            StorageUnavailableError: ClickHouse is down.
        """
        started = time.perf_counter()
        query = await self._bounded_query(caller, request)
        by_level = await self._logs.count_by_level(query)
        total = sum(by_level.values())
        logger.info(
            "log counts %s project=%s filters=%d query=%s total=%d duration_ms=%d",
            caller.label,
            request.project_id,
            len(request.filters),
            bool(request.query),
            total,
            (time.perf_counter() - started) * 1000,
        )
        return LogCountsResponse(total=total, by_level=by_level)

    async def _bounded_query(self, caller: Caller, request: LogFilterRequest) -> LogQuery:
        return await bounded_query(self._projects, caller, request)


async def bounded_query(
    projects: ProjectLookup, caller: Caller, request: LogFilterRequest
) -> LogQuery:
    """Check ownership and range, parse the filters, and build the bounded query.

    Shared by search, counts and export, so they always apply the same rules.

    Raises:
        NotFoundError: The project isn't in the caller's organization, or they may not see it.
        InvalidRequestError: Bad range (backwards, or older than 7 days) or query.
    """
    # A project the caller may not see answers like one that doesn't exist.
    if not caller.can_see(request.project_id) or not await projects.project_exists(
        caller.org_id, request.project_id
    ):
        raise NotFoundError("No project with this id in your organization.")
    start = request.start.astimezone(UTC)
    end = request.end.astimezone(UTC)
    if end <= start:
        raise InvalidRequestError("end must be after start.")
    if start < datetime.now(UTC) - LOG_RETENTION:
        raise InvalidRequestError("start must be within the last 7 days; older logs are gone.")
    return LogQuery(
        org_id=caller.org_id,
        project_id=request.project_id,
        start=start,
        end=end,
        condition=build_condition(request.filters, request.combine, request.query),
    )
