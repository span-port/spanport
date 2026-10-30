"""POST /api/v1/logs/search and /api/v1/logs/counts: query a project's logs.

Callers are signed-in people (session cookie plus CSRF header) or scripts with an admin key.
Checks run in this order: caller → content type → body size (64 KB) → body validation.
An unauthenticated request never has its body read.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from spanport_server.core.constants import LOG_COUNTS_PATH, LOG_SEARCH_PATH, MAX_SEARCH_BODY_BYTES
from spanport_server.core.request_body import parse_json_body
from spanport_server.dependencies import get_log_search_service, require_logs_reader
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.log_search import (
    LogCountsResponse,
    LogFilterRequest,
    LogSearchRequest,
    LogSearchResponse,
)
from spanport_server.services.log_search_service import LogSearchService

router = APIRouter()


@router.post(LOG_SEARCH_PATH)
async def search_logs(
    request: Request,
    caller: Annotated[Caller, Depends(require_logs_reader)],
    search_service: Annotated[LogSearchService, Depends(get_log_search_service)],
    content_type: Annotated[str, Header()] = "",
) -> LogSearchResponse:
    """Return one page of a project's logs, newest first.

    Returns:
        `data`, `next_cursor` and `has_more`.

    Raises:
        InvalidKeyError / NotSignedInError: No valid admin key or session (401).
        MissingScopeError / CsrfError: The key lacks logs:read, or no CSRF header (403).
        UnsupportedMediaTypeError / PayloadTooLargeError / InvalidRequestError: Bad body.
        NotFoundError: The project isn't in the caller's organization (404).
    """
    body = await parse_json_body(request, content_type, LogSearchRequest, MAX_SEARCH_BODY_BYTES)
    return await search_service.search(caller, body)


@router.post(LOG_COUNTS_PATH)
async def count_logs(
    request: Request,
    caller: Annotated[Caller, Depends(require_logs_reader)],
    search_service: Annotated[LogSearchService, Depends(get_log_search_service)],
    content_type: Annotated[str, Header()] = "",
) -> LogCountsResponse:
    """Count a project's matching logs, in total and per level.

    Returns:
        `total` and `by_level`.

    Raises:
        The same errors as search_logs.
    """
    body = await parse_json_body(request, content_type, LogFilterRequest, MAX_SEARCH_BODY_BYTES)
    return await search_service.counts(caller, body)
