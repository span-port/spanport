import threading
from collections.abc import Iterator
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from conftest import VALID_KEY, FakeSpanport

from spanport._key_check import check_data_key

WRONG_KEY = "sp_ingest_wrong-test-key-000000000000000000wxyz"


def test_valid_key_is_accepted(
    fake_spanport: FakeSpanport, sdk_messages: pytest.LogCaptureFixture
) -> None:
    assert check_data_key(fake_spanport.url, VALID_KEY) is True

    [request] = fake_spanport.requests
    assert (request.method, request.path) == ("GET", "/api/v1/api-keys/current")
    assert request.authorization == f"Bearer {VALID_KEY}"
    assert "data key ...a1b2 accepted" in sdk_messages.text


def test_rejected_key_is_reported_loudly_without_showing_the_key(
    fake_spanport: FakeSpanport, sdk_messages: pytest.LogCaptureFixture
) -> None:
    assert check_data_key(fake_spanport.url, WRONG_KEY) is False

    [message] = sdk_messages.records
    assert message.levelname == "ERROR"
    assert "...wxyz was rejected" in message.getMessage()
    assert WRONG_KEY not in sdk_messages.text


def test_unreachable_server_is_a_warning_not_a_crash(
    sdk_messages: pytest.LogCaptureFixture,
) -> None:
    assert check_data_key("http://127.0.0.1:9", VALID_KEY) is False

    [message] = sdk_messages.records
    assert message.levelname == "WARNING"
    assert "could not reach" in message.getMessage()


@pytest.fixture
def redirect_to_other_host(fake_spanport: FakeSpanport) -> Iterator[str]:
    """A server that answers every request with a redirect to fake_spanport (the "other host")."""
    target = fake_spanport.url

    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", target + "/stolen")
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_redirect_is_refused_so_the_key_never_reaches_another_host(
    fake_spanport: FakeSpanport,
    redirect_to_other_host: str,
    sdk_messages: pytest.LogCaptureFixture,
) -> None:
    assert check_data_key(redirect_to_other_host, VALID_KEY) is False

    assert fake_spanport.requests == []
    assert "HTTP 302" in sdk_messages.text


def test_non_http_url_is_refused(sdk_messages: pytest.LogCaptureFixture) -> None:
    assert check_data_key("file:///etc/passwd", VALID_KEY) is False

    assert "must start with http:// or https://" in sdk_messages.text
