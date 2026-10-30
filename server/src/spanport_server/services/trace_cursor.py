"""The opaque paging cursor for the Requests list: where the last page ended, as base64url JSON."""

import base64
import binascii
import json
import re
from datetime import datetime

from spanport_server.core.constants import (
    CURSOR_SPAN_KEY,
    CURSOR_TIME_KEY,
    INVALID_CURSOR_DETAIL,
    SPAN_ID_PATTERN,
)
from spanport_server.core.errors import InvalidRequestError
from spanport_server.schemas.trace import SpanPosition


def encode_trace_cursor(position: SpanPosition) -> str:
    """Encode the last row's position into a cursor clients pass back unchanged."""
    payload = {CURSOR_TIME_KEY: position.ts.isoformat(), CURSOR_SPAN_KEY: position.span_id}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_trace_cursor(cursor: str) -> SpanPosition:
    """Decode a cursor from a previous response.

    Raises:
        InvalidRequestError: The cursor was changed, cut short or made up.
    """
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        ts = datetime.fromisoformat(payload[CURSOR_TIME_KEY])
        span_id = str(payload[CURSOR_SPAN_KEY])
    except (binascii.Error, ValueError, KeyError, TypeError) as error:
        raise InvalidRequestError(INVALID_CURSOR_DETAIL) from error
    if ts.tzinfo is None or not re.fullmatch(SPAN_ID_PATTERN, span_id):
        raise InvalidRequestError(INVALID_CURSOR_DETAIL)
    return SpanPosition(ts=ts, span_id=span_id)
