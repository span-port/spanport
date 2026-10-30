"""Checks an API key on every request: prefix, known, type, not revoked, not expired, scope.

No cache: a revoked key stops working on the next request.
"""

import logging
from datetime import UTC, datetime
from typing import NoReturn, Protocol

from spanport_server.core.constants import INVALID_KEY_DETAIL
from spanport_server.core.errors import InvalidKeyError, MissingScopeError
from spanport_server.core.key_hashing import hash_api_key, visible_suffix
from spanport_server.schemas.api_key import ApiKeyRecord, KeyType, Scope, key_prefix

logger = logging.getLogger(__name__)


class ApiKeyLookup(Protocol):
    """Finds stored keys."""

    async def find_by_hash(self, key_hash: str) -> ApiKeyRecord | None:
        """Return the key with this hash, or None."""
        ...


def reject(reason: str, key_type: KeyType, raw_key: str) -> NoReturn:
    """Log why a key was rejected (never the key itself) and raise InvalidKeyError."""
    logger.warning("key rejected: %s %s key ...%s", reason, key_type, visible_suffix(raw_key))
    raise InvalidKeyError(INVALID_KEY_DETAIL)


class ApiKeyAuthService:
    """Authenticates raw API keys."""

    def __init__(self, keys: ApiKeyLookup) -> None:
        """Create the service.

        Args:
            keys: Where stored keys are looked up.
        """
        self._keys = keys

    async def authenticate(
        self, raw_key: str | None, key_type: KeyType, required_scope: Scope | None = None
    ) -> ApiKeyRecord:
        """Check a raw key and return the stored key it matches.

        Every authentication failure gives the caller the same message, so it can't tell why a
        key failed. A valid key without the needed scope gets a separate, explicit error.

        Args:
            raw_key: The key from the request, or None if none was sent.
            key_type: The kind of key this endpoint needs.
            required_scope: The scope this endpoint needs (admin keys), or None.

        Returns:
            The matching key, with its org (and project, for data keys).

        Raises:
            InvalidKeyError: Missing, malformed, unknown, of another type, revoked or expired.
            MissingScopeError: Valid, but without `required_scope`.
        """
        if not raw_key:
            reject("missing", key_type, "")
        if not raw_key.startswith(key_prefix(key_type)):
            reject("wrong prefix", key_type, raw_key)
        record = await self._keys.find_by_hash(hash_api_key(raw_key))
        if record is None:
            reject("unknown", key_type, raw_key)
        if record.key_type != key_type:
            reject("wrong type", key_type, raw_key)
        if record.revoked_at is not None:
            reject("revoked", key_type, raw_key)
        if record.expires_at is not None and record.expires_at <= datetime.now(UTC):
            reject("expired", key_type, raw_key)
        if required_scope is not None and required_scope not in record.scopes:
            logger.warning(
                "key refused: missing scope %s key=...%s", required_scope, record.last_four
            )
            raise MissingScopeError(f"This key does not have the {required_scope} scope.")
        return record
