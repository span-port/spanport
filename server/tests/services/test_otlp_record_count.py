import time

import pytest
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord, ResourceLogs, ScopeLogs
from otlp_samples import make_record, make_request, make_span, make_trace_request

from spanport_server.core.errors import InvalidRequestError, PayloadTooLargeError
from spanport_server.services.otlp_record_count import check_record_count, count_records

RECORD_PATH = (1, 2, 2)


def empty_records_request(count: int) -> bytes:
    # The attack shape: records with no fields at all, two bytes each on the wire.
    scope = ScopeLogs(log_records=[LogRecord() for _ in range(count)])
    request = ExportLogsServiceRequest(resource_logs=[ResourceLogs(scope_logs=[scope])])
    return bytes(request.SerializeToString())


def length_delimited(key: int, content: bytes) -> bytes:
    length = len(content)
    varint = bytearray()
    while length >= 0x80:
        varint.append((length & 0x7F) | 0x80)
        length >>= 7
    varint.append(length)
    return bytes([key]) + bytes(varint) + content


def test_counts_records_across_resources_and_scopes() -> None:
    request = make_request(make_record("a"), make_record("b"))
    request.resource_logs.append(
        ResourceLogs(scope_logs=[ScopeLogs(log_records=[make_record("c")]), ScopeLogs()])
    )

    assert count_records(request.SerializeToString(), RECORD_PATH, limit=100) == 3


def test_counts_spans_the_same_way() -> None:
    payload = make_trace_request(make_span(), make_span(), make_span()).SerializeToString()

    assert count_records(payload, RECORD_PATH, limit=100) == 3


def test_empty_request_has_no_records() -> None:
    assert count_records(b"", RECORD_PATH, limit=100) == 0


def test_stops_counting_once_past_the_limit() -> None:
    payload = empty_records_request(1_000)

    assert count_records(payload, RECORD_PATH, limit=10) == 11


def test_a_request_at_the_limit_is_accepted() -> None:
    check_record_count(empty_records_request(5_000))


def test_a_request_over_the_limit_is_refused() -> None:
    with pytest.raises(PayloadTooLargeError, match="at most 5,000"):
        check_record_count(empty_records_request(5_001))


def test_millions_of_empty_records_are_refused_quickly() -> None:
    # 10 MB of empty records: about 5 million, which decoding would turn into gigabytes.
    scope_logs = b"\x12\x00" * 5_000_000
    payload = length_delimited(0x0A, length_delimited(0x12, scope_logs))
    started = time.perf_counter()

    with pytest.raises(PayloadTooLargeError):
        check_record_count(payload)

    assert time.perf_counter() - started < 1


@pytest.mark.parametrize(
    "payload",
    [b"\x0a\x05\x12", b"\x0a", b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff", b"\x0b"],
    ids=["length-past-end", "missing-length", "endless-varint", "group-wire-type"],
)
def test_bytes_that_are_not_protobuf_are_refused(payload: bytes) -> None:
    with pytest.raises(InvalidRequestError):
        count_records(payload, RECORD_PATH, limit=100)


def test_unknown_fields_of_every_wire_type_are_skipped() -> None:
    unknown_fields = b"\x10\x96\x01" + b"\x19" + bytes(8) + b"\x25" + bytes(4) + b"\x2a\x01x"
    payload = unknown_fields + make_request(make_record(), make_record()).SerializeToString()

    assert count_records(payload, RECORD_PATH, limit=100) == 2
