"""Exports the current log search as a CSV or NDJSON file, streamed in batches.

Same rules as search (own org, visible projects, last 7 days), plus: viewers can't export, and a
file holds at most MAX_EXPORT_LINES (larger exports, emailed as a link, come later).
"""

import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from spanport_server.core.constants import (
    CSV_CONTENT_TYPE,
    EXPORT_BATCH_SIZE,
    EXPORT_FILE_PREFIX,
    EXPORT_TIME_FORMAT,
    MAX_EXPORT_LINES,
    NDJSON_CONTENT_TYPE,
    NO_PROJECT_DETAIL,
    TOO_MANY_TO_EXPORT_DETAIL,
    VIEWER_EXPORT_DETAIL,
)
from spanport_server.core.errors import InvalidRequestError, NotAllowedError, NotFoundError
from spanport_server.core.ids import UuidV7
from spanport_server.schemas.auth import Caller, Role
from spanport_server.schemas.log_search import (
    ExportFormat,
    LogExportRequest,
    LogPosition,
    LogQuery,
)
from spanport_server.schemas.tenant import ProjectItem
from spanport_server.services.log_export_format import file_header, file_row
from spanport_server.services.log_search_service import LogSearchStore, bounded_query

logger = logging.getLogger(__name__)


class ExportProjects(Protocol):
    """Project checks and names for the export's file name."""

    async def project_exists(self, org_id: UuidV7, project_id: UuidV7) -> bool:
        """Whether the project exists in this organization."""
        ...

    async def find_project(self, org_id: UuidV7, project_id: UuidV7) -> ProjectItem | None:
        """The project, or None."""
        ...


@dataclass(frozen=True)
class PreparedExport:
    """A checked export, ready to stream."""

    query: LogQuery
    export_format: ExportFormat
    file_name: str
    content_type: str
    total: int
    caller_label: str


def content_type_of(export_format: ExportFormat) -> str:
    """The file's media type."""
    match export_format:
        case ExportFormat.CSV:
            return CSV_CONTENT_TYPE
        case ExportFormat.NDJSON:
            return NDJSON_CONTENT_TYPE


def export_file_name(project: ProjectItem, export_format: ExportFormat, at: datetime) -> str:
    """e.g. spanport-logs-northwind-hr-portal-production-20261030-1421.csv."""
    stamp = at.astimezone(UTC).strftime(EXPORT_TIME_FORMAT)
    parts = (EXPORT_FILE_PREFIX, project.client, project.project, project.environment, stamp)
    return "-".join(parts) + f".{export_format.value}"


class LogExportService:
    """Checks an export, then streams its rows newest first."""

    def __init__(self, projects: ExportProjects, logs: LogSearchStore) -> None:
        """Create the service.

        Args:
            projects: Project checks and names (Postgres).
            logs: Stored logs (ClickHouse).
        """
        self._projects = projects
        self._logs = logs

    async def prepare(self, caller: Caller, request: LogExportRequest) -> PreparedExport:
        """Check everything before the first byte is sent, so errors are normal responses.

        Raises:
            NotAllowedError: The caller is a viewer.
            NotFoundError: The project isn't in the caller's organization or not visible to them.
            InvalidRequestError: Bad range or query, or more than MAX_EXPORT_LINES match.
            StorageUnavailableError: ClickHouse is down.
        """
        if caller.role is Role.VIEWER:
            raise NotAllowedError(VIEWER_EXPORT_DETAIL)
        query = await bounded_query(self._projects, caller, request)
        project = await self._projects.find_project(caller.org_id, request.project_id)
        if project is None:
            raise NotFoundError(NO_PROJECT_DETAIL)
        total = sum((await self._logs.count_by_level(query)).values())
        if total > MAX_EXPORT_LINES:
            raise InvalidRequestError(
                TOO_MANY_TO_EXPORT_DETAIL.format(count=total, limit=MAX_EXPORT_LINES)
            )
        return PreparedExport(
            query=query,
            export_format=request.format,
            file_name=export_file_name(project, request.format, datetime.now(UTC)),
            content_type=content_type_of(request.format),
            total=total,
            caller_label=caller.label,
        )

    async def lines(self, export: PreparedExport) -> AsyncIterator[str]:
        """The file, a batch of rows at a time, newest first; logs one line when done."""
        started = time.perf_counter()
        yield file_header(export.export_format)
        written = 0
        after: LogPosition | None = None
        while written < MAX_EXPORT_LINES:
            batch = await self._logs.search(export.query, after, EXPORT_BATCH_SIZE)
            # Logs that arrived late (inside the range, after the count) never push it over.
            batch = batch[: MAX_EXPORT_LINES - written]
            if not batch:
                break
            yield "".join(file_row(export.export_format, item) for item in batch)
            written += len(batch)
            after = LogPosition(ts=batch[-1].ts, log_id=batch[-1].log_id)
            if len(batch) < EXPORT_BATCH_SIZE:
                break
        logger.info(
            "logs exported %s project=%s format=%s rows=%d duration_ms=%d",
            export.caller_label,
            export.query.project_id,
            export.export_format,
            written,
            (time.perf_counter() - started) * 1000,
        )
