import gzip
from collections.abc import AsyncIterator

import httpx
import pytest
from fakes import SAMPLE_DATA_KEY, FakeApiKeyStore, FakeSpanWriter
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceResponse
from otlp_samples import make_span, make_trace_request

from spanport_server.dependencies import get_api_key_auth_service, get_span_ingest_service
from spanport_server.main import create_app
from spanport_server.services.api_key_auth_service import ApiKeyAuthService
from spanport_server.services.span_ingest_service import SpanIngestService

pytestmark = pytest.mark.anyio

PROTOBUF_HEADERS = {
    "Authorization": f"Bearer {SAMPLE_DATA_KEY}",
    "Content-Type": "application/x-protobuf",
}
VALID_PAYLOAD = make_trace_request(make_span(), make_span(name="SELECT users")).SerializeToString()


@pytest.fixture
def writer() -> FakeSpanWriter:
    return FakeSpanWriter()


@pytest.fixture
async def client(writer: FakeSpanWriter) -> AsyncIterator[httpx.AsyncClient]:
    keys = FakeApiKeyStore()
    keys.add_key(SAMPLE_DATA_KEY)
    app = create_app()
    app.dependency_overrides[get_api_key_auth_service] = lambda: ApiKeyAuthService(keys)
    app.dependency_overrides[get_span_ingest_service] = lambda: SpanIngestService(writer)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


async def test_stores_spans_under_the_keys_project(
    client: httpx.AsyncClient, writer: FakeSpanWriter
) -> None:
    response = await client.post(
        "/v1/traces",
        content=gzip.compress(VALID_PAYLOAD),
        headers={**PROTOBUF_HEADERS, "Content-Encoding": "gzip"},
    )

    assert response.status_code == 200
    ExportTraceServiceResponse.FromString(response.content)
    assert [row.name for row in writer.rows] == ["GET /users/:id", "SELECT users"]


async def test_an_unknown_key_never_reaches_the_parser(
    client: httpx.AsyncClient, writer: FakeSpanWriter
) -> None:
    headers = {**PROTOBUF_HEADERS, "Authorization": "Bearer sp_ingest_wrong"}

    response = await client.post("/v1/traces", content=b"garbage", headers=headers)

    assert response.status_code == 401
    assert writer.rows == []


async def test_json_is_refused_like_for_logs(client: httpx.AsyncClient) -> None:
    headers = {**PROTOBUF_HEADERS, "Content-Type": "application/json"}

    response = await client.post("/v1/traces", content=b"{}", headers=headers)

    assert response.status_code == 415


async def test_storage_down_is_a_503_so_the_collector_retries() -> None:
    keys = FakeApiKeyStore()
    keys.add_key(SAMPLE_DATA_KEY)
    app = create_app()
    app.dependency_overrides[get_api_key_auth_service] = lambda: ApiKeyAuthService(keys)
    app.dependency_overrides[get_span_ingest_service] = lambda: SpanIngestService(
        FakeSpanWriter(storage_down=True)
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/traces", content=VALID_PAYLOAD, headers=PROTOBUF_HEADERS)

    assert response.status_code == 503
