"""The opaque paging cursor: where the previous page ended, as base64url JSON.

A cursor comes back from the client, so every part of it is checked: it must be a JSON object
with the expected text fields, and its time must fall inside the request's range.
"""

import base64
import binascii
import json
import uuid
from datetime import UTC, datetime

from spanport_server.core.constants import CURSOR_ID_KEY, CURSOR_TIME_KEY, INVALID_CURSOR_DETAIL
from spanport_server.core.errors import InvalidRequestError
from spanport_server.schemas.log_search import LogPosition


def encode_cursor(position: LogPosition) -> str:
    """Encode the last row's position into a cursor string clients pass back unchanged."""
    payload = {CURSOR_TIME_KEY: position.ts.isoformat(), CURSOR_ID_KEY: str(position.log_id)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_cursor(cursor: str, start: datetime, end: datetime) -> LogPosition:
    """Decode a cursor from a previous response of a search over [start, end].

    Raises:
        InvalidRequestError: The cursor was changed, cut short, made up or belongs to another
            time range.
    """
    payload = cursor_payload(cursor)
    try:
        log_id = uuid.UUID(cursor_text(payload, CURSOR_ID_KEY))
    except ValueError as error:
        raise InvalidRequestError(INVALID_CURSOR_DETAIL) from error
    return LogPosition(ts=cursor_time(payload, start, end), log_id=log_id)


def cursor_payload(cursor: str) -> dict[str, object]:
    """The cursor's JSON object.

    Raises:
        InvalidRequestError: Not base64url JSON, nested too deeply, or not an object.
    """
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    except (binascii.Error, ValueError, RecursionError) as error:
        raise InvalidRequestError(INVALID_CURSOR_DETAIL) from error
    if not isinstance(payload, dict):
        raise InvalidRequestError(INVALID_CURSOR_DETAIL)
    return payload


def cursor_text(payload: dict[str, object], key: str) -> str:
    """A text field of the cursor.

    Raises:
        InvalidRequestError: Missing, or not text.
    """
    value = payload.get(key)
    if not isinstance(value, str):
        raise InvalidRequestError(INVALID_CURSOR_DETAIL)
    return value


def cursor_time(payload: dict[str, object], start: datetime, end: datetime) -> datetime:
    """The cursor's time in UTC, which must lie within the request's range.

    Raises:
        InvalidRequestError: Missing, not an ISO 8601 time with a zone, or outside [start, end].
    """
    try:
        ts = datetime.fromisoformat(cursor_text(payload, CURSOR_TIME_KEY))
        if ts.tzinfo is None:
            raise InvalidRequestError(INVALID_CURSOR_DETAIL)
        ts = ts.astimezone(UTC)
    except (ValueError, OverflowError) as error:
        raise InvalidRequestError(INVALID_CURSOR_DETAIL) from error
    if not start <= ts <= end:
        raise InvalidRequestError(INVALID_CURSOR_DETAIL)
    return ts
