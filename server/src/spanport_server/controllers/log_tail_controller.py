"""POST /api/v1/logs/tail: new logs of one project as a Server-Sent Events stream.

The caller, the body and the project are checked before the stream starts, so a bad request gets
a normal problem+json response. The stream sends a `logs` event for each batch of new lines
(oldest first) and a heartbeat comment when idle, so proxies keep it open. It ends when the
client leaves. POST (read with fetch) rather than EventSource, because the filters go in a body.
"""

import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import TypeAdapter

from spanport_server.core.constants import (
    LOG_TAIL_PATH,
    MAX_SEARCH_BODY_BYTES,
    SSE_CONTENT_TYPE,
    SSE_HEARTBEAT,
    SSE_LOGS_EVENT,
    SSE_OPENED,
    STREAM_HEADERS,
    TAIL_HEARTBEAT_SECONDS,
)
from spanport_server.core.request_body import parse_json_body
from spanport_server.dependencies import get_log_tail_service, require_logs_reader
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.log_search import LogItem, LogTailRequest
from spanport_server.services.log_tail_service import LogTailService

router = APIRouter()

LOG_BATCH = TypeAdapter(list[LogItem])


@router.post(LOG_TAIL_PATH)
async def tail_logs(
    request: Request,
    caller: Annotated[Caller, Depends(require_logs_reader)],
    tail_service: Annotated[LogTailService, Depends(get_log_tail_service)],
    content_type: Annotated[str, Header()] = "",
) -> StreamingResponse:
    """Stream a project's new matching logs until the client disconnects.

    Returns:
        A text/event-stream response.

    Raises:
        InvalidKeyError / NotSignedInError: No valid admin key or session (401).
        MissingScopeError / CsrfError: The key lacks logs:read, or no CSRF header (403).
        UnsupportedMediaTypeError / PayloadTooLargeError / InvalidRequestError: Bad body or query.
        NotFoundError: The project isn't in the caller's organization (404).
    """
    body = await parse_json_body(request, content_type, LogTailRequest, MAX_SEARCH_BODY_BYTES)
    tail = await tail_service.open(caller, body)
    return StreamingResponse(
        server_sent_events(tail_service.batches(tail)),
        media_type=SSE_CONTENT_TYPE,
        headers=STREAM_HEADERS,
    )


async def server_sent_events(batches: AsyncIterator[list[LogItem]]) -> AsyncIterator[bytes]:
    """Turn batches into SSE frames: a comment at once (so proxies pass the headers on), then an
    event per non-empty batch, and a heartbeat when idle.
    """
    yield SSE_OPENED.encode()
    last_sent = time.monotonic()
    async for batch in batches:
        if batch:
            yield b"event: " + SSE_LOGS_EVENT.encode() + b"\ndata: "
            yield LOG_BATCH.dump_json(batch) + b"\n\n"
            last_sent = time.monotonic()
        elif time.monotonic() - last_sent >= TAIL_HEARTBEAT_SECONDS:
            yield SSE_HEARTBEAT.encode()
            last_sent = time.monotonic()
