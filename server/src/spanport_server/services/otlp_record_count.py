"""Counts the records in an OTLP request by reading the protobuf wire format, without decoding it.

Decoding builds an object per record: a 10 MB body of empty records holds 5 million of them and
takes hundreds of MB to decode. Counting first lets a request over the limit be refused cheaply.
The count stops as soon as it passes the limit, and each record is skipped by its length.
"""

from enum import IntEnum

from spanport_server.core.constants import (
    INVALID_OTLP_DETAIL,
    MAX_INGEST_RECORDS,
    MAX_VARINT_SHIFT,
    OTLP_RECORD_FIELD_PATH,
    PROTOBUF_FIELD_NUMBER_SHIFT,
    PROTOBUF_FIXED32_BYTES,
    PROTOBUF_FIXED64_BYTES,
    PROTOBUF_WIRE_TYPE_MASK,
    TOO_MANY_RECORDS_DETAIL,
    VARINT_BITS_PER_BYTE,
    VARINT_CONTINUE_BIT,
    VARINT_PAYLOAD_MASK,
)
from spanport_server.core.errors import InvalidRequestError, PayloadTooLargeError


class WireType(IntEnum):
    """Protobuf wire types (groups are not used by OTLP and are refused)."""

    VARINT = 0
    FIXED64 = 1
    LENGTH_DELIMITED = 2
    FIXED32 = 5


def read_varint(data: bytes, position: int) -> tuple[int, int]:
    """Read a varint.

    Returns:
        The value and the position after it.

    Raises:
        InvalidRequestError: The varint is truncated or too long.
    """
    value = 0
    shift = 0
    while position < len(data) and shift <= MAX_VARINT_SHIFT:
        byte = data[position]
        position += 1
        value |= (byte & VARINT_PAYLOAD_MASK) << shift
        if not byte & VARINT_CONTINUE_BIT:
            return value, position
        shift += VARINT_BITS_PER_BYTE
    raise InvalidRequestError(INVALID_OTLP_DETAIL)


def skip_value(data: bytes, position: int, wire_type: int) -> int:
    """Skip one field value of the given wire type and return the position after it.

    Raises:
        InvalidRequestError: Unknown wire type, or a truncated varint.
    """
    match wire_type:
        case WireType.VARINT:
            return read_varint(data, position)[1]
        case WireType.LENGTH_DELIMITED:
            length, position = read_varint(data, position)
            return position + length
        case WireType.FIXED64:
            return position + PROTOBUF_FIXED64_BYTES
        case WireType.FIXED32:
            return position + PROTOBUF_FIXED32_BYTES
    raise InvalidRequestError(INVALID_OTLP_DETAIL)


def count_records(
    data: bytes, field_path: tuple[int, ...], limit: int, start: int = 0, end: int | None = None
) -> int:
    """Count the messages at `field_path` inside `data[start:end]`, stopping past `limit`.

    Args:
        data: The serialized request.
        field_path: Field numbers from the request down to the record, e.g. (1, 2, 2).
        limit: Counting stops once the count is over this.
        start: Where the message to read begins.
        end: Where it ends; the end of `data` by default.

    Returns:
        The number of records, or a number over `limit` if there are more than `limit`.

    Raises:
        InvalidRequestError: The bytes are not valid protobuf.
    """
    end = len(data) if end is None else end
    count = 0
    position = start
    while position < end and count <= limit:
        key, position = read_varint(data, position)
        wire_type = key & PROTOBUF_WIRE_TYPE_MASK
        field_number = key >> PROTOBUF_FIELD_NUMBER_SHIFT
        if field_number != field_path[0] or wire_type != WireType.LENGTH_DELIMITED:
            position = skip_value(data, position, wire_type)
            continue
        length, position = read_varint(data, position)
        if position + length > end:
            raise InvalidRequestError(INVALID_OTLP_DETAIL)
        if len(field_path) == 1:
            count += 1
        else:
            count += count_records(data, field_path[1:], limit - count, position, position + length)
        position += length
    if position > end:
        raise InvalidRequestError(INVALID_OTLP_DETAIL)
    return count


def check_record_count(payload: bytes) -> None:
    """Refuse a request holding more than MAX_INGEST_RECORDS log records or spans.

    Raises:
        PayloadTooLargeError: Too many records.
        InvalidRequestError: The bytes are not valid protobuf.
    """
    if count_records(payload, OTLP_RECORD_FIELD_PATH, MAX_INGEST_RECORDS) > MAX_INGEST_RECORDS:
        raise PayloadTooLargeError(TOO_MANY_RECORDS_DETAIL.format(limit=MAX_INGEST_RECORDS))
