"""Request IDs and problem+json errors (RFC 9457). Stack traces go to logs, never clients."""

import logging
from collections.abc import Awaitable, Callable
from http import HTTPStatus

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from spanport_server.core.constants import (
    PROBLEM_CONTENT_TYPE,
    PROBLEM_TYPE_DEFAULT,
    REQUEST_ID_HEADER,
    RETRY_AFTER_HEADER,
)
from spanport_server.core.errors import InvalidRequestError, RateLimitedError, SpanportError
from spanport_server.core.ids import new_id
from spanport_server.core.request_body import describe_issues
from spanport_server.core.request_context import request_id_var

logger = logging.getLogger(__name__)


def problem_response(status: HTTPStatus, code: str, detail: str) -> JSONResponse:
    """Build a problem+json response for the current request.

    Args:
        status: HTTP status; its phrase becomes the title.
        code: Stable error code, e.g. "invalid_key".
        detail: What went wrong, without secrets.

    Returns:
        The JSON response, including the request ID.
    """
    body = {
        "type": PROBLEM_TYPE_DEFAULT,
        "title": status.phrase,
        "status": status.value,
        "detail": detail,
        "code": code,
        "request_id": request_id_var.get(),
    }
    return JSONResponse(body, status_code=status.value, media_type=PROBLEM_CONTENT_TYPE)


async def assign_request_id(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Give the request a UUIDv7 ID for its log lines, its error body and the response header.

    Args:
        request: The incoming request.
        call_next: The rest of the app.

    Returns:
        The response, with the X-Request-ID header set.
    """
    request_id = str(new_id())
    # Not reset afterwards: the handler for unexpected errors runs after this function, and the
    # server handles each request in its own task, so the value never reaches another request.
    request_id_var.set(request_id)
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response


def install_error_handlers(app: FastAPI) -> None:
    """Register the request ID middleware and the problem+json exception handlers.

    Args:
        app: The FastAPI app to configure.
    """
    app.middleware("http")(assign_request_id)

    @app.exception_handler(SpanportError)
    async def handle_spanport_error(request: Request, error: SpanportError) -> JSONResponse:
        """Return a domain error as problem+json (with Retry-After when rate limited)."""
        response = problem_response(error.status, error.code, error.detail)
        if isinstance(error, RateLimitedError):
            response.headers[RETRY_AFTER_HEADER] = str(error.retry_after_seconds)
        return response

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        """Bad query parameters: a 400 naming the fields, never echoing their values."""
        return problem_response(
            InvalidRequestError.status, InvalidRequestError.code, describe_issues(error.errors())
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
        """Return framework errors (unknown route, wrong method) as problem+json."""
        status = HTTPStatus(error.status_code)
        return problem_response(status, status.phrase.lower().replace(" ", "_"), str(error.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        """Log an unexpected error with its stack trace and return a plain 500."""
        logger.exception("unhandled error method=%s path=%s", request.method, request.url.path)
        return problem_response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            SpanportError.code,
            "Something went wrong on the server. Try again later.",
        )
