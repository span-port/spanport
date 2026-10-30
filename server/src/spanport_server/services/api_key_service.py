"""Creates, lists and revokes API keys, from the CLI (by slugs) and the UI (by ids)."""

import logging
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Protocol

from spanport_server.core.constants import (
    ADMIN_KEY_PROJECT_DETAIL,
    ADMIN_KEY_SCOPES_DETAIL,
    API_KEY_RANDOM_BYTES,
    ARCHIVED_PROJECT_DETAIL,
    KEY_PROJECT_DETAIL,
    MAX_ADMIN_KEY_DAYS,
    NO_ACTIVE_KEY_DETAIL,
    NO_KEY_DETAIL,
    NO_REVOKED_KEY_DETAIL,
    SLUG_PATTERN,
)
from spanport_server.core.errors import InvalidRequestError, NotFoundError
from spanport_server.core.ids import UuidV7
from spanport_server.core.key_hashing import hash_api_key, visible_suffix
from spanport_server.schemas.api_key import (
    ApiKeyListResponse,
    ApiKeyRecord,
    CreatedKey,
    CreateKeyRequest,
    KeyType,
    Scope,
    key_item,
    key_prefix,
)
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.tenant import ProjectItem, ProjectRef
from spanport_server.services.id_cursor import parse_id_cursor

logger = logging.getLogger(__name__)


class TenantStore(Protocol):
    """Finds or creates organizations, clients and projects."""

    async def get_or_create_project(
        self, org_slug: str, client_slug: str, project_slug: str, environment: str
    ) -> ProjectRef:
        """Return the project, creating it and its parents if missing."""
        ...

    async def find_org_id(self, org_slug: str) -> UuidV7 | None:
        """Return the organization's id, or None if there is none with this slug."""
        ...

    async def find_project(self, org_id: UuidV7, project_id: UuidV7) -> ProjectItem | None:
        """One project of this organization, archived or not, or None."""
        ...


class ApiKeyStore(Protocol):
    """Stores keys."""

    async def insert_key(
        self,
        org_id: UuidV7,
        project_id: UuidV7 | None,
        key_type: KeyType,
        key_hash: str,
        last_four: str,
        scopes: tuple[Scope, ...] = (),
        expires_at: datetime | None = None,
        name: str | None = None,
    ) -> ApiKeyRecord:
        """Store a key and return it."""
        ...

    async def list_for_org(self, org_id: UuidV7) -> list[ApiKeyRecord]:
        """Every key of the organization, newest first."""
        ...

    async def list_page(
        self, org_id: UuidV7, before_id: UuidV7 | None, limit: int
    ) -> list[ApiKeyRecord]:
        """Up to `limit` keys of the organization older than `before_id`, newest first."""
        ...

    async def revoke(self, org_id: UuidV7, key_id: UuidV7, revoked_at: datetime) -> bool:
        """Revoke a key of the organization; False if none matched or already revoked."""
        ...

    async def rename(self, org_id: UuidV7, key_id: UuidV7, name: str) -> ApiKeyRecord | None:
        """The renamed key, or None when the organization has no such key."""
        ...

    async def delete_revoked(self, org_id: UuidV7, key_id: UuidV7) -> bool:
        """Delete a revoked key; False when the organization has no revoked key with this id."""
        ...


def check_slug(field_name: str, value: str) -> None:
    """Raise InvalidRequestError unless `value` is a slug. The message never echoes the value."""
    if not re.fullmatch(SLUG_PATTERN, value):
        raise InvalidRequestError(
            f"{field_name} must be 1 to 63 lowercase letters, digits or dashes."
        )


def check_admin_key(scopes: tuple[Scope, ...], expires_in_days: int) -> None:
    """Raise InvalidRequestError for an admin key without scopes or with a bad expiry."""
    if not scopes:
        raise InvalidRequestError(ADMIN_KEY_SCOPES_DETAIL)
    if not 1 <= expires_in_days <= MAX_ADMIN_KEY_DAYS:
        raise InvalidRequestError(f"Admin keys must expire within 1 to {MAX_ADMIN_KEY_DAYS} days.")


