"""The current request's ID, readable from anywhere while that request is handled.

A ContextVar holds one value per request even when many requests run at once, so log lines and
error responses can include the ID without it being passed through every function.
"""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
