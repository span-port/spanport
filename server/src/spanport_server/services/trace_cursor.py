"""The opaque paging cursor for the Requests list: where the last page ended, as base64url JSON."""

import base64
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
from spanport_server.services.log_cursor import cursor_payload, cursor_text, cursor_time


def encode_trace_cursor(position: SpanPosition) -> str:
    """Encode the last row's position into a cursor clients pass back unchanged."""
    payload = {CURSOR_TIME_KEY: position.ts.isoformat(), CURSOR_SPAN_KEY: position.span_id}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_trace_cursor(cursor: str, start: datetime, end: datetime) -> SpanPosition:
    """Decode a cursor from a previous response of a search over [start, end].

    Raises:
        InvalidRequestError: The cursor was changed, cut short, made up or belongs to another
            time range.
    """
    payload = cursor_payload(cursor)
    span_id = cursor_text(payload, CURSOR_SPAN_KEY)
    if not re.fullmatch(SPAN_ID_PATTERN, span_id):
        raise InvalidRequestError(INVALID_CURSOR_DETAIL)
    return SpanPosition(ts=cursor_time(payload, start, end), span_id=span_id)
