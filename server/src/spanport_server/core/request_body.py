"""Reading request bodies safely: size-capped, and JSON validated without echoing values."""

from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import Request
from pydantic import BaseModel, ValidationError

from spanport_server.core.constants import JSON_CONTENT_TYPE, VALIDATION_DETAIL_SEPARATOR
from spanport_server.core.errors import (
    InvalidRequestError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)


async def read_body_capped(request: Request, max_bytes: int) -> bytes:
    """Read the body, stopping as soon as it passes `max_bytes`.

    Raises:
        PayloadTooLargeError: The body is over `max_bytes`.
    """
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > max_bytes:
            raise PayloadTooLargeError(f"The body is over {max_bytes} bytes.")
        chunks.append(chunk)
    return b"".join(chunks)


def media_type(content_type: str) -> str:
    """The media type part of a Content-Type header, lower-cased, without parameters."""
    return content_type.partition(";")[0].strip().lower()


async def parse_json_body[ModelType: BaseModel](
    request: Request, content_type: str, model: type[ModelType], max_bytes: int
) -> ModelType:
    """Read a JSON body (at most `max_bytes`) and validate it against `model`.

    Error messages name the fields that are wrong and why, never the values sent.

    Raises:
        UnsupportedMediaTypeError: Not application/json.
        PayloadTooLargeError: Over `max_bytes`.
        InvalidRequestError: Not valid JSON, or doesn't match the model.
    """
    if media_type(content_type) != JSON_CONTENT_TYPE:
        raise UnsupportedMediaTypeError(f"Send the body as {JSON_CONTENT_TYPE}.")
    body = await read_body_capped(request, max_bytes)
    try:
        return model.model_validate_json(body)
    except ValidationError as error:
        raise InvalidRequestError(describe_validation_error(error)) from error


def describe_validation_error(error: ValidationError) -> str:
    """Describe a body validation failure; see describe_issues."""
    return describe_issues(error.errors(include_input=False, include_url=False))


def describe_issues(issues: Sequence[Mapping[str, Any]]) -> str:
    """List each bad field and why, e.g. "limit: Input should be less than or equal to 500".

    Only the location and the general part of Pydantic's message are used: the detail after it
    can quote the input (e.g. "invalid character: found `m` at 2"), and values are never echoed.
    """
    problems = [
        f"{'.'.join(str(part) for part in issue['loc']) or 'body'}: "
        f"{str(issue['msg']).split(VALIDATION_DETAIL_SEPARATOR, 1)[0]}"
        for issue in issues
    ]
    return "; ".join(problems)
