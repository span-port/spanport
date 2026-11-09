import pytest

from spanport._endpoints import is_local_url, key_check_url, warn_plain_http


@pytest.mark.parametrize(
    "url",
    ["http://localhost:4318", "http://127.0.0.1:4318", "http://[::1]:4318", "http://LOCALHOST"],
)
def test_this_machine_is_local(url: str) -> None:
    assert is_local_url(url)


def test_another_host_is_not_local() -> None:
    assert not is_local_url("https://collector.acme.com")


def test_a_given_server_url_is_always_used() -> None:
    assert key_check_url("https://collector.acme.com", "https://spanport.acme.com") == (
        "https://spanport.acme.com"
    )


def test_the_default_server_is_used_only_with_a_local_collector(
    sdk_messages: pytest.LogCaptureFixture,
) -> None:
    assert key_check_url("http://localhost:4318", None) == "http://localhost:8000"
    assert sdk_messages.records == []


def test_a_remote_collector_without_server_url_skips_the_key_check(
    sdk_messages: pytest.LogCaptureFixture,
) -> None:
    assert key_check_url("https://collector.acme.com", None) is None

    [message] = sdk_messages.records
    assert "set server_url" in message.getMessage()


def test_plain_http_to_another_host_is_warned_once(
    sdk_messages: pytest.LogCaptureFixture,
) -> None:
    warn_plain_http(["http://collector.acme.com:4318", "http://spanport.acme.com"])

    [message] = sdk_messages.records
    assert message.levelname == "WARNING"
    assert "http://collector.acme.com:4318, http://spanport.acme.com" in message.getMessage()


def test_https_and_local_http_are_not_warned(sdk_messages: pytest.LogCaptureFixture) -> None:
    warn_plain_http(["https://collector.acme.com", "http://localhost:4318"])

    assert sdk_messages.records == []
