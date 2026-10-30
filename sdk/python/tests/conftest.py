import logging
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import spanport
from spanport._sdk_logger import get_sdk_logger

VALID_KEY = "sp_ingest_valid-test-key-00000000000000000a1b2"


@dataclass(frozen=True)
class ReceivedRequest:
    method: str
    path: str
    authorization: str | None
    body: bytes


class FakeSpanport:
    """A local HTTP server playing both the collector (POST /v1/logs) and the server (key check)."""

    def __init__(self) -> None:
        self.requests: list[ReceivedRequest] = []
        received = self.requests

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                received.append(self._received(self.rfile.read(length)))
                self.send_response(HTTPStatus.OK)
                self.end_headers()

            def do_GET(self) -> None:
                received.append(self._received(b""))
                valid = self.headers.get("Authorization") == f"Bearer {VALID_KEY}"
                self.send_response(HTTPStatus.OK if valid else HTTPStatus.UNAUTHORIZED)
                self.end_headers()

            def _received(self, body: bytes) -> ReceivedRequest:
                return ReceivedRequest(
                    self.command, self.path, self.headers.get("Authorization"), body
                )

            def log_message(self, format: str, *args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def fake_spanport() -> Iterator[FakeSpanport]:
    server = FakeSpanport()
    server.start()
    yield server
    server.stop()


@pytest.fixture(autouse=True)
def clean_sdk() -> Iterator[None]:
    """Each test starts with no SDK pipeline attached and ends by removing it."""
    yield
    spanport.shutdown()


@pytest.fixture
def sdk_messages(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    """Capture the SDK's own messages, which go to stderr and never reach the root logger."""
    sdk_logger = get_sdk_logger()
    sdk_logger.addHandler(caplog.handler)
    caplog.set_level(logging.INFO, logger=sdk_logger.name)
    yield caplog
    sdk_logger.removeHandler(caplog.handler)
