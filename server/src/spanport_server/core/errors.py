"""Domain errors. Services raise these; core/error_handlers.py turns them into problem+json."""

from http import HTTPStatus


class SpanportError(Exception):
    """Base error with an HTTP status and a stable code clients can rely on."""

    status = HTTPStatus.INTERNAL_SERVER_ERROR
    code = "internal_error"

    def __init__(self, detail: str) -> None:
        """Create the error.

        Args:
            detail: What went wrong and what to do next. Never include secrets or user data.
        """
        super().__init__(detail)
        self.detail = detail


class InvalidRequestError(SpanportError):
    """The request is malformed."""

    status = HTTPStatus.BAD_REQUEST
    code = "invalid_request"


class InvalidKeyError(SpanportError):
    """The API key is missing, unknown, revoked, expired or of the wrong type."""

    status = HTTPStatus.UNAUTHORIZED
    code = "invalid_key"


class NotSignedInError(SpanportError):
    """No valid session: never signed in, signed out, idle too long or the user was disabled."""

    status = HTTPStatus.UNAUTHORIZED
    code = "not_signed_in"


class InvalidLoginError(SpanportError):
    """The email or password is wrong. Never says which."""

    status = HTTPStatus.UNAUTHORIZED
    code = "invalid_login"


class CsrfError(SpanportError):
    """A signed-in browser request that changes something came without its CSRF token."""

    status = HTTPStatus.FORBIDDEN
    code = "csrf_failed"


class SetupLinkError(SpanportError):
    """The first-time setup token is wrong, used or expired, or setup is already done."""

    status = HTTPStatus.GONE
    code = "setup_link_invalid"


class InviteLinkError(SpanportError):
    """The invite link is wrong, used, cancelled or expired."""

    status = HTTPStatus.GONE
    code = "invite_invalid"


class MissingScopeError(SpanportError):
    """The key is valid but its scopes don't allow this action."""

    status = HTTPStatus.FORBIDDEN
    code = "insufficient_scope"


class NotAllowedError(SpanportError):
    """Signed in, but the person's role may not do this (e.g. a member managing keys)."""

    status = HTTPStatus.FORBIDDEN
    code = "insufficient_role"


class RateLimitedError(SpanportError):
    """Too many attempts; the client may try again after `retry_after_seconds`."""

    status = HTTPStatus.TOO_MANY_REQUESTS
    code = "rate_limited"

    def __init__(self, detail: str, retry_after_seconds: int) -> None:
        """Create the error.

        Args:
            detail: What happened and when to try again.
            retry_after_seconds: Sent as the Retry-After header.
        """
        super().__init__(detail)
        self.retry_after_seconds = retry_after_seconds


class ConflictError(SpanportError):
    """The thing to create already exists."""

    status = HTTPStatus.CONFLICT
    code = "already_exists"


class NotFoundError(SpanportError):
    """The thing asked for doesn't exist, or belongs to another organization."""

    status = HTTPStatus.NOT_FOUND
    code = "not_found"


class PayloadTooLargeError(SpanportError):
    """The body is over the size limit, before or after decompression."""

    status = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    code = "payload_too_large"


class UnsupportedMediaTypeError(SpanportError):
    """The content type or content encoding is not accepted."""

    status = HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    code = "unsupported_media_type"


class DeliveryError(SpanportError):
    """The mail server refused an alert email or couldn't be reached."""

    status = HTTPStatus.BAD_GATEWAY
    code = "delivery_failed"


class StorageUnavailableError(SpanportError):
    """A database is unreachable. Clients should retry later."""

    status = HTTPStatus.SERVICE_UNAVAILABLE
    code = "storage_unavailable"
