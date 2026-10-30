import logging
import threading

import pytest
from conftest import VALID_KEY, FakeSpanport
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest

import spanport


def wait_for_key_check() -> None:
    for thread in threading.enumerate():
        if thread.name == "spanport-key-check":
            thread.join(timeout=5)


def test_logs_reach_the_collector_with_the_data_key(
    fake_spanport: FakeSpanport, sdk_messages: pytest.LogCaptureFixture
) -> None:
    spanport.init(
        data_key=VALID_KEY,
        service="hr-portal-api",
        collector_url=fake_spanport.url,
        server_url=fake_spanport.url,
    )
    wait_for_key_check()
    logging.getLogger("app").error("Payment failed for order 1042")
    spanport.shutdown()

    [log_post] = [request for request in fake_spanport.requests if request.method == "POST"]
    assert log_post.path == "/v1/logs"
    assert log_post.authorization == f"Bearer {VALID_KEY}"
    sent = ExportLogsServiceRequest.FromString(log_post.body)
    [record] = sent.resource_logs[0].scope_logs[0].log_records
    assert record.body.string_value == "Payment failed for order 1042"
    assert "data key ...a1b2 accepted" in sdk_messages.text


def test_shutdown_detaches_the_handler(fake_spanport: FakeSpanport) -> None:
    handlers_before = list(logging.getLogger().handlers)
    spanport.init(VALID_KEY, "svc", fake_spanport.url, fake_spanport.url, check_key=False)
    assert len(logging.getLogger().handlers) == len(handlers_before) + 1

    spanport.shutdown()
    spanport.shutdown()

    assert logging.getLogger().handlers == handlers_before


@pytest.mark.parametrize(
    ("data_key", "service", "expected"),
    [
        ("", "svc", "data_key must be a data key"),
        ("sp_admin_wrong-type", "svc", "data_key must be a data key"),
        (VALID_KEY, "", "service must name this app"),
    ],
)
def test_bad_arguments_are_reported_and_nothing_is_attached(
    sdk_messages: pytest.LogCaptureFixture, data_key: str, service: str, expected: str
) -> None:
    handlers_before = list(logging.getLogger().handlers)

    spanport.init(data_key=data_key, service=service, check_key=False)

    assert expected in sdk_messages.text
    assert logging.getLogger().handlers == handlers_before


def test_init_never_raises_even_if_setup_breaks(
    monkeypatch: pytest.MonkeyPatch, sdk_messages: pytest.LogCaptureFixture
) -> None:
    def broken_exporter(collector_url: str, data_key: str) -> None:
        raise RuntimeError("exporter could not start")

    monkeypatch.setattr(spanport, "build_otlp_exporter", broken_exporter)

    spanport.init(VALID_KEY, "svc", check_key=False)

    assert "setup failed; the app keeps running" in sdk_messages.text


def test_second_init_is_ignored(
    fake_spanport: FakeSpanport, sdk_messages: pytest.LogCaptureFixture
) -> None:
    spanport.init(VALID_KEY, "svc", fake_spanport.url, fake_spanport.url, check_key=False)
    handlers_after_first = list(logging.getLogger().handlers)

    spanport.init(VALID_KEY, "svc", fake_spanport.url, fake_spanport.url, check_key=False)

    assert logging.getLogger().handlers == handlers_after_first
    assert "already called" in sdk_messages.text
