"""Checks shared by every search over a time range (logs, requests, APIs, errors, the map)."""

from datetime import UTC, datetime

from spanport_server.core.constants import (
    MAX_RANGE_END_SKEW,
    RANGE_END_DETAIL,
    RANGE_ORDER_DETAIL,
    RANGE_OUT_OF_BOUNDS_DETAIL,
)
from spanport_server.core.errors import InvalidRequestError


def checked_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """The range in UTC: forwards, and ending at most MAX_RANGE_END_SKEW from now, so the range
    (and the earlier period some screens compare with) stays within real dates.

    Raises:
        InvalidRequestError: The range is backwards, ends too far ahead, or a time can't be
            turned into UTC (e.g. year 9999 with a negative offset).
    """
    try:
        start, end = start.astimezone(UTC), end.astimezone(UTC)
    except OverflowError as error:
        raise InvalidRequestError(RANGE_OUT_OF_BOUNDS_DETAIL) from error
    if end <= start:
        raise InvalidRequestError(RANGE_ORDER_DETAIL)
    if end > datetime.now(UTC) + MAX_RANGE_END_SKEW:
        raise InvalidRequestError(RANGE_END_DETAIL)
    return start, end
