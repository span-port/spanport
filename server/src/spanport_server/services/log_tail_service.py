"""Live tail: new matching logs of one project, a batch every few seconds.

Each poll reads the newest matching logs of the last TAIL_WINDOW and passes on only those not
sent before, so logs that arrive a few seconds late (the collector batches) still appear once.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from spanport_server.core.constants import (
    MAX_FUTURE_LOG_SKEW,
    TAIL_BATCH_LIMIT,
    TAIL_POLL_SECONDS,
    TAIL_WINDOW,
)
from spanport_server.core.errors import NotFoundError
from spanport_server.core.ids import UuidV7
from spanport_server.core.log_query_model import Condition
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.log_search import LogItem, LogQuery, LogTailRequest
from spanport_server.services.log_query_parser import build_condition
from spanport_server.services.log_search_service import LogSearchStore, ProjectLookup

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpenTail:
    """A checked live tail request, ready to stream."""

    org_id: UuidV7
    project_id: UuidV7
    condition: Condition | None


class LogTailService:
    """Opens and runs live tails."""

    def __init__(
        self,
        projects: ProjectLookup,
        logs: LogSearchStore,
        wait: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Create the service.

        Args:
            projects: Project ownership checks (Postgres).
            logs: Stored logs (ClickHouse).
            wait: Pause between polls; tests pass one that doesn't sleep.
        """
        self._projects = projects
        self._logs = logs
        self._wait = wait

    async def open(self, caller: Caller, request: LogTailRequest) -> OpenTail:
        """Check the request before any streaming starts, so errors are normal responses.

        Raises:
            NotFoundError: The project isn't in the caller's organization.
            InvalidRequestError: The query is not valid.
        """
        # A project the caller may not see answers like one that doesn't exist.
        if not caller.can_see(request.project_id) or not await self._projects.project_exists(
            caller.org_id, request.project_id
        ):
            raise NotFoundError("No project with this id in your organization.")
        condition = build_condition(request.filters, request.combine, request.query)
        logger.info(
            "log tail opened %s project=%s filters=%d query=%s",
            caller.label,
            request.project_id,
            len(request.filters),
            bool(request.query),
        )
        return OpenTail(org_id=caller.org_id, project_id=request.project_id, condition=condition)

    async def batches(self, tail: OpenTail) -> AsyncIterator[list[LogItem]]:
        """New logs, oldest first, one batch per poll (often empty). Runs until cancelled.

        Raises:
            StorageUnavailableError: ClickHouse is down.
        """
        sent: dict[UuidV7, datetime] = {}
        while True:
            now = datetime.now(UTC)
            query = LogQuery(
                org_id=tail.org_id,
                project_id=tail.project_id,
                start=now - TAIL_WINDOW,
                end=now + MAX_FUTURE_LOG_SKEW,
                condition=tail.condition,
            )
            newest_first = await self._logs.search(query, after=None, limit=TAIL_BATCH_LIMIT)
            fresh = [row for row in reversed(newest_first) if row.log_id not in sent]
            sent.update((row.log_id, row.ts) for row in fresh)
            # Forget ids that have left the window; they can't be read again.
            sent = {log_id: ts for log_id, ts in sent.items() if ts >= now - TAIL_WINDOW}
            yield fresh
            await self._wait(TAIL_POLL_SECONDS)