def new_raw_key(key_type: KeyType) -> str:
    """A new random key with its type's prefix."""
    return key_prefix(key_type) + secrets.token_urlsafe(API_KEY_RANDOM_BYTES)


class ApiKeyService:
    """Creates, lists and revokes keys."""

    def __init__(self, tenants: TenantStore, keys: ApiKeyStore) -> None:
        """Create the service.

        Args:
            tenants: Organization, client and project storage.
            keys: Key storage.
        """
        self._tenants = tenants
        self._keys = keys

    async def create_data_key(
        self, org_slug: str, client_slug: str, project_slug: str, environment: str
    ) -> CreatedKey:
        """Create a data key for a project, creating the project and its parents if missing (CLI).

        Returns:
            The new key. Its raw value is never stored and must be shown to the user once.

        Raises:
            InvalidRequestError: A slug or the environment is not valid.
        """
        check_slug("org", org_slug)
        check_slug("client", client_slug)
        check_slug("project", project_slug)
        check_slug("environment", environment)
        project = await self._tenants.get_or_create_project(
            org_slug, client_slug, project_slug, environment
        )
        return await self._insert_data_key(project.org_id, project.project_id, None)

    async def create_admin_key(
        self, org_slug: str, scopes: tuple[Scope, ...], expires_in_days: int
    ) -> CreatedKey:
        """Create an admin key for an existing organization (CLI).

        Raises:
            InvalidRequestError: Bad slug, no scopes or expiry out of range.
            NotFoundError: No organization with this slug.
        """
        check_slug("org", org_slug)
        check_admin_key(scopes, expires_in_days)
        org_id = await self._require_org(org_slug)
        return await self._insert_admin_key(org_id, scopes, expires_in_days, None)

    async def create_key(self, caller: Caller, request: CreateKeyRequest) -> CreatedKey:
        """Create a named key from the UI: a data key for an org's project, or an admin key.

        Raises:
            InvalidRequestError: A data key without a project, an admin key with a project or
                without scopes.
            NotFoundError: The project isn't in the caller's organization.
        """
        name = request.name.strip()
        if request.key_type == KeyType.INGEST:
            if request.project_id is None:
                raise InvalidRequestError(KEY_PROJECT_DETAIL)
            project = await self._tenants.find_project(caller.org_id, request.project_id)
            if project is None:
                raise NotFoundError(KEY_PROJECT_DETAIL)
            if project.archived:
                raise InvalidRequestError(ARCHIVED_PROJECT_DETAIL)
            return await self._insert_data_key(caller.org_id, request.project_id, name)
        if request.project_id is not None:
            raise InvalidRequestError(ADMIN_KEY_PROJECT_DETAIL)
        scopes = tuple(dict.fromkeys(request.scopes))
        check_admin_key(scopes, request.expires_in_days)
        return await self._insert_admin_key(caller.org_id, scopes, request.expires_in_days, name)

    async def list_page(self, caller: Caller, cursor: str | None, limit: int) -> ApiKeyListResponse:
        """One page of the caller's organization's keys, newest first, without hashes.

        Raises:
            InvalidRequestError: The cursor is not valid.
        """
        before_id = parse_id_cursor(cursor) if cursor else None
        rows = await self._keys.list_page(caller.org_id, before_id, limit + 1)
        page = rows[:limit]
        has_more = len(rows) > limit
        logger.info("keys listed %s rows=%d has_more=%s", caller.label, len(page), has_more)
        return ApiKeyListResponse(
            data=[key_item(record) for record in page],
            next_cursor=str(page[-1].id) if has_more else None,
            has_more=has_more,
        )

    async def list_keys(self, org_slug: str) -> list[ApiKeyRecord]:
        """Every key of an organization, newest first, without hashes (CLI).

        Raises:
            NotFoundError: No organization with this slug.
        """
        org_id = await self._require_org(org_slug)
        keys = await self._keys.list_for_org(org_id)
        logger.info("keys listed org=%s count=%d", org_slug, len(keys))
        return keys

    async def revoke_key(self, org_slug: str, key_id: UuidV7) -> None:
        """Revoke one key of an organization by slug (CLI).

        Raises:
            NotFoundError: No such organization, no such key in it, or already revoked.
        """
        await self.revoke_in_org(await self._require_org(org_slug), key_id, f"org={org_slug}")

    async def revoke_in_org(self, org_id: UuidV7, key_id: UuidV7, label: str) -> None:
        """Revoke one key of an organization. It stops working on its next request.

        Args:
            org_id: The organization the key must belong to.
            key_id: The key.
            label: Who asked, for the log line.

        Raises:
            NotFoundError: No such key in the organization, or already revoked.
        """
        if not await self._keys.revoke(org_id, key_id, datetime.now(UTC)):
            raise NotFoundError(NO_ACTIVE_KEY_DETAIL)
        logger.info("key revoked id=%s %s", key_id, label)

    async def rename_key(self, caller: Caller, key_id: UuidV7, name: str) -> ApiKeyRecord:
        """Give a key a new name; the key itself doesn't change.

        Raises:
            NotFoundError: No such key in the caller's organization.
        """
        renamed = await self._keys.rename(caller.org_id, key_id, name.strip())
        if renamed is None:
            raise NotFoundError(NO_KEY_DETAIL)
        logger.info("key renamed id=%s %s", key_id, caller.label)
        return renamed

    async def delete_key(self, caller: Caller, key_id: UuidV7) -> None:
        """Remove a revoked key from the list for good. Active keys must be revoked first.

        Raises:
            NotFoundError: No revoked key with this id in the caller's organization.
        """
        if not await self._keys.delete_revoked(caller.org_id, key_id):
            raise NotFoundError(NO_REVOKED_KEY_DETAIL)
        logger.info("key deleted id=%s %s", key_id, caller.label)

    async def _insert_data_key(
        self, org_id: UuidV7, project_id: UuidV7, name: str | None
    ) -> CreatedKey:
        """Store a new data key and log its id and last four characters (never the key)."""
        raw_key = new_raw_key(KeyType.INGEST)
        record = await self._keys.insert_key(
            org_id,
            project_id,
            KeyType.INGEST,
            hash_api_key(raw_key),
            visible_suffix(raw_key),
            name=name,
        )
        logger.info(
            "data key created id=%s key=...%s org=%s project=%s",
            record.id,
            record.last_four,
            org_id,
            project_id,
        )
        return CreatedKey(raw_key=raw_key, record=record)

    async def _insert_admin_key(
        self, org_id: UuidV7, scopes: tuple[Scope, ...], expires_in_days: int, name: str | None
    ) -> CreatedKey:
        """Store a new admin key and log its id, scopes and expiry (never the key)."""
        raw_key = new_raw_key(KeyType.ADMIN)
        record = await self._keys.insert_key(
            org_id,
            None,
            KeyType.ADMIN,
            hash_api_key(raw_key),
            visible_suffix(raw_key),
            scopes=scopes,
            expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
            name=name,
        )
        logger.info(
            "admin key created id=%s key=...%s org=%s scopes=%s expires=%s",
            record.id,
            record.last_four,
            org_id,
            ",".join(scopes),
            record.expires_at,
        )
        return CreatedKey(raw_key=raw_key, record=record)

    async def _require_org(self, org_slug: str) -> UuidV7:
        """The organization's id, or NotFoundError."""
        org_id = await self._tenants.find_org_id(org_slug)
        if org_id is None:
            raise NotFoundError("No organization with this slug.")
        return org_id
