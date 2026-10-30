from datetime import UTC, datetime, timedelta

import pytest
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import (
    AnyValue,
    ArrayValue,
    KeyValue,
    KeyValueList,
)
from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord, ResourceLogs, ScopeLogs
from otlp_samples import SAMPLE_TIME_NANOS, make_record, make_request

from spanport_server.core.errors import InvalidRequestError
from spanport_server.core.ids import new_id
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.otlp_log_parser import (
    any_value_to_text,
    decode_logs_request,
    drop_expired,
    level_name,
    to_log_rows,
)

PROJECT = ProjectRef(org_id=new_id(), project_id=new_id())
RECEIVED_AT = datetime(2026, 10, 26, 10, 0, 5, tzinfo=UTC)


def test_converts_a_record_to_a_row_under_the_keys_project() -> None:
    request = make_request(
        make_record(time_unix_nano=SAMPLE_TIME_NANOS, attributes={"user.id": "u-42"})
    )

    [row] = to_log_rows(request, PROJECT, RECEIVED_AT)

    assert row.org_id == PROJECT.org_id
    assert row.project_id == PROJECT.project_id
    assert row.ts == datetime(2026, 10, 26, 10, 0, 0, tzinfo=UTC)
    assert row.service == "hr-portal-api"
    assert row.level == "ERROR"
    assert row.message == "Payment failed for order 1042"
    assert row.trace_id == "0af7651916cd43dd8448eb211c80319c"
    assert row.span_id == "b7ad6b7169203331"
    assert row.attributes == {"user.id": "u-42"}
    assert row.resource_attributes == {"service.name": "hr-portal-api"}


def nanos(moment: datetime) -> int:
    return int(moment.timestamp()) * 1_000_000_000


def test_time_far_in_the_future_is_replaced_by_received_time() -> None:
    two_hours_ahead = make_record(time_unix_nano=nanos(RECEIVED_AT + timedelta(hours=2)))
    thirty_minutes_ahead = make_record(time_unix_nano=nanos(RECEIVED_AT + timedelta(minutes=30)))

    rows = to_log_rows(make_request(two_hours_ahead, thirty_minutes_ahead), PROJECT, RECEIVED_AT)

    assert rows[0].ts == RECEIVED_AT
    assert rows[1].ts == RECEIVED_AT + timedelta(minutes=30)


def test_drop_expired_keeps_only_the_last_seven_days() -> None:
    inside = make_record("inside", time_unix_nano=nanos(RECEIVED_AT - timedelta(days=6)))
    expired = make_record("expired", time_unix_nano=nanos(RECEIVED_AT - timedelta(days=8)))
    rows = to_log_rows(make_request(inside, expired), PROJECT, RECEIVED_AT)

    kept = drop_expired(rows, RECEIVED_AT)

    assert [row.message for row in kept] == ["inside"]


def test_flattens_every_resource_scope_and_record() -> None:
    request = ExportLogsServiceRequest(
        resource_logs=[
            ResourceLogs(
                scope_logs=[
                    ScopeLogs(log_records=[make_record("a"), make_record("b")]),
                    ScopeLogs(log_records=[make_record("c")]),
                ]
            ),
            ResourceLogs(scope_logs=[ScopeLogs(log_records=[make_record("d")])]),
        ]
    )

    rows = to_log_rows(request, PROJECT, RECEIVED_AT)

    assert [row.message for row in rows] == ["a", "b", "c", "d"]
    assert rows[3].service == "unknown_service"


def test_each_row_gets_its_own_time_ordered_log_id() -> None:
    rows = to_log_rows(make_request(make_record(), make_record()), PROJECT, RECEIVED_AT)

    assert rows[0].log_id != rows[1].log_id
    assert rows[0].log_id.version == 7
    assert rows[0].log_id < rows[1].log_id


def test_missing_time_falls_back_to_observed_then_received_time() -> None:
    observed_only = make_record(time_unix_nano=0)
    observed_only.observed_time_unix_nano = SAMPLE_TIME_NANOS
    no_time = make_record(time_unix_nano=0)

    rows = to_log_rows(make_request(observed_only, no_time), PROJECT, RECEIVED_AT)

    assert rows[0].ts == datetime(2026, 10, 26, 10, 0, 0, tzinfo=UTC)
    assert rows[1].ts == RECEIVED_AT
    assert rows[1].observed_ts == RECEIVED_AT


@pytest.mark.parametrize(
    ("severity_number", "severity_text", "expected"),
    [
        (1, "", "TRACE"),
        (4, "", "TRACE"),
        (5, "", "DEBUG"),
        (9, "", "INFO"),
        (13, "WARNING", "WARN"),
        (17, "", "ERROR"),
        (20, "", "ERROR"),
        (21, "", "FATAL"),
        (24, "", "FATAL"),
        (0, "warning", "WARNING"),
        (0, "", "UNSPECIFIED"),
        (25, "", "UNSPECIFIED"),
    ],
)
def test_level_comes_from_severity_number_then_text(
    severity_number: int, severity_text: str, expected: str
) -> None:
    assert level_name(severity_number, severity_text) == expected


def test_non_string_bodies_become_json_text() -> None:
    nested = AnyValue(
        kvlist_value=KeyValueList(
            values=[
                KeyValue(key="order", value=AnyValue(int_value=1042)),
                KeyValue(
                    key="tags",
                    value=AnyValue(
                        array_value=ArrayValue(
                            values=[AnyValue(string_value="a"), AnyValue(bool_value=True)]
                        )
                    ),
                ),
            ]
        )
    )

    assert any_value_to_text(nested) == '{"order": 1042, "tags": ["a", true]}'
    assert any_value_to_text(AnyValue(double_value=1.5)) == "1.5"
    assert any_value_to_text(AnyValue(bytes_value=b"\x01\xff")) == '"01ff"'
    assert any_value_to_text(AnyValue()) == ""


def test_decodes_a_valid_request() -> None:
    payload = make_request(make_record()).SerializeToString()

    assert len(decode_logs_request(payload).resource_logs) == 1


def test_rejects_bytes_that_are_not_a_logs_request() -> None:
    with pytest.raises(InvalidRequestError):
        decode_logs_request(b"\xff\xff\xff not protobuf")


def test_empty_request_gives_no_rows() -> None:
    assert to_log_rows(ExportLogsServiceRequest(), PROJECT, RECEIVED_AT) == []


def test_empty_record_still_becomes_a_row() -> None:
    [row] = to_log_rows(make_request(LogRecord()), PROJECT, RECEIVED_AT)

    assert row.message == ""
    assert row.trace_id == ""
    assert row.level == "UNSPECIFIED"
