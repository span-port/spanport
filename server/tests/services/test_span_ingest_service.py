import pytest
from fakes import SAMPLE_DATA_KEY, FakeApiKeyStore, FakeSpanWriter
from opentelemetry.proto.trace.v1.trace_pb2 import Span
from otlp_samples import make_span, make_trace_request

from spanport_server.core.errors import InvalidRequestError, PayloadTooLargeError
from spanport_server.services.span_ingest_service import SpanIngestService

pytestmark = pytest.mark.anyio


async def test_stores_every_span_under_the_keys_project(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    key = FakeApiKeyStore().add_key(SAMPLE_DATA_KEY)
    writer = FakeSpanWriter()
    payload = make_trace_request(make_span(), make_span()).SerializeToString()

    stored = await SpanIngestService(writer).ingest(key, payload)

    assert stored == 2
    assert {(row.org_id, row.project_id) for row in writer.rows} == {(key.org_id, key.project_id)}
    assert "spans ingested" in caplog.text


async def test_more_than_5000_spans_are_refused_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    key = FakeApiKeyStore().add_key(SAMPLE_DATA_KEY)
    writer = FakeSpanWriter()
    payload = make_trace_request(*[Span() for _ in range(5_001)]).SerializeToString()

    with pytest.raises(PayloadTooLargeError):
        await SpanIngestService(writer).ingest(key, payload)

    assert writer.rows == []
    assert len(caplog.records) == 1
    assert "spans rejected" in caplog.text


async def test_a_value_storage_refuses_is_a_bad_request() -> None:
    key = FakeApiKeyStore().add_key(SAMPLE_DATA_KEY)
    payload = make_trace_request(make_span()).SerializeToString()

    with pytest.raises(InvalidRequestError):
        await SpanIngestService(FakeSpanWriter(refuses_values=True)).ingest(key, payload)


async def test_garbage_is_refused() -> None:
    key = FakeApiKeyStore().add_key(SAMPLE_DATA_KEY)

    with pytest.raises(InvalidRequestError):
        await SpanIngestService(FakeSpanWriter()).ingest(key, b"\xff\xff not protobuf")
