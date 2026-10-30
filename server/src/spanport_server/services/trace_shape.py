"""Works out one trace's waterfall from its stored spans: offsets from the start, each span's
own time (not covered by its child spans), and service call vs external for client calls.
"""

from collections import defaultdict
from datetime import datetime

from spanport_server.core.constants import (
    INCOMING_SPAN_KINDS,
    NANOS_PER_MICROSECOND,
    NANOS_PER_MILLISECOND,
    SPAN_CATEGORY_CLIENT,
    SPAN_LABEL_EXTERNAL,
    SPAN_LABEL_SERVICE_CALL,
)
from spanport_server.schemas.trace import SpanItem, StoredSpan, TraceDetail


def nanos_between(earlier: datetime, later: datetime) -> int:
    """Nanoseconds from `earlier` to `later` (datetimes carry microseconds)."""
    return round((later - earlier).total_seconds() * 1_000_000) * NANOS_PER_MICROSECOND


def self_nanos(span: StoredSpan, children: list[StoredSpan]) -> int:
    """The span's own time: its duration minus the time covered by at least one child.

    Children may overlap each other (parallel calls) or run past the parent; only the covered
    part of the parent counts, once.
    """
    covered_until = 0
    covered = 0
    intervals = sorted(
        (
            max(0, nanos_between(span.start_ts, child.start_ts)),
            min(span.duration_ns, nanos_between(span.start_ts, child.start_ts) + child.duration_ns),
        )
        for child in children
    )
    for start, end in intervals:
        start = max(start, covered_until)
        if end > start:
            covered += end - start
            covered_until = end
    return max(0, span.duration_ns - covered)


def span_label(span: StoredSpan, children: list[StoredSpan]) -> str:
    """The span's category, with a client call split by who answered it: another of your
    services (a server span joined the trace under it) or something outside.
    """
    if span.category != SPAN_CATEGORY_CLIENT:
        return span.category
    answered_by_you = any(
        child.kind in INCOMING_SPAN_KINDS or child.service != span.service for child in children
    )
    return SPAN_LABEL_SERVICE_CALL if answered_by_you else SPAN_LABEL_EXTERNAL


def build_trace_detail(trace_id: str, spans: list[StoredSpan], truncated: bool) -> TraceDetail:
    """The waterfall for spans that are already ordered by start time (at least one)."""
    children: dict[str, list[StoredSpan]] = defaultdict(list)
    for span in spans:
        children[span.parent_span_id].append(span)
    trace_start = min(span.start_ts for span in spans)
    trace_end_ns = max(
        nanos_between(trace_start, span.start_ts) + span.duration_ns for span in spans
    )
    items = [
        SpanItem(
            span_id=span.span_id,
            parent_span_id=span.parent_span_id,
            service=span.service,
            name=span.name,
            kind=span.kind,
            label=span_label(span, children[span.span_id]),
            start_ts=span.start_ts,
            offset_ms=nanos_between(trace_start, span.start_ts) / NANOS_PER_MILLISECOND,
            duration_ms=span.duration_ns / NANOS_PER_MILLISECOND,
            self_ms=self_nanos(span, children[span.span_id]) / NANOS_PER_MILLISECOND,
            status_code=span.status_code,
            status_message=span.status_message,
            http_method=span.http_method,
            http_route=span.http_route,
            http_status=span.http_status,
            attributes=span.attributes,
        )
        for span in spans
    ]
    return TraceDetail(
        trace_id=trace_id,
        start_ts=trace_start,
        duration_ms=trace_end_ns / NANOS_PER_MILLISECOND,
        spans=items,
        truncated=truncated,
    )
