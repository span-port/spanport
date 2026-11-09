"""Stores logs sent through the collector."""

import asyncio
import logging
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol

from spanport_server.core.constants import INVALID_KEY_DETAIL
from spanport_server.core.errors import InvalidKeyError, InvalidRequestError, PayloadTooLargeError
from spanport_server.schemas.api_key import ApiKeyRecord
from spanport_server.schemas.log_row import LogRow
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.otlp_log_parser import (
    build_log_rows,
    drop_expired,
)

logger = logging.getLogger(__name__)


class LogWriter(Protocol):
    """Writes log rows."""

    async def insert_logs(self, rows: Sequence[LogRow]) -> None:
        """Insert rows, waiting until they are on disk."""
        ...


class LogIngestService:
    """Decodes OTLP logs and stores them under the data key's project."""

    def __init__(self, writer: LogWriter) -> None:
        """Create the service.

        Args:
            writer: Where rows are stored.
        """
        self._writer = writer

    async def ingest(self, key: ApiKeyRecord, payload: bytes) -> int:
        """Decode and store one OTLP logs request.

        Args:
            key: The authenticated data key; it decides the org and project.
            payload: The decompressed protobuf body.

        Returns:
            How many log records were stored. Records older than the retention are dropped.

        Raises:
            PayloadTooLargeError: More than MAX_INGEST_RECORDS log records.
            InvalidRequestError: Not a valid OTLP logs request, or storage refused a value.
            StorageUnavailableError: Log storage is down; the collector should retry.
        """
        started = time.perf_counter()
        if key.project_id is None:
            # Data keys always have a project (a database check enforces it); never guess one.
            raise InvalidKeyError(INVALID_KEY_DETAIL)
        project = ProjectRef(org_id=key.org_id, project_id=key.project_id)
        received_at = datetime.now(UTC)
        try:
            all_rows = await asyncio.to_thread(build_log_rows, payload, project, received_at)
            kept_rows = drop_expired(all_rows, received_at)
            if kept_rows:
                await self._writer.insert_logs(kept_rows)
        except (InvalidRequestError, PayloadTooLargeError) as error:
            logger.warning(
                "logs rejected org=%s project=%s key=...%s code=%s bytes=%d",
                key.org_id,
                key.project_id,
                key.last_four,
                error.code,
                len(payload),
            )
            raise
        logger.info(
            "logs ingested org=%s project=%s key=...%s records=%d dropped_expired=%d bytes=%d "
            "duration_ms=%d",
            key.org_id,
            key.project_id,
            key.last_four,
            len(kept_rows),
            len(all_rows) - len(kept_rows),
            len(payload),
            (time.perf_counter() - started) * 1000,
        )
        return len(kept_rows)
