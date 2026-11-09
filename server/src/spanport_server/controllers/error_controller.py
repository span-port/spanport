"""The Errors screen's API: 4xx and 5xx answers over time, and one interval's failing requests.

Same callers as log search (an admin key with logs:read, or a signed-in session).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from spanport_server.core.constants import (
    ERROR_SUMMARY_PATH,
    ERROR_WINDOW_PATH,
    MAX_SEARCH_BODY_BYTES,
)
from spanport_server.core.request_body import parse_json_body
from spanport_server.dependencies import get_error_service, require_logs_reader
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.errors import (
    ErrorSummaryRequest,
    ErrorSummaryResponse,
    ErrorWindowRequest,
    ErrorWindowResponse,
)
from spanport_server.services.error_service import ErrorService

router = APIRouter()


@router.post(ERROR_SUMMARY_PATH)
async def error_summary(
    request: Request,
    caller: Annotated[Caller, Depends(require_logs_reader)],
    error_service: Annotated[ErrorService, Depends(get_error_service)],
    content_type: Annotated[str, Header()] = "",
) -> ErrorSummaryResponse:
    """4xx and 5xx per interval in a time range, the totals and the failing APIs.

    Raises:
        InvalidKeyError / NotSignedInError (401), MissingScopeError / CsrfError (403),
        InvalidRequestError: bad body or range (400), NotFoundError: project (404),
        StorageUnavailableError (503).
    """
    body = await parse_json_body(request, content_type, ErrorSummaryRequest, MAX_SEARCH_BODY_BYTES)
    return await error_service.summary(caller, body)


@router.post(ERROR_WINDOW_PATH)
async def error_window(
    request: Request,
    caller: Annotated[Caller, Depends(require_logs_reader)],
    error_service: Annotated[ErrorService, Depends(get_error_service)],
    content_type: Annotated[str, Header()] = "",
) -> ErrorWindowResponse:
    """One interval's failing requests: by status and API, and the newest ones.

    Raises:
        InvalidKeyError / NotSignedInError (401), MissingScopeError / CsrfError (403),
        InvalidRequestError: bad body or range (400), NotFoundError: project (404),
        StorageUnavailableError (503).
    """
    body = await parse_json_body(request, content_type, ErrorWindowRequest, MAX_SEARCH_BODY_BYTES)
    return await error_service.window(caller, body)
