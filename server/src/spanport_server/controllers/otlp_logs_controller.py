"""POST /v1/logs: OTLP/HTTP logs from the collector.

Checks run in this order, so unauthenticated requests never reach the parser:
key → content type → body size → bounded gzip decompression → protobuf decode.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceResponse

from spanport_server.core.compression import decode_otlp_body
from spanport_server.core.constants import (
    MAX_INGEST_BODY_BYTES,
    OTLP_LOGS_PATH,
    PROTOBUF_CONTENT_TYPE,
)
from spanport_server.core.errors import UnsupportedMediaTypeError
from spanport_server.core.request_body import media_type, read_body_capped
from spanport_server.dependencies import get_log_ingest_service, require_data_key
from spanport_server.schemas.api_key import ApiKeyRecord
from spanport_server.services.log_ingest_service import LogIngestService

router = APIRouter()


@router.post(OTLP_LOGS_PATH)
async def export_logs(
    request: Request,
    key: Annotated[ApiKeyRecord, Depends(require_data_key)],
    ingest_service: Annotated[LogIngestService, Depends(get_log_ingest_service)],
    content_type: Annotated[str, Header()] = "",
    content_encoding: Annotated[str, Header()] = "",
) -> Response:
    """Store a batch of OTLP logs under the data key's project.

    Returns:
        An empty OTLP ExportLogsServiceResponse (protobuf).

    Raises:
        UnsupportedMediaTypeError: Not protobuf, or an encoding other than gzip.
        PayloadTooLargeError: Over 10 MB sent or 50 MB after decompression.
        InvalidRequestError: Not valid gzip or not a valid OTLP request.
        StorageUnavailableError: ClickHouse is down; the collector retries.
    """
    if media_type(content_type) != PROTOBUF_CONTENT_TYPE:
        raise UnsupportedMediaTypeError(f"Send OTLP logs as {PROTOBUF_CONTENT_TYPE}.")
    body = await read_body_capped(request, MAX_INGEST_BODY_BYTES)
    await ingest_service.ingest(key, decode_otlp_body(body, content_encoding))
    return Response(
        ExportLogsServiceResponse().SerializeToString(), media_type=PROTOBUF_CONTENT_TYPE
    )
