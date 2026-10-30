import gzip
from collections.abc import AsyncIterator

import httpx
import pytest
from fakes import SAMPLE_DATA_KEY, FakeApiKeyStore, FakeLogWriter
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceResponse
from otlp_samples import make_record, make_request

from spanport_server.dependencies import get_api_key_auth_service, get_log_ingest_service
from spanport_server.main import create_app
from spanport_server.services.api_key_auth_service import ApiKeyAuthService
from spanport_server.services.log_ingest_service import LogIngestService

pytestmark = pytest.mark.anyio

PROTOBUF_HEADERS = {
    "Authorization": f"Bearer {SAMPLE_DATA_KEY}",
    "Content-Type": "application/x-protobuf",
}
VALID_PAYLOAD = make_request(make_record()).SerializeToString()


@pytest.fixture
def writer() -> FakeLogWriter:
    return FakeLogWriter()


@pytest.fixture
async def client(writer: FakeLogWriter) -> AsyncIterator[httpx.AsyncClient]:
    keys = FakeApiKeyStore()
    keys.add_key(SAMPLE_DATA_KEY)
    app = create_app()
    app.dependency_overrides[get_api_key_auth_service] = lambda: ApiKeyAuthService(keys)
    app.dependency_overrides[get_log_ingest_service] = lambda: LogIngestService(writer)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


async def test_stores_logs_and_replies_with_an_otlp_response(
    client: httpx.AsyncClient, writer: FakeLogWriter
) -> None:
    response = await client.post("/v1/logs", content=VALID_PAYLOAD, headers=PROTOBUF_HEADERS)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-protobuf"
    ExportLogsServiceResponse.FromString(response.content)
    assert len(writer.rows) == 1


async def test_accepts_a_gzip_body(client: httpx.AsyncClient, writer: FakeLogWriter) -> None:
    headers = {**PROTOBUF_HEADERS, "Content-Encoding": "gzip"}

    response = await client.post("/v1/logs", content=gzip.compress(VALID_PAYLOAD), headers=headers)

    assert response.status_code == 200
    assert len(writer.rows) == 1


@pytest.mark.parametrize(
    "authorization",
    [None, "sp_ingest_no-bearer-prefix", "Bearer sp_ingest_unknown-key"],
    ids=["missing", "no-bearer", "unknown"],
)
async def test_rejects_requests_without_a_valid_data_key(
    client: httpx.AsyncClient, writer: FakeLogWriter, authorization: str | None
) -> None:
    headers = {"Content-Type": "application/x-protobuf"}
    if authorization:
        headers["Authorization"] = authorization

    response = await client.post("/v1/logs", content=VALID_PAYLOAD, headers=headers)

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "invalid_key"
    assert writer.rows == []


async def test_key_is_checked_before_the_body_is_read(client: httpx.AsyncClient) -> None:
    oversized = b"\0" * (10 * 1024 * 1024 + 1)

    response = await client.post(
        "/v1/logs", content=oversized, headers={"Content-Type": "application/x-protobuf"}
    )

    assert response.status_code == 401


async def test_rejects_json_bodies(client: httpx.AsyncClient) -> None:
    headers = {**PROTOBUF_HEADERS, "Content-Type": "application/json"}

    response = await client.post("/v1/logs", content=b"{}", headers=headers)

    assert response.status_code == 415
    assert response.json()["code"] == "unsupported_media_type"


async def test_rejects_unknown_content_encoding(client: httpx.AsyncClient) -> None:
    headers = {**PROTOBUF_HEADERS, "Content-Encoding": "br"}

    response = await client.post("/v1/logs", content=VALID_PAYLOAD, headers=headers)

    assert response.status_code == 415


async def test_rejects_a_body_over_10_mb(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/v1/logs", content=b"\0" * (10 * 1024 * 1024 + 1), headers=PROTOBUF_HEADERS
    )

    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"


async def test_rejects_a_gzip_body_that_expands_past_50_mb(client: httpx.AsyncClient) -> None:
    bomb = gzip.compress(b"\0" * (50 * 1024 * 1024 + 1))
    headers = {**PROTOBUF_HEADERS, "Content-Encoding": "gzip"}

    response = await client.post("/v1/logs", content=bomb, headers=headers)

    assert response.status_code == 413


async def test_rejects_a_body_that_is_not_otlp(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/v1/logs", content=b"\xff\xff not protobuf", headers=PROTOBUF_HEADERS
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_request"


async def test_replies_503_when_storage_is_down_so_the_collector_retries(
    client: httpx.AsyncClient, writer: FakeLogWriter
) -> None:
    writer.storage_down = True

    response = await client.post("/v1/logs", content=VALID_PAYLOAD, headers=PROTOBUF_HEADERS)

    assert response.status_code == 503
    assert response.json()["code"] == "storage_unavailable"


async def test_unknown_routes_return_problem_json(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/nothing-here")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
