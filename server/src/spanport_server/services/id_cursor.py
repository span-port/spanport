"""Paging cursors for lists ordered by id: the cursor is the last id of the previous page."""

import uuid

from spanport_server.core.constants import INVALID_CURSOR_DETAIL
from spanport_server.core.errors import InvalidRequestError
from spanport_server.core.ids import UuidV7


def parse_id_cursor(cursor: str) -> UuidV7:
    """The id a cursor points past.

    Raises:
        InvalidRequestError: The cursor is not an id.
    """
    try:
        return uuid.UUID(cursor)
    except ValueError as error:
        raise InvalidRequestError(INVALID_CURSOR_DETAIL) from error
