"""POST /v1/traces: OTLP/HTTP traces (spans) from the collector.

The same checks as /v1/logs, in the same order, so unauthenticated requests never reach the
parser: key → content type → body size → bounded gzip decompression → protobuf decode.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceResponse

from spanport_server.core.compression import decode_otlp_body
from spanport_server.core.constants import (
    MAX_INGEST_BODY_BYTES,
    OTLP_TRACES_PATH,
    PROTOBUF_CONTENT_TYPE,
)
from spanport_server.core.errors import UnsupportedMediaTypeError
from spanport_server.core.request_body import media_type, read_body_capped
from spanport_server.dependencies import get_span_ingest_service, require_data_key
from spanport_server.schemas.api_key import ApiKeyRecord
from spanport_server.services.span_ingest_service import SpanIngestService

router = APIRouter()


@router.post(OTLP_TRACES_PATH)
async def export_traces(
    request: Request,
    key: Annotated[ApiKeyRecord, Depends(require_data_key)],
    ingest_service: Annotated[SpanIngestService, Depends(get_span_ingest_service)],
    content_type: Annotated[str, Header()] = "",
    content_encoding: Annotated[str, Header()] = "",
) -> Response:
    """Store a batch of OTLP spans under the data key's project.

    Returns:
        An empty OTLP ExportTraceServiceResponse (protobuf).

    Raises:
        UnsupportedMediaTypeError: Not protobuf, or an encoding other than gzip.
        PayloadTooLargeError: Over 10 MB sent or 50 MB after decompression.
        InvalidRequestError: Not valid gzip or not a valid OTLP request.
        StorageUnavailableError: ClickHouse is down; the collector retries.
    """
    if media_type(content_type) != PROTOBUF_CONTENT_TYPE:
        raise UnsupportedMediaTypeError(f"Send OTLP traces as {PROTOBUF_CONTENT_TYPE}.")
    body = await read_body_capped(request, MAX_INGEST_BODY_BYTES)
    await ingest_service.ingest(key, decode_otlp_body(body, content_encoding))
    return Response(
        ExportTraceServiceResponse().SerializeToString(), media_type=PROTOBUF_CONTENT_TYPE
    )
