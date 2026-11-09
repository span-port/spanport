from datetime import UTC, datetime, timedelta

import pytest
from opentelemetry.proto.trace.v1.trace_pb2 import Span, Status
from otlp_samples import make_span, make_trace_request

from spanport_server.core.errors import InvalidRequestError, PayloadTooLargeError
from spanport_server.core.ids import new_id
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.otlp_span_parser import (
    build_span_rows,
    decode_traces_request,
    drop_expired_spans,
    http_status,
    route_from_path,
    span_category,
    to_span_rows,
)

PROJECT = ProjectRef(org_id=new_id(), project_id=new_id())
NOW = datetime.now(UTC)


def parse_one(span: Span) -> dict[str, object]:
    (row,) = to_span_rows(make_trace_request(span), PROJECT, NOW)
    return row.__dict__


def test_an_incoming_request_keeps_its_route_status_and_exact_duration() -> None:
    row = parse_one(
        make_span(
            duration_ms=885,
            attributes={
                "http.request.method": "get",
                "http.route": "/api/environments/:id",
                "http.response.status_code": 500,
            },
            status_code=Status.STATUS_CODE_ERROR,
        )
    )

    assert row["category"] == "incoming_request"
    assert row["kind"] == "SERVER"
    assert (row["http_method"], row["http_route"], row["http_status"]) == (
        "GET",
        "/api/environments/:id",
        500,
    )
    assert row["status_code"] == "ERROR"
    assert row["duration_ns"] == 885_000_000
    assert row["service"] == "hr-portal-api"
    assert row["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
    assert row["parent_span_id"] == "00f067aa0ba902b7"
    assert (row["org_id"], row["project_id"]) == (PROJECT.org_id, PROJECT.project_id)


def test_older_http_attribute_names_are_read_too() -> None:
    row = parse_one(make_span(attributes={"http.method": "POST", "http.status_code": 201}))

    assert (row["http_method"], row["http_status"]) == ("POST", 201)


def test_without_a_route_the_path_stands_in_with_ids_hidden() -> None:
    row = parse_one(
        make_span(
            attributes={
                "url.path": "/api/environments/64f1c0ffee00000000000001/components/42/variables"
            }
        )
    )
    older = parse_one(make_span(attributes={"http.target": "/users/7?page=2"}))

    assert row["http_route"] == "/api/environments/:id/components/:id/variables"
    assert older["http_route"] == "/users/:id"


@pytest.mark.parametrize(
    ("path", "route"),
    [
        ("/orders/0af76519-16cd-43dd-8448-eb211c80319c", "/orders/:id"),
        ("/files/aB3dE5fG7hJ9kL1mN3pQ5r", "/files/:id"),
        ("/api/v1/health", "/api/v1/health"),
        ("/api/environments/staging", "/api/environments/staging"),
        ("", ""),
    ],
)
def test_route_from_path_hides_only_id_like_parts(path: str, route: str) -> None:
    assert route_from_path(path) == route


@pytest.mark.parametrize(
    ("kind", "attributes", "category"),
    [
        # The first matching rule wins: an LLM call over HTTP is still "llm".
        (Span.SPAN_KIND_CLIENT, {"gen_ai.system": "anthropic"}, "llm"),
        (Span.SPAN_KIND_CLIENT, {"db.system": "postgresql"}, "db"),
        # The current OpenTelemetry name, sent by e.g. @opentelemetry/instrumentation-pg 0.77.
        (Span.SPAN_KIND_CLIENT, {"db.system.name": "postgresql"}, "db"),
        (Span.SPAN_KIND_CLIENT, {"server.address": "s3.amazonaws.com"}, "client"),
        (Span.SPAN_KIND_PRODUCER, {}, "client"),
        (Span.SPAN_KIND_SERVER, {}, "incoming_request"),
        (Span.SPAN_KIND_INTERNAL, {}, "code"),
    ],
)
def test_spans_are_labelled_by_the_trd_rules(
    kind: int, attributes: dict[str, str], category: str
) -> None:
    assert parse_one(make_span(kind=kind, attributes=attributes))["category"] == category


def test_category_rule_order_directly() -> None:
    assert span_category("SERVER", {"db.system": "redis", "gen_ai.system": "openai"}) == "llm"
    assert span_category("INTERNAL", {"db.system": "redis"}) == "db"


def test_a_span_dated_far_in_the_future_gets_the_receive_time() -> None:
    future = int((NOW + timedelta(days=2)).timestamp() * 1_000_000_000)

    row = parse_one(make_span(start_unix_nano=future, duration_ms=10))

    assert row["start_ts"] == NOW
    assert row["end_ts"] == NOW + timedelta(milliseconds=10)


def test_spans_older_than_30_days_are_dropped() -> None:
    old = int((NOW - timedelta(days=31)).timestamp() * 1_000_000_000)
    rows = to_span_rows(
        make_trace_request(make_span(start_unix_nano=old), make_span()), PROJECT, NOW
    )

    assert len(drop_expired_spans(rows, NOW)) == 1


def test_garbage_is_a_clear_error() -> None:
    with pytest.raises(InvalidRequestError, match="traces"):
        decode_traces_request(b"not protobuf \xff\xff")


@pytest.mark.parametrize(
    ("value", "status"),
    [("404", 404), ("999", 999), ("1000", 0), ("٤٠٤", 0), ("²", 0), ("", 0)],
    ids=["normal", "three-digits", "four-digits", "arabic-digits", "superscript", "absent"],
)
def test_http_status_takes_only_up_to_three_ascii_digits(value: str, status: int) -> None:
    assert http_status({"http.response.status_code": value}) == status


def test_a_span_longer_than_a_day_is_stored_as_one_day() -> None:
    span = make_span()
    span.end_time_unix_nano = 2**64 - 1

    row = parse_one(span)

    assert row["duration_ns"] == 24 * 3600 * 1_000_000_000
    assert row["end_ts"] == row["start_ts"] + timedelta(days=1)  # type: ignore[operator]


def test_a_span_that_ends_before_it_starts_takes_no_time() -> None:
    span = make_span()
    span.end_time_unix_nano = span.start_time_unix_nano - 1

    assert parse_one(span)["duration_ns"] == 0


def test_long_names_methods_and_paths_are_cut() -> None:
    long_path = "/v" * 3_000
    row = parse_one(
        make_span(name="n" * 5_000, attributes={"http.method": "x" * 100, "url.path": long_path})
    )

    assert row["name"] == "n" * 1_000
    assert row["http_method"] == "X" * 16
    assert len(str(row["http_route"])) == 2_048


def test_build_span_rows_refuses_more_than_5000_spans() -> None:
    payload = make_trace_request(*[Span() for _ in range(5_001)]).SerializeToString()

    with pytest.raises(PayloadTooLargeError):
        build_span_rows(payload, PROJECT, NOW)
