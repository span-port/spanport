import logging
from collections.abc import Callable, Iterator, Sequence

import pytest
from opentelemetry.sdk._logs import ReadableLogRecord
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.trace import TracerProvider

from spanport._pipeline import build_logging_handler

ExportedLogs = Callable[[], Sequence[ReadableLogRecord]]


@pytest.fixture
def exported_logs() -> Iterator[ExportedLogs]:
    """Attach the SDK pipeline to the root logger; return a function that flushes and lists logs."""
    # OpenTelemetry leaves this test helper's constructor without type hints.
    exporter = InMemoryLogRecordExporter()  # type: ignore[no-untyped-call]
    handler, provider = build_logging_handler("hr-portal-api", exporter)
    root = logging.getLogger()
    root.addHandler(handler)

    def flush_and_list() -> Sequence[ReadableLogRecord]:
        provider.force_flush()
        return exporter.get_finished_logs()

    yield flush_and_list
    root.removeHandler(handler)
    provider.shutdown()


def test_app_log_is_exported_with_service_level_and_extra_fields(
    exported_logs: ExportedLogs,
) -> None:
    logging.getLogger("app.payments").error(
        "Payment failed for order %s", 1042, extra={"order_id": 1042}
    )

    [record] = exported_logs()
    assert record.log_record.body == "Payment failed for order 1042"
    assert record.log_record.severity_text == "ERROR"
    assert record.log_record.attributes is not None
    assert record.log_record.attributes["order_id"] == 1042
    assert record.resource.attributes["service.name"] == "hr-portal-api"


def test_log_inside_a_span_carries_its_trace_and_span_ids(exported_logs: ExportedLogs) -> None:
    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("POST /payments") as span:
        logging.getLogger("app.payments").error("card declined")
        span_context = span.get_span_context()

    [record] = exported_logs()
    assert record.log_record.trace_id == span_context.trace_id
    assert record.log_record.span_id == span_context.span_id


@pytest.mark.parametrize(
    "logger_name",
    ["spanport", "opentelemetry.exporter.otlp", "urllib3.connectionpool", "requests"],
)
def test_sdk_and_export_path_logs_are_never_exported(
    exported_logs: ExportedLogs, logger_name: str
) -> None:
    logging.getLogger(logger_name).error("Failed to export batch")
    logging.getLogger("app").error("real app log")

    assert [record.log_record.body for record in exported_logs()] == ["real app log"]
