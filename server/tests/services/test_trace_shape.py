from datetime import UTC, datetime, timedelta

from spanport_server.schemas.trace import StoredSpan
from spanport_server.services.trace_shape import build_trace_detail, self_nanos, span_label

T0 = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
MS = 1_000_000


def span(
    span_id: str,
    parent: str = "",
    start_ms: int = 0,
    duration_ms: int = 10,
    category: str = "code",
    kind: str = "INTERNAL",
    service: str = "api",
) -> StoredSpan:
    return StoredSpan(
        span_id=span_id,
        parent_span_id=parent,
        service=service,
        name=span_id,
        kind=kind,
        category=category,
        start_ts=T0 + timedelta(milliseconds=start_ms),
        duration_ns=duration_ms * MS,
        status_code="UNSET",
        status_message="",
        http_method="",
        http_route="",
        http_status=0,
        attributes={},
    )


def test_own_time_is_what_no_child_covers_even_when_children_overlap() -> None:
    parent = span("root", duration_ms=100)
    # 10-40 and 30-60 overlap: together they cover 10-60, so 50 ms covered, 50 ms own time.
    children = [span("a", "root", 10, 30), span("b", "root", 30, 30)]

    assert self_nanos(parent, children) == 50 * MS


def test_a_child_running_past_its_parent_only_counts_inside_it() -> None:
    parent = span("root", duration_ms=100)

    assert self_nanos(parent, [span("late", "root", 90, 50)]) == 90 * MS
    assert self_nanos(parent, []) == 100 * MS


def test_client_calls_are_service_calls_only_when_your_service_answered() -> None:
    call = span("call", category="client", kind="CLIENT")
    answered = span("srv", "call", kind="SERVER", service="billing", category="incoming_request")

    assert span_label(call, [answered]) == "service_call"
    assert span_label(call, []) == "external"
    assert span_label(span("q", category="db"), []) == "db"


def test_the_waterfall_has_offsets_total_duration_and_own_times() -> None:
    spans = [
        span("root", duration_ms=885, category="incoming_request", kind="SERVER"),
        span("service", "root", 5, 870),
        span("db", "service", 10, 42, category="db"),
        span("aws", "service", 60, 790, category="client", kind="CLIENT"),
    ]

    detail = build_trace_detail("0af7651916cd43dd8448eb211c80319c", spans, truncated=False)
    by_id = {item.span_id: item for item in detail.spans}

    assert detail.duration_ms == 885
    assert by_id["aws"].offset_ms == 60
    assert by_id["aws"].label == "external"
    assert by_id["service"].self_ms == 870 - 42 - 790
    assert by_id["root"].self_ms == 15
