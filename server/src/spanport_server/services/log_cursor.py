"""The opaque paging cursor: where the previous page ended, as base64url JSON."""

import base64
import binascii
import json
import uuid
from datetime import datetime

from spanport_server.core.constants import CURSOR_ID_KEY, CURSOR_TIME_KEY, INVALID_CURSOR_DETAIL
from spanport_server.core.errors import InvalidRequestError
from spanport_server.schemas.log_search import LogPosition


def encode_cursor(position: LogPosition) -> str:
    """Encode the last row's position into a cursor string clients pass back unchanged."""
    payload = {CURSOR_TIME_KEY: position.ts.isoformat(), CURSOR_ID_KEY: str(position.log_id)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_cursor(cursor: str) -> LogPosition:
    """Decode a cursor from a previous response.

    Raises:
        InvalidRequestError: The cursor was changed, cut short or made up.
    """
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        ts = datetime.fromisoformat(payload[CURSOR_TIME_KEY])
        log_id = uuid.UUID(payload[CURSOR_ID_KEY])
    except (binascii.Error, ValueError, KeyError, TypeError) as error:
        raise InvalidRequestError(INVALID_CURSOR_DETAIL) from error
    if ts.tzinfo is None:
        raise InvalidRequestError(INVALID_CURSOR_DETAIL)
    return LogPosition(ts=ts, log_id=log_id)
