"""Turns an OTLP traces request (protobuf) into rows for the spans table, each labelled with
what it was (TRD "Span classification")."""

from collections.abc import Iterable
from datetime import datetime, timedelta

from google.protobuf.message import DecodeError
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.trace.v1.trace_pb2 import Span, Status

from spanport_server.core.constants import (
    DB_SYSTEM_ATTRIBUTE,
    GEN_AI_ATTRIBUTE_PREFIX,
    HTTP_METHOD_ATTRIBUTES,
    HTTP_ROUTE_ATTRIBUTES,
    HTTP_STATUS_ATTRIBUTES,
    INCOMING_SPAN_KINDS,
    NANOS_PER_MICROSECOND,
    OUTGOING_SPAN_KINDS,
    SERVICE_NAME_ATTRIBUTE,
    SPAN_CATEGORY_CLIENT,
    SPAN_CATEGORY_CODE,
    SPAN_CATEGORY_DB,
    SPAN_CATEGORY_INCOMING,
    SPAN_CATEGORY_LLM,
    SPAN_KIND_PREFIX,
    SPAN_KIND_UNSPECIFIED,
    SPAN_RETENTION,
    SPAN_STATUS_UNSET,
    STATUS_CODE_PREFIX,
    UNKNOWN_SERVICE_NAME,
)
from spanport_server.core.errors import InvalidRequestError
from spanport_server.schemas.span_row import SpanRow
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.otlp_log_parser import attributes_to_dict, event_time


def decode_traces_request(payload: bytes) -> ExportTraceServiceRequest:
    """Decode an OTLP ExportTraceServiceRequest.

    Raises:
        InvalidRequestError: The bytes are not a valid request.
    """
    request = ExportTraceServiceRequest()
    try:
        request.ParseFromString(payload)
    except DecodeError as error:
        raise InvalidRequestError("The body is not a valid OTLP traces request.") from error
    return request


def to_span_rows(
    request: ExportTraceServiceRequest, project: ProjectRef, received_at: datetime
) -> list[SpanRow]:
    """Flatten a request into one row per span.

    Args:
        request: The decoded request.
        project: Where the rows belong; taken from the data key, never from the payload.
        received_at: When the server received it; a span stamped far in the future gets this.
    """
    rows: list[SpanRow] = []
    for resource_spans in request.resource_spans:
        resource_attributes = attributes_to_dict(resource_spans.resource.attributes)
        service = resource_attributes.get(SERVICE_NAME_ATTRIBUTE, UNKNOWN_SERVICE_NAME)
        for scope_spans in resource_spans.scope_spans:
            for span in scope_spans.spans:
                rows.append(to_span_row(span, project, service, resource_attributes, received_at))
    return rows


def to_span_row(
    span: Span,
    project: ProjectRef,
    service: str,
    resource_attributes: dict[str, str],
    received_at: datetime,
) -> SpanRow:
    """Convert one OTLP span to a row, with its category and HTTP fields."""
    attributes = attributes_to_dict(span.attributes)
    kind = kind_name(span.kind)
    start_ts = event_time(span.start_time_unix_nano, received_at, received_at)
    duration_ns = max(0, span.end_time_unix_nano - span.start_time_unix_nano)
    return SpanRow(
        org_id=project.org_id,
        project_id=project.project_id,
        trace_id=span.trace_id.hex(),
        span_id=span.span_id.hex(),
        parent_span_id=span.parent_span_id.hex(),
        service=service,
        name=span.name,
        kind=kind,
        category=span_category(kind, attributes),
        start_ts=start_ts,
        end_ts=start_ts + timedelta(microseconds=duration_ns / NANOS_PER_MICROSECOND),
        duration_ns=duration_ns,
        status_code=status_name(span.status.code),
        status_message=span.status.message,
        http_method=first_of(attributes, HTTP_METHOD_ATTRIBUTES).upper(),
        http_route=first_of(attributes, HTTP_ROUTE_ATTRIBUTES),
        http_status=http_status(attributes),
        attributes=attributes,
        resource_attributes=resource_attributes,
    )


def span_category(kind: str, attributes: dict[str, str]) -> str:
    """What the span was; the first rule that matches wins: LLM, DB, outgoing call, incoming
    request, else your own code.
    """
    if any(key.startswith(GEN_AI_ATTRIBUTE_PREFIX) for key in attributes):
        return SPAN_CATEGORY_LLM
    if DB_SYSTEM_ATTRIBUTE in attributes:
        return SPAN_CATEGORY_DB
    if kind in OUTGOING_SPAN_KINDS:
        return SPAN_CATEGORY_CLIENT
    if kind in INCOMING_SPAN_KINDS:
        return SPAN_CATEGORY_INCOMING
    return SPAN_CATEGORY_CODE


def kind_name(value: int) -> str:
    """The span kind's name, e.g. 2 → "SERVER"; a value newer than our protobufs is UNSPECIFIED."""
    try:
        return str(Span.SpanKind.Name(value)).removeprefix(SPAN_KIND_PREFIX)
    except ValueError:
        return SPAN_KIND_UNSPECIFIED


def status_name(value: int) -> str:
    """The status code's name, e.g. 2 → "ERROR"; an unknown value is UNSET."""
    try:
        return str(Status.StatusCode.Name(value)).removeprefix(STATUS_CODE_PREFIX)
    except ValueError:
        return SPAN_STATUS_UNSET


def first_of(attributes: dict[str, str], names: Iterable[str]) -> str:
    """The first of `names` the span has, or ""."""
    return next((attributes[name] for name in names if name in attributes), "")


def http_status(attributes: dict[str, str]) -> int:
    """The HTTP status code as a number, or 0 when absent or not a number."""
    value = first_of(attributes, HTTP_STATUS_ATTRIBUTES)
    return int(value) if value.isdigit() else 0


def drop_expired_spans(rows: list[SpanRow], received_at: datetime) -> list[SpanRow]:
    """Keep only spans inside the retention window (older ones would be deleted anyway, and
    many old days in one batch can make ClickHouse reject the whole insert)."""
    oldest_kept = received_at - SPAN_RETENTION
    return [row for row in rows if row.start_ts >= oldest_kept]
