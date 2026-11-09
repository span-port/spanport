"""Live tail: new matching logs of one project, a batch every few seconds.

Each poll reads the newest matching logs of the last TAIL_WINDOW and passes on only those not
sent before, so logs that arrive a few seconds late (the collector batches) still appear once.
A caller runs a few tails at most; each tail checks every minute that its caller may still read
the project, and ends after the longest allowed run (the UI then opens a new one).
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from spanport_server.core.constants import (
    DEFAULT_MAX_TAILS_PER_CALLER,
    DEFAULT_TAIL_MAX_MINUTES,
    MAX_FUTURE_LOG_SKEW,
    NO_PROJECT_DETAIL,
    SECONDS_PER_MINUTE,
    STREAM_SLOT_MARGIN_SECONDS,
    STREAM_SLOT_RETRY_SECONDS,
    TAIL_BATCH_LIMIT,
    TAIL_POLL_SECONDS,
    TAIL_RECHECK_SECONDS,
    TAIL_SLOT_KEY,
    TAIL_WINDOW,
    TOO_MANY_TAILS_DETAIL,
)
from spanport_server.core.errors import (
    CsrfError,
    InvalidKeyError,
    MissingScopeError,
    NotFoundError,
    NotSignedInError,
    RateLimitedError,
)
from spanport_server.core.ids import UuidV7
from spanport_server.core.log_query_model import Condition
from spanport_server.core.rate_limiter import ConcurrencyLimiter, Lease
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.log_search import LogItem, LogQuery, LogTailRequest
from spanport_server.services.log_query_parser import build_condition
from spanport_server.services.log_search_service import LogSearchStore, ProjectLookup

logger = logging.getLogger(__name__)

# Authenticates the tail's caller again: their session or key as it is now.
type CallerCheck = Callable[[], Awaitable[Caller]]

# Why a caller may no longer read: signed out, user removed, key revoked or expired, scope gone.
ACCESS_LOST_ERRORS = (NotSignedInError, CsrfError, InvalidKeyError, MissingScopeError)


@dataclass(frozen=True)
class OpenTail:
    """A checked live tail request, ready to stream, holding one of its caller's tail slots."""

    org_id: UuidV7
    project_id: UuidV7
    condition: Condition | None
    caller_label: str
    lease: Lease


class LogTailService:
    """Opens and runs live tails."""

    def __init__(
        self,
        projects: ProjectLookup,
        logs: LogSearchStore,
        slots: ConcurrencyLimiter,
        max_tails: int = DEFAULT_MAX_TAILS_PER_CALLER,
        max_minutes: int = DEFAULT_TAIL_MAX_MINUTES,
        wait: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create the service.

        Args:
            projects: Project ownership checks (Postgres).
            logs: Stored logs (ClickHouse).
            slots: Tails running per caller, shared by the whole app.
            max_tails: Tails one caller may run at once (SPANPORT_RATE_LIMIT_CONCURRENT_TAILS).
            max_minutes: How long one tail may run (SPANPORT_TAIL_MAX_MINUTES).
            wait: Pause between polls; tests pass one that doesn't sleep.
            clock: Monotonic seconds; tests pass a fake one.
        """
        self._projects = projects
        self._logs = logs
        self._slots = slots
        self._max_tails = max_tails
        self._max_seconds = max_minutes * SECONDS_PER_MINUTE
        self._wait = wait
        self._clock = clock

    async def open(self, caller: Caller, request: LogTailRequest) -> OpenTail:
        """Check the request before any streaming starts, so errors are normal responses.

        Raises:
            NotFoundError: The project isn't in the caller's organization.
            InvalidRequestError: The query is not valid.
            RateLimitedError: The caller already runs the most tails allowed.
        """
        if not await self._may_read(caller, request.project_id):
            raise NotFoundError(NO_PROJECT_DETAIL)
        condition = build_condition(request.filters, request.combine, request.query)
        slot_key = TAIL_SLOT_KEY.format(org_id=caller.org_id, caller=caller.label)
        lease = self._slots.acquire(
            slot_key, self._max_tails, self._max_seconds + STREAM_SLOT_MARGIN_SECONDS
        )
        if lease is None:
            logger.warning(
                "log tail refused: too many open %s limit=%d", caller.label, self._max_tails
            )
            raise RateLimitedError(
                TOO_MANY_TAILS_DETAIL.format(limit=self._max_tails), STREAM_SLOT_RETRY_SECONDS
            )
        logger.info(
            "log tail opened %s project=%s filters=%d query=%s",
            caller.label,
            request.project_id,
            len(request.filters),
            bool(request.query),
        )
        return OpenTail(
            org_id=caller.org_id,
            project_id=request.project_id,
            condition=condition,
            caller_label=caller.label,
            lease=lease,
        )

    async def batches(self, tail: OpenTail, recheck: CallerCheck) -> AsyncIterator[list[LogItem]]:
        """New logs, oldest first, one batch per poll (often empty).

        Runs until cancelled, until the caller may no longer read the project (checked every
        TAIL_RECHECK_SECONDS) or until the longest allowed run is over. The tail's slot is
        given back however it ends.

        Raises:
            StorageUnavailableError: ClickHouse is down.
        """
        started = checked = self._clock()
        sent: dict[UuidV7, datetime] = {}
        try:
            while True:
                elapsed = self._clock() - started
                if elapsed >= self._max_seconds:
                    logger.info(
                        "log tail ended: time limit %s project=%s minutes=%d",
                        tail.caller_label,
                        tail.project_id,
                        elapsed // SECONDS_PER_MINUTE,
                    )
                    return
                if self._clock() - checked >= TAIL_RECHECK_SECONDS:
                    if not await self._still_allowed(tail, recheck):
                        return
                    checked = self._clock()
                fresh, sent = await self._poll(tail, sent)
                yield fresh
                await self._wait(TAIL_POLL_SECONDS)
        finally:
            self._slots.release(tail.lease)

    async def _poll(
        self, tail: OpenTail, sent: dict[UuidV7, datetime]
    ) -> tuple[list[LogItem], dict[UuidV7, datetime]]:
        """The logs not sent yet, oldest first, and the ids sent that are still in the window."""
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
        return fresh, {log_id: ts for log_id, ts in sent.items() if ts >= now - TAIL_WINDOW}

    async def _still_allowed(self, tail: OpenTail, recheck: CallerCheck) -> bool:
        """Whether the tail's caller is still signed in (or their key still valid) and may still
        see the project; logs one line when not.
        """
        try:
            caller = await recheck()
        except ACCESS_LOST_ERRORS as error:
            logger.info(
                "log tail ended: access lost %s project=%s code=%s",
                tail.caller_label,
                tail.project_id,
                error.code,
            )
            return False
        if caller.org_id == tail.org_id and await self._may_read(caller, tail.project_id):
            return True
        logger.info(
            "log tail ended: project no longer visible %s project=%s",
            tail.caller_label,
            tail.project_id,
        )
        return False

    async def _may_read(self, caller: Caller, project_id: UuidV7) -> bool:
        """A project the caller may not see answers like one that doesn't exist."""
        return caller.can_see(project_id) and await self._projects.project_exists(
            caller.org_id, project_id
        )
