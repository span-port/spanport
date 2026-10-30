"""Bounded gzip decompression, so a small body can't expand into a huge one (zip bomb)."""

import zlib

from spanport_server.core.constants import GZIP_ENCODING, MAX_INGEST_DECOMPRESSED_BYTES
from spanport_server.core.errors import (
    InvalidRequestError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)

# 16 + MAX_WBITS tells zlib to expect a gzip header and trailer.
GZIP_WBITS = 16 + zlib.MAX_WBITS


def gunzip_capped(compressed: bytes, max_bytes: int) -> bytes:
    """Decompress a single gzip member, stopping as soon as the output passes `max_bytes`.

    Args:
        compressed: The gzip-compressed body.
        max_bytes: Largest allowed decompressed size.

    Returns:
        The decompressed bytes.

    Raises:
        InvalidRequestError: The body is not valid gzip, is truncated or has several members.
        PayloadTooLargeError: The decompressed body is over `max_bytes`.
    """
    decompressor = zlib.decompressobj(wbits=GZIP_WBITS)
    try:
        decompressed = decompressor.decompress(compressed, max_bytes + 1)
    except zlib.error as error:
        raise InvalidRequestError("The body is not valid gzip.") from error
    if len(decompressed) > max_bytes:
        raise PayloadTooLargeError(f"The decompressed body is over {max_bytes} bytes.")
    if not decompressor.eof:
        raise InvalidRequestError("The gzip body is truncated.")
    if decompressor.unused_data:
        raise InvalidRequestError("Send one gzip member per request.")
    return decompressed


def decode_otlp_body(body: bytes, content_encoding: str) -> bytes:
    """Undo an OTLP request's Content-Encoding: none, or gzip (capped at 50 MB decompressed).

    Raises:
        UnsupportedMediaTypeError: Any other encoding.
        InvalidRequestError / PayloadTooLargeError: As for gunzip_capped.
    """
    encoding = content_encoding.strip().lower()
    if not encoding:
        return body
    if encoding == GZIP_ENCODING:
        return gunzip_capped(body, MAX_INGEST_DECOMPRESSED_BYTES)
    raise UnsupportedMediaTypeError("Content-Encoding must be gzip or absent.")
