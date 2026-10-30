import smtplib
import socket
from email.message import EmailMessage

import pytest

from spanport_server.clients.email_client import EmailClient, failure_detail
from spanport_server.core.config import Settings
from spanport_server.core.errors import DeliveryError

pytestmark = pytest.mark.anyio


class FakeConnection:
    """Records what the client did with the SMTP connection, and the message it sent."""

    def __init__(self, kind: str, calls: list[str], sent: list[EmailMessage]) -> None:
        self.calls = calls
        self.sent = sent
        calls.append(kind)

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def starttls(self) -> None:
        self.calls.append("starttls")

    def login(self, username: str, password: str) -> None:
        self.calls.append("login")

    def send_message(self, message: EmailMessage) -> None:
        self.calls.append("send")
        self.sent.append(message)


def settings(port: int) -> Settings:
    return Settings.model_validate(
        {
            "postgres_host": "db",
            "postgres_port": 5432,
            "postgres_user": "u",
            "postgres_password": "p",
            "postgres_db": "d",
            "clickhouse_host": "ch",
            "clickhouse_port": 8123,
            "clickhouse_user": "u",
            "clickhouse_password": "p",
            "clickhouse_db": "d",
            "server_host": "127.0.0.1",
            "server_port": 8000,
            "smtp_host": "smtp.example.com",
            "smtp_port": port,
            "smtp_username": "alerts@example.com",
            "smtp_password": "app-password",
            "smtp_from": "alerts@example.com",
        }
    )


class Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.sent: list[EmailMessage] = []


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    recorded = Recorder()
    monkeypatch.setattr(
        smtplib, "SMTP", lambda *a, **k: FakeConnection("plain", recorded.calls, recorded.sent)
    )
    monkeypatch.setattr(
        smtplib, "SMTP_SSL", lambda *a, **k: FakeConnection("ssl", recorded.calls, recorded.sent)
    )
    return recorded


async def send(port: int) -> None:
    await EmailClient(settings(port)).send(["a@example.com"], "Subject", "Body", "<p>Body</p>")


async def test_port_465_uses_ssl_from_the_start_without_starttls(recorder: Recorder) -> None:
    await send(465)

    assert recorder.calls == ["ssl", "login", "send"]


async def test_port_587_starts_plain_then_starttls(recorder: Recorder) -> None:
    await send(587)

    assert recorder.calls == ["plain", "starttls", "login", "send"]


async def test_the_email_has_a_text_part_and_an_html_part(recorder: Recorder) -> None:
    await send(587)

    (message,) = recorder.sent
    assert message.get_content_type() == "multipart/alternative"
    parts = {part.get_content_type(): part.get_content().strip() for part in message.iter_parts()}
    assert parts == {"text/plain": "Body", "text/html": "<p>Body</p>"}


async def test_a_refusal_becomes_a_delivery_error_naming_what_to_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")

    monkeypatch.setattr(smtplib, "SMTP", refuse)

    with pytest.raises(DeliveryError, match="SPANPORT_SMTP_PORT"):
        await send(587)


def test_the_ui_address_must_be_a_web_address() -> None:
    assert settings(587).model_copy(update={"ui_url": None}).ui_url is None
    with pytest.raises(ValueError, match="http"):
        Settings.model_validate({**settings(587).model_dump(), "ui_url": "javascript:alert(1)"})
    trimmed = Settings.model_validate(
        {**settings(587).model_dump(), "ui_url": "https://spanport.acme.com/"}
    )
    assert trimmed.ui_url == "https://spanport.acme.com"


def test_each_failure_says_which_setting_to_check() -> None:
    assert "app password" in failure_detail(smtplib.SMTPAuthenticationError(535, b"bad"))
    assert "SMTP_FROM" in failure_detail(smtplib.SMTPSenderRefused(553, b"no", "a@b.c"))
    assert "recipient" in failure_detail(smtplib.SMTPRecipientsRefused({}))
    assert "SMTP_HOST" in failure_detail(socket.gaierror("Name or service not known"))
    assert "SMTPDataError" in failure_detail(smtplib.SMTPDataError(554, b"spam"))
