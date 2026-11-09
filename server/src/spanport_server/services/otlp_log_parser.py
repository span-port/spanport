"""Turns an OTLP logs request (protobuf) into rows for the logs table."""

import json
from datetime import UTC, datetime

from google.protobuf.message import DecodeError
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord

from spanport_server.core.constants import (
    LOG_LEVELS,
    LOG_RETENTION,
    MAX_ATTRIBUTE_KEY_LENGTH,
    MAX_FUTURE_LOG_SKEW,
    MAX_LEVEL_TEXT_LENGTH,
    MAX_SERVICE_NAME_LENGTH,
    MAX_SEVERITY_NUMBER,
    NANOS_PER_SECOND,
    SERVICE_NAME_ATTRIBUTE,
    SEVERITY_NUMBERS_PER_LEVEL,
    UNKNOWN_SERVICE_NAME,
    UNSPECIFIED_LOG_LEVEL,
)
from spanport_server.core.errors import InvalidRequestError
from spanport_server.core.ids import new_id
from spanport_server.schemas.log_row import LogRow
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.otlp_record_count import check_record_count


def decode_logs_request(payload: bytes) -> ExportLogsServiceRequest:
    """Decode an OTLP ExportLogsServiceRequest.

    Raises:
        InvalidRequestError: The bytes are not a valid request.
    """
    request = ExportLogsServiceRequest()
    try:
        request.ParseFromString(payload)
    except DecodeError as error:
        raise InvalidRequestError("The body is not a valid OTLP logs request.") from error
    return request


def build_log_rows(payload: bytes, project: ProjectRef, received_at: datetime) -> list[LogRow]:
    """Check the record count, decode the request and flatten it into rows.

    CPU-bound: the ingest service runs it in a worker thread.

    Raises:
        PayloadTooLargeError: More than MAX_INGEST_RECORDS records.
        InvalidRequestError: Not a valid OTLP logs request.
    """
    check_record_count(payload)
    return to_log_rows(decode_logs_request(payload), project, received_at)


def to_log_rows(
    request: ExportLogsServiceRequest, project: ProjectRef, received_at: datetime
) -> list[LogRow]:
    """Flatten a request into one row per log record.

    Args:
        request: The decoded request.
        project: Where the rows belong; taken from the data key, never from the payload.
        received_at: When the server received the request; used when a record has no time.

    Returns:
        The rows, in request order.
    """
    rows: list[LogRow] = []
    for resource_logs in request.resource_logs:
        resource_attributes = attributes_to_dict(resource_logs.resource.attributes)
        service = service_name(resource_attributes)
        for scope_logs in resource_logs.scope_logs:
            for record in scope_logs.log_records:
                rows.append(to_log_row(record, project, service, resource_attributes, received_at))
    return rows


def to_log_row(
    record: LogRecord,
    project: ProjectRef,
    service: str,
    resource_attributes: dict[str, str],
    received_at: datetime,
) -> LogRow:
    """Convert one OTLP log record to a row."""
    observed_ts = not_in_future(
        timestamp_or(record.observed_time_unix_nano, received_at), received_at
    )
    return LogRow(
        org_id=project.org_id,
        project_id=project.project_id,
        log_id=new_id(),
        ts=event_time(record.time_unix_nano, observed_ts, received_at),
        observed_ts=observed_ts,
        service=service,
        level=level_name(record.severity_number, record.severity_text),
        severity_number=min(max(record.severity_number, 0), MAX_SEVERITY_NUMBER),
        message=any_value_to_text(record.body),
        trace_id=record.trace_id.hex(),
        span_id=record.span_id.hex(),
        attributes=attributes_to_dict(record.attributes),
        resource_attributes=resource_attributes,
    )


def service_name(resource_attributes: dict[str, str]) -> str:
    """The resource's service.name, cut to MAX_SERVICE_NAME_LENGTH, or "unknown_service"."""
    service = resource_attributes.get(SERVICE_NAME_ATTRIBUTE, UNKNOWN_SERVICE_NAME)
    return service[:MAX_SERVICE_NAME_LENGTH]


def timestamp_or(unix_nanos: int, fallback: datetime) -> datetime:
    """Convert OTLP nanoseconds since 1970 to a UTC datetime; 0 means unset."""
    if unix_nanos == 0:
        return fallback
    return datetime.fromtimestamp(unix_nanos / NANOS_PER_SECOND, UTC)


def event_time(time_unix_nano: int, observed_ts: datetime, received_at: datetime) -> datetime:
    """When the log happened: the record's time, else when it was observed.

    A time more than MAX_FUTURE_LOG_SKEW ahead means the sender's clock is wrong, so the time the
    server received it is used instead.
    """
    return not_in_future(timestamp_or(time_unix_nano, observed_ts), received_at)


def not_in_future(ts: datetime, received_at: datetime) -> datetime:
    """`ts`, or `received_at` when `ts` is more than MAX_FUTURE_LOG_SKEW ahead of it.

    Besides a wrong clock, this keeps times past what storage can hold (year 2262) out of a batch.
    """
    if ts > received_at + MAX_FUTURE_LOG_SKEW:
        return received_at
    return ts


def drop_expired(rows: list[LogRow], received_at: datetime) -> list[LogRow]:
    """Keep only rows inside the retention window.

    Older rows would be deleted by the TTL anyway, and a batch spread over many old days can make
    ClickHouse reject the whole insert (too many partitions), losing the valid rows with it.
    """
    oldest_kept = received_at - LOG_RETENTION
    return [row for row in rows if row.ts >= oldest_kept]


def level_name(severity_number: int, severity_text: str) -> str:
    """Name the level from the OTLP severity number, or the sender's text if it has none."""
    if 0 < severity_number <= len(LOG_LEVELS) * SEVERITY_NUMBERS_PER_LEVEL:
        return LOG_LEVELS[(severity_number - 1) // SEVERITY_NUMBERS_PER_LEVEL]
    return severity_text[:MAX_LEVEL_TEXT_LENGTH].upper() or UNSPECIFIED_LOG_LEVEL


def attributes_to_dict(attributes: list[KeyValue]) -> dict[str, str]:
    """Convert OTLP attributes to a flat string map, keys cut to MAX_ATTRIBUTE_KEY_LENGTH."""
    return {
        attribute.key[:MAX_ATTRIBUTE_KEY_LENGTH]: any_value_to_text(attribute.value)
        for attribute in attributes
    }


def any_value_to_text(value: AnyValue) -> str:
    """Render an OTLP value as text: strings as-is, everything else as JSON."""
    if value.WhichOneof("value") == "string_value":
        return value.string_value
    json_value = any_value_to_json(value)
    return "" if json_value is None else json.dumps(json_value)


def any_value_to_json(value: AnyValue) -> object:
    """Convert an OTLP value, including nested arrays and maps, to plain Python."""
    match value.WhichOneof("value"):
        case "string_value":
            return value.string_value
        case "bool_value":
            return value.bool_value
        case "int_value":
            return value.int_value
        case "double_value":
            return value.double_value
        case "bytes_value":
            return value.bytes_value.hex()
        case "array_value":
            return [any_value_to_json(item) for item in value.array_value.values]
        case "kvlist_value":
            return {item.key: any_value_to_json(item.value) for item in value.kvlist_value.values}
    return None
