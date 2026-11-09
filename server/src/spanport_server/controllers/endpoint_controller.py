"""The APIs screen's API: per-endpoint speed, errors and where the time goes.

Same callers as log search (an admin key with logs:read, or a signed-in session).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from spanport_server.core.constants import (
    ENDPOINT_DETAIL_PATH,
    ENDPOINT_SUMMARY_PATH,
    MAX_SEARCH_BODY_BYTES,
)
from spanport_server.core.request_body import parse_json_body
from spanport_server.dependencies import (
    get_endpoint_detail_service,
    get_endpoint_service,
    require_logs_reader,
)
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.endpoint import (
    EndpointDetailRequest,
    EndpointDetailResponse,
    EndpointSummaryRequest,
    EndpointSummaryResponse,
)
from spanport_server.services.endpoint_detail_service import EndpointDetailService
from spanport_server.services.endpoint_service import EndpointService

router = APIRouter()


@router.post(ENDPOINT_SUMMARY_PATH)
async def endpoint_summary(
    request: Request,
    caller: Annotated[Caller, Depends(require_logs_reader)],
    endpoint_service: Annotated[EndpointService, Depends(get_endpoint_service)],
    content_type: Annotated[str, Header()] = "",
) -> EndpointSummaryResponse:
    """A project's request totals and its busiest endpoints in a time range.

    Raises:
        InvalidKeyError / NotSignedInError (401), MissingScopeError / CsrfError (403),
        InvalidRequestError: bad body or range (400), NotFoundError: project (404),
        StorageUnavailableError (503).
    """
    body = await parse_json_body(
        request, content_type, EndpointSummaryRequest, MAX_SEARCH_BODY_BYTES
    )
    return await endpoint_service.summary(caller, body)


@router.post(ENDPOINT_DETAIL_PATH)
async def endpoint_detail(
    request: Request,
    caller: Annotated[Caller, Depends(require_logs_reader)],
    detail_service: Annotated[EndpointDetailService, Depends(get_endpoint_detail_service)],
    content_type: Annotated[str, Header()] = "",
) -> EndpointDetailResponse:
    """One endpoint in a time range: numbers, timeline, status codes, steps, slowest requests.

    Raises:
        InvalidKeyError / NotSignedInError (401), MissingScopeError / CsrfError (403),
        InvalidRequestError: bad body or range (400), NotFoundError: project (404),
        StorageUnavailableError (503).
    """
    body = await parse_json_body(
        request, content_type, EndpointDetailRequest, MAX_SEARCH_BODY_BYTES
    )
    return await detail_service.detail(caller, body)
