"""POST /api/v1/logs/export: the current log search as a downloadable CSV or NDJSON file.

The caller, the body, the role and the size are checked before streaming starts, so problems
are normal problem+json responses. The body is the search body plus `format`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse

from spanport_server.core.constants import (
    CONTENT_DISPOSITION_HEADER,
    LOG_EXPORT_PATH,
    MAX_SEARCH_BODY_BYTES,
)
from spanport_server.core.request_body import parse_json_body
from spanport_server.dependencies import get_log_export_service, require_logs_reader
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.log_search import LogExportRequest
from spanport_server.services.log_export_service import LogExportService

router = APIRouter()


@router.post(LOG_EXPORT_PATH)
async def export_logs(
    request: Request,
    caller: Annotated[Caller, Depends(require_logs_reader)],
    export_service: Annotated[LogExportService, Depends(get_log_export_service)],
    content_type: Annotated[str, Header()] = "",
) -> StreamingResponse:
    """Stream the matching logs as a file, newest first.

    Returns:
        The file, with Content-Disposition naming it.

    Raises:
        InvalidKeyError / NotSignedInError (401), MissingScopeError / CsrfError (403),
        NotAllowedError: a viewer (403), NotFoundError: project (404),
        InvalidRequestError: bad body or more than 100,000 matching lines (400),
        StorageUnavailableError (503).
    """
    body = await parse_json_body(request, content_type, LogExportRequest, MAX_SEARCH_BODY_BYTES)
    export = await export_service.prepare(caller, body)
    return StreamingResponse(
        export_service.lines(export),
        media_type=export.content_type,
        headers={CONTENT_DISPOSITION_HEADER: f'attachment; filename="{export.file_name}"'},
    )
