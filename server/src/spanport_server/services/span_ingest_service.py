"""Stores spans (traces) sent through the collector."""

import logging
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol

from spanport_server.core.constants import INVALID_KEY_DETAIL
from spanport_server.core.errors import InvalidKeyError
from spanport_server.schemas.api_key import ApiKeyRecord
from spanport_server.schemas.span_row import SpanRow
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.otlp_span_parser import (
    decode_traces_request,
    drop_expired_spans,
    to_span_rows,
)

logger = logging.getLogger(__name__)


class SpanWriter(Protocol):
    """Writes span rows."""

    async def insert_spans(self, rows: Sequence[SpanRow]) -> None:
        """Insert rows, waiting until they are on disk."""
        ...


class SpanIngestService:
    """Decodes OTLP traces and stores their spans under the data key's project."""

    def __init__(self, writer: SpanWriter) -> None:
        """Create the service.

        Args:
            writer: Where rows are stored.
        """
        self._writer = writer

    async def ingest(self, key: ApiKeyRecord, payload: bytes) -> int:
        """Decode and store one OTLP traces request.

        Args:
            key: The authenticated data key; it decides the org and project.
            payload: The decompressed protobuf body.

        Returns:
            How many spans were stored. Spans older than the retention are dropped.

        Raises:
            InvalidRequestError: The payload is not a valid OTLP traces request.
            StorageUnavailableError: Storage is down; the collector should retry.
        """
        started = time.perf_counter()
        if key.project_id is None:
            # Data keys always have a project (a database check enforces it); never guess one.
            raise InvalidKeyError(INVALID_KEY_DETAIL)
        request = decode_traces_request(payload)
        project = ProjectRef(org_id=key.org_id, project_id=key.project_id)
        received_at = datetime.now(UTC)
        all_rows = to_span_rows(request, project, received_at)
        kept_rows = drop_expired_spans(all_rows, received_at)
        if kept_rows:
            await self._writer.insert_spans(kept_rows)
        logger.info(
            "spans ingested org=%s project=%s key=...%s spans=%d dropped_expired=%d bytes=%d "
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
