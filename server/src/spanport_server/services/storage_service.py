"""Setup -> Data -> Storage: how much each project of the organization keeps, and for how long.

Sizes are estimates: a project's rows times the table's average row size on disk.
"""

import logging
from typing import Protocol

from spanport_server.core.constants import (
    LOG_RETENTION,
    LOGS_TABLE,
    MAX_PROJECTS_LIMIT,
    SPAN_RETENTION,
    SPANS_TABLE,
)
from spanport_server.core.ids import UuidV7
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.storage import (
    ProjectRows,
    ProjectStorage,
    StorageResponse,
    TableUsage,
)
from spanport_server.schemas.tenant import ProjectItem

logger = logging.getLogger(__name__)

EMPTY_USAGE = TableUsage(rows=0, estimated_bytes=0, oldest=None, newest=None)


class ProjectLister(Protocol):
    """Lists an organization's projects."""

    async def list_projects(
        self, org_id: UuidV7, after_id: UuidV7 | None, limit: int
    ) -> list[ProjectItem]:
        """Up to `limit` projects of the org after `after_id`, ordered by id."""
        ...


class StorageStore(Protocol):
    """Row counts and sizes of stored telemetry."""

    async def log_rows(self, org_id: UuidV7) -> list[ProjectRows]:
        """Log lines per project of the organization."""
        ...

    async def span_rows(self, org_id: UuidV7) -> list[ProjectRows]:
        """Request steps per project of the organization."""
        ...

    async def bytes_per_row(self, table: str) -> float:
        """Average size of a row of `table` on disk."""
        ...


def usage(rows: ProjectRows | None, bytes_per_row: float) -> TableUsage:
    """One project's usage of a table; zeros when it has no rows."""
    if rows is None:
        return EMPTY_USAGE
    return TableUsage(
        rows=rows.rows,
        estimated_bytes=round(rows.rows * bytes_per_row),
        oldest=rows.oldest,
        newest=rows.newest,
    )


def total(usages: list[TableUsage]) -> TableUsage:
    """All projects' usage of a table added up."""
    oldest = [item.oldest for item in usages if item.oldest is not None]
    newest = [item.newest for item in usages if item.newest is not None]
    return TableUsage(
        rows=sum(item.rows for item in usages),
        estimated_bytes=sum(item.estimated_bytes for item in usages),
        oldest=min(oldest, default=None),
        newest=max(newest, default=None),
    )


class StorageService:
    """Summarises the organization's stored logs and traces per project."""

    def __init__(self, projects: ProjectLister, storage: StorageStore) -> None:
        """Create the service.

        Args:
            projects: The organization's projects (Postgres).
            storage: Row counts and sizes (ClickHouse).
        """
        self._projects = projects
        self._storage = storage

    async def summary(self, caller: Caller) -> StorageResponse:
        """Every project's stored logs and traces, with totals; biggest projects first.

        Raises:
            StorageUnavailableError: ClickHouse is down.
        """
        projects = await self._projects.list_projects(caller.org_id, None, MAX_PROJECTS_LIMIT)
        logs = {rows.project_id: rows for rows in await self._storage.log_rows(caller.org_id)}
        spans = {rows.project_id: rows for rows in await self._storage.span_rows(caller.org_id)}
        log_row_bytes = await self._storage.bytes_per_row(LOGS_TABLE)
        span_row_bytes = await self._storage.bytes_per_row(SPANS_TABLE)
        stored = [
            ProjectStorage(
                project_id=project.id,
                client=project.client,
                project=project.project,
                environment=project.environment,
                logs=usage(logs.get(project.id), log_row_bytes),
                spans=usage(spans.get(project.id), span_row_bytes),
            )
            for project in projects
        ]
        stored.sort(
            key=lambda item: item.logs.estimated_bytes + item.spans.estimated_bytes, reverse=True
        )
        totals = {
            LOGS_TABLE: total([item.logs for item in stored]),
            SPANS_TABLE: total([item.spans for item in stored]),
        }
        logger.info(
            "storage summary %s projects=%d log_rows=%d span_rows=%d",
            caller.label,
            len(stored),
            totals[LOGS_TABLE].rows,
            totals[SPANS_TABLE].rows,
        )
        return StorageResponse(
            logs_retention_days=LOG_RETENTION.days,
            spans_retention_days=SPAN_RETENTION.days,
            totals=totals,
            projects=stored,
        )
