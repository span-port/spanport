from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from spanport_server.core.error_handlers import install_error_handlers
from spanport_server.core.errors import InvalidRequestError

pytestmark = pytest.mark.anyio


def build_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/invalid")
    async def invalid() -> None:
        raise InvalidRequestError("The cursor is not valid.")

    @app.get("/crash")
    async def crash() -> None:
        raise RuntimeError("database password is hunter2")

    return app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    # The server re-raises unexpected errors after replying; the transport must not re-raise them.
    transport = httpx.ASGITransport(app=build_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


async def test_every_response_gets_a_uuidv7_request_id(client: httpx.AsyncClient) -> None:
    first = await client.get("/ok")
    second = await client.get("/ok")

    first_id = first.headers["x-request-id"]
    assert first_id != second.headers["x-request-id"]
    assert first_id[14] == "7"


async def test_domain_error_is_full_problem_json(client: httpx.AsyncClient) -> None:
    response = await client.get("/invalid")

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Bad Request",
        "status": 400,
        "detail": "The cursor is not valid.",
        "code": "invalid_request",
        "request_id": response.headers["x-request-id"],
    }


async def test_unexpected_error_hides_details_but_keeps_the_request_id(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    response = await client.get("/crash")

    body = response.json()
    assert response.status_code == 500
    assert body["code"] == "internal_error"
    assert body["request_id"]
    assert "hunter2" not in response.text
    assert "unhandled error method=GET path=/crash" in caplog.text


async def test_unknown_route_is_problem_json(client: httpx.AsyncClient) -> None:
    response = await client.get("/missing")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert response.json()["request_id"] == response.headers["x-request-id"]
