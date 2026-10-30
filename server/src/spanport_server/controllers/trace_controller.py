"""The Requests screen's API: search a project's incoming requests, and one trace's waterfall.

Same callers as log search (an admin key with logs:read, or a signed-in session).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request

from spanport_server.core.constants import MAX_SEARCH_BODY_BYTES, TRACE_PATH, TRACE_SEARCH_PATH
from spanport_server.core.ids import UuidV7
from spanport_server.core.request_body import parse_json_body
from spanport_server.dependencies import get_trace_service, require_logs_reader
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.trace import TraceDetail, TraceSearchRequest, TraceSearchResponse
from spanport_server.services.trace_service import TraceService

router = APIRouter()


@router.post(TRACE_SEARCH_PATH)
async def search_traces(
    request: Request,
    caller: Annotated[Caller, Depends(require_logs_reader)],
    trace_service: Annotated[TraceService, Depends(get_trace_service)],
    content_type: Annotated[str, Header()] = "",
) -> TraceSearchResponse:
    """One page of a project's incoming requests, newest first.

    Raises:
        InvalidKeyError / NotSignedInError (401), MissingScopeError / CsrfError (403),
        InvalidRequestError: bad body, range or cursor (400), NotFoundError: project (404),
        StorageUnavailableError (503).
    """
    body = await parse_json_body(request, content_type, TraceSearchRequest, MAX_SEARCH_BODY_BYTES)
    return await trace_service.search(caller, body)


@router.get(TRACE_PATH)
async def get_trace(
    trace_id: str,
    project_id: Annotated[UuidV7, Query()],
    caller: Annotated[Caller, Depends(require_logs_reader)],
    trace_service: Annotated[TraceService, Depends(get_trace_service)],
) -> TraceDetail:
    """Every span of one trace in the project, as a waterfall.

    Raises:
        InvalidKeyError / NotSignedInError (401), MissingScopeError (403),
        InvalidRequestError: not a trace id (400), NotFoundError: project or trace (404),
        StorageUnavailableError (503).
    """
    return await trace_service.get_trace(caller, project_id, trace_id)
