"""Builders for OTLP logs and traces requests used across tests."""

import time
from collections.abc import Mapping

from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord, ResourceLogs, ScopeLogs
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span, Status

# 2026-10-26T10:00:00Z
SAMPLE_TIME_NANOS = 1_793_008_800_000_000_000


def make_record(
    body: str = "Payment failed for order 1042",
    severity_number: int = 17,
    time_unix_nano: int | None = None,
    attributes: dict[str, str] | None = None,
) -> LogRecord:
    # Default to now, so ingest tests never fall outside the 7-day retention.
    return LogRecord(
        time_unix_nano=time.time_ns() if time_unix_nano is None else time_unix_nano,
        severity_number=severity_number,  # type: ignore[arg-type]
        body=AnyValue(string_value=body),
        attributes=[
            KeyValue(key=key, value=AnyValue(string_value=value))
            for key, value in (attributes or {}).items()
        ],
        trace_id=bytes.fromhex("0af7651916cd43dd8448eb211c80319c"),
        span_id=bytes.fromhex("b7ad6b7169203331"),
    )


def make_request(*records: LogRecord, service: str = "hr-portal-api") -> ExportLogsServiceRequest:
    resource = Resource(
        attributes=[KeyValue(key="service.name", value=AnyValue(string_value=service))]
    )
    return ExportLogsServiceRequest(
        resource_logs=[
            ResourceLogs(resource=resource, scope_logs=[ScopeLogs(log_records=list(records))])
        ]
    )


def make_span(
    name: str = "GET /users/:id",
    kind: int = Span.SPAN_KIND_SERVER,
    duration_ms: int = 42,
    attributes: Mapping[str, str | int] | None = None,
    status_code: int = Status.STATUS_CODE_UNSET,
    start_unix_nano: int | None = None,
) -> Span:
    # Default to now, so ingest tests never fall outside the 30-day retention.
    start = time.time_ns() if start_unix_nano is None else start_unix_nano
    return Span(
        trace_id=bytes.fromhex("0af7651916cd43dd8448eb211c80319c"),
        span_id=bytes.fromhex("b7ad6b7169203331"),
        parent_span_id=bytes.fromhex("00f067aa0ba902b7"),
        name=name,
        kind=kind,  # type: ignore[arg-type]
        start_time_unix_nano=start,
        end_time_unix_nano=start + duration_ms * 1_000_000,
        attributes=[
            KeyValue(
                key=key,
                value=AnyValue(int_value=value)
                if isinstance(value, int)
                else AnyValue(string_value=value),
            )
            for key, value in (attributes or {}).items()
        ],
        status=Status(code=status_code),  # type: ignore[arg-type]
    )


def make_trace_request(*spans: Span, service: str = "hr-portal-api") -> ExportTraceServiceRequest:
    resource = Resource(
        attributes=[KeyValue(key="service.name", value=AnyValue(string_value=service))]
    )
    return ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(resource=resource, scope_spans=[ScopeSpans(spans=list(spans))])
        ]
    )
