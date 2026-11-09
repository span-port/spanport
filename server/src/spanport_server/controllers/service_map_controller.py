"""The service map's API: what calls what in a project over a time range.

Same callers as log search (an admin key with logs:read, or a signed-in session).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from spanport_server.core.constants import MAX_SEARCH_BODY_BYTES, SERVICE_MAP_PATH
from spanport_server.core.request_body import parse_json_body
from spanport_server.dependencies import get_service_map_service, require_logs_reader
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.service_map import ServiceMapRequest, ServiceMapResponse
from spanport_server.services.service_map_service import ServiceMapService

router = APIRouter()


@router.post(SERVICE_MAP_PATH)
async def service_map(
    request: Request,
    caller: Annotated[Caller, Depends(require_logs_reader)],
    map_service: Annotated[ServiceMapService, Depends(get_service_map_service)],
    content_type: Annotated[str, Header()] = "",
) -> ServiceMapResponse:
    """A project's services, databases, outgoing calls and LLM providers, and who calls whom.

    Raises:
        InvalidKeyError / NotSignedInError (401), MissingScopeError / CsrfError (403),
        InvalidRequestError: bad body or range (400), NotFoundError: project (404),
        StorageUnavailableError (503).
    """
    body = await parse_json_body(request, content_type, ServiceMapRequest, MAX_SEARCH_BODY_BYTES)
    return await map_service.service_map(caller, body)
