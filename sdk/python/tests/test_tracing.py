import asyncio
from collections.abc import Iterator

import pytest
import requests
from conftest import VALID_KEY, FakeSpanport
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

import spanport
from spanport._spans import use_tracer_provider
from spanport._tracing import ActiveTracing, start_tracing


class Tracing:
    """Tracing into memory, as init() would start it."""

    def __init__(self) -> None:
        self.exporter = InMemorySpanExporter()
        self.active: ActiveTracing = start_tracing("orders-api", self.exporter)
        use_tracer_provider(self.active.provider)

    def finished(self) -> dict[str, ReadableSpan]:
        self.active.provider.force_flush()
        return {span.name: span for span in self.exporter.get_finished_spans()}


@pytest.fixture
def tracing() -> Iterator[Tracing]:
    running = Tracing()
    yield running
    use_tracer_provider(None)
    running.active.stop()


def parent_of(span: ReadableSpan) -> int | None:
    return span.parent.span_id if span.parent else None


def test_span_blocks_nest_under_the_current_one(tracing: Tracing) -> None:
    with spanport.span("handle request"), spanport.span("load user"):
        pass

    spans = tracing.finished()
    root = spans["handle request"]
    assert parent_of(spans["load user"]) == root.context.span_id
    assert root.resource.attributes["service.name"] == "orders-api"


def test_a_failed_step_is_marked_and_the_error_re_raised(tracing: Tracing) -> None:
    with pytest.raises(ValueError, match="payment declined"), spanport.span("charge card"):
        raise ValueError("payment declined")

    failed = tracing.finished()["charge card"]
    assert failed.status.status_code is StatusCode.ERROR
    assert failed.events[0].name == "exception"


def test_trace_times_functions_and_every_method_of_a_class(tracing: Tracing) -> None:
    @spanport.trace()
    def score(text: str) -> int:
        return len(text)

    @spanport.trace()
    class VariablesService:
        def __init__(self, prefix: str) -> None:
            self.prefix = prefix

        def list(self) -> list[str]:
            return [f"{self.prefix}-a"]

        async def find(self, variable_id: str) -> str:
            await asyncio.sleep(0)
            return f"{self.prefix}-{variable_id}"

    service = VariablesService("var")
    assert score("abc") == 3
    assert service.list() == ["var-a"]
    assert asyncio.run(service.find("7")) == "var-7"
    assert VariablesService.find.__name__ == "find"

    names = set(tracing.finished())
    assert {
        "test_trace_times_functions_and_every_method_of_a_class.<locals>.score",
        "VariablesService.list",
        "VariablesService.find",
    } <= names
    assert "VariablesService.__init__" not in names


def test_outgoing_requests_are_timed_and_carry_traceparent(
    tracing: Tracing, fake_spanport: FakeSpanport
) -> None:
    assert "opentelemetry.instrumentation.requests" in tracing.active.optional

    with spanport.span("checkout"):
        requests.get(f"{fake_spanport.url}/billing", timeout=5)

    spans = tracing.finished()
    checkout = spans["checkout"]
    [call] = [span for span in spans.values() if span.kind is SpanKind.CLIENT]
    assert parent_of(call) == checkout.context.span_id
    [received] = [request for request in fake_spanport.requests if request.path == "/billing"]
    trace_id = format(checkout.context.trace_id, "032x")
    assert (received.traceparent or "").startswith(f"00-{trace_id}-")


def test_init_sends_traces_with_the_data_key_but_never_its_own_calls(
    fake_spanport: FakeSpanport,
) -> None:
    spanport.init(VALID_KEY, "orders-api", fake_spanport.url, fake_spanport.url, check_key=False)
    with spanport.span("checkout"):
        pass
    spanport.shutdown()

    posts = [request for request in fake_spanport.requests if request.path == "/v1/traces"]
    assert posts
    assert all(post.authorization == f"Bearer {VALID_KEY}" for post in posts)
    names = [
        span.name
        for post in posts
        for resource in ExportTraceServiceRequest.FromString(post.body).resource_spans
        for scope in resource.scope_spans
        for span in scope.spans
    ]
    assert names == ["checkout"]


def test_traces_false_sends_none_and_init_works_again_after_shutdown(
    fake_spanport: FakeSpanport,
) -> None:
    spanport.init(VALID_KEY, "svc", fake_spanport.url, fake_spanport.url, False, traces=False)
    with spanport.span("not sent"):
        pass
    spanport.shutdown()
    assert not [request for request in fake_spanport.requests if request.path == "/v1/traces"]

    spanport.init(VALID_KEY, "svc", fake_spanport.url, fake_spanport.url, check_key=False)
    with spanport.span("sent after restart"):
        pass
    spanport.shutdown()
    assert [request for request in fake_spanport.requests if request.path == "/v1/traces"]
