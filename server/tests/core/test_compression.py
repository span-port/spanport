import gzip

import pytest

from spanport_server.core.compression import gunzip_capped
from spanport_server.core.errors import InvalidRequestError, PayloadTooLargeError


def test_decompresses_a_body_within_the_limit() -> None:
    assert gunzip_capped(gzip.compress(b"hello logs"), max_bytes=100) == b"hello logs"


def test_body_exactly_at_the_limit_is_accepted() -> None:
    assert gunzip_capped(gzip.compress(b"x" * 100), max_bytes=100) == b"x" * 100


def test_stops_a_zip_bomb_over_the_limit() -> None:
    bomb = gzip.compress(b"\0" * 1_000_000)

    with pytest.raises(PayloadTooLargeError):
        gunzip_capped(bomb, max_bytes=1000)


def test_rejects_data_that_is_not_gzip() -> None:
    with pytest.raises(InvalidRequestError):
        gunzip_capped(b"not gzip at all", max_bytes=100)


def test_rejects_a_truncated_body() -> None:
    truncated = gzip.compress(b"hello logs")[:-6]

    with pytest.raises(InvalidRequestError):
        gunzip_capped(truncated, max_bytes=100)


def test_rejects_several_gzip_members() -> None:
    two_members = gzip.compress(b"one") + gzip.compress(b"two")

    with pytest.raises(InvalidRequestError):
        gunzip_capped(two_members, max_bytes=100)
