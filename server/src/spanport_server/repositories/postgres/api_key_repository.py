"""Reads and writes the api_keys table."""

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spanport_server.core.ids import UuidV7, new_id
from spanport_server.models import ApiKey, Project
from spanport_server.schemas.api_key import ApiKeyRecord, KeyType, Scope


def to_record(api_key: ApiKey) -> ApiKeyRecord:
    """Convert a table row to the record services use."""
    return ApiKeyRecord(
        id=api_key.id,
        org_id=api_key.org_id,
        project_id=api_key.project_id,
        key_type=KeyType(api_key.key_type),
        last_four=api_key.last_four,
        scopes=tuple(Scope(scope) for scope in api_key.scopes),
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        revoked_at=api_key.revoked_at,
        name=api_key.name,
    )


class ApiKeyRepository:
    """api_keys table access."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Create the repository.

        Args:
            sessionmaker: Opens Postgres sessions.
        """
        self._sessionmaker = sessionmaker

    async def find_by_hash(self, key_hash: str) -> ApiKeyRecord | None:
        """Find a key by its hash.

        This is how a request's org is found, so it is the one lookup not filtered by org_id.
        A data key of an archived project is not found, so it stops working at once.

        Args:
            key_hash: SHA-256 hex digest of the raw key.

        Returns:
            The key, or None if no usable key has this hash.
        """
        query = (
            select(ApiKey)
            .outerjoin(Project, Project.id == ApiKey.project_id)
            .where(ApiKey.key_hash == key_hash, Project.archived_at.is_(None))
        )
        async with self._sessionmaker() as session:
            api_key = await session.scalar(query)
        return None if api_key is None else to_record(api_key)

    async def delete_revoked(self, org_id: UuidV7, key_id: UuidV7) -> bool:
        """Delete a revoked key of this organization; active keys are never deleted.

        Returns:
            False when the organization has no revoked key with this id.
        """
        async with self._sessionmaker.begin() as session:
            deleted = await session.scalar(
                delete(ApiKey)
                .where(
                    ApiKey.org_id == org_id,
                    ApiKey.id == key_id,
                    ApiKey.revoked_at.is_not(None),
                )
                .returning(ApiKey.id)
            )
        return deleted is not None

    async def rename(self, org_id: UuidV7, key_id: UuidV7, name: str) -> ApiKeyRecord | None:
        """Give a key of this organization a new name.

        Returns:
            The renamed key, or None when the organization has no such key.
        """
        async with self._sessionmaker.begin() as session:
            api_key = await session.scalar(
                update(ApiKey)
                .where(ApiKey.org_id == org_id, ApiKey.id == key_id)
                .values(name=name)
                .returning(ApiKey)
            )
            return None if api_key is None else to_record(api_key)

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
        """Store a new key.

        Args:
            org_id: Organization the key belongs to.
            project_id: Project for data keys; None for admin keys.
            key_type: Kind of key.
            key_hash: SHA-256 hex digest of the raw key.
            last_four: Last 4 characters of the raw key, for display.
            scopes: What an admin key may do.
            expires_at: When the key stops working; required for admin keys.
            name: What people call the key, e.g. "hr-portal-telemetry".

        Returns:
            The stored key.
        """
        api_key = ApiKey(
            id=new_id(),
            org_id=org_id,
            project_id=project_id,
            name=name,
            key_type=key_type,
            key_hash=key_hash,
            last_four=last_four,
            scopes=list(scopes),
            expires_at=expires_at,
        )
        async with self._sessionmaker.begin() as session:
            session.add(api_key)
            await session.flush()
            await session.refresh(api_key)
        return to_record(api_key)

    async def list_for_org(self, org_id: UuidV7) -> list[ApiKeyRecord]:
        """Return every key of one organization, newest first.

        Args:
            org_id: The organization.

        Returns:
            The keys, including revoked and expired ones.
        """
        async with self._sessionmaker() as session:
            api_keys = await session.scalars(
                select(ApiKey).where(ApiKey.org_id == org_id).order_by(ApiKey.created_at.desc())
            )
            return [to_record(api_key) for api_key in api_keys]

    async def list_page(
        self, org_id: UuidV7, before_id: UuidV7 | None, limit: int
    ) -> list[ApiKeyRecord]:
        """One page of an organization's keys, newest first (ids are time-ordered UUIDv7).

        Args:
            org_id: The organization.
            before_id: Continue with keys older than this id; None for the first page.
            limit: Most rows to return.

        Returns:
            Up to `limit` keys, including revoked and expired ones.
        """
        query = (
            select(ApiKey).where(ApiKey.org_id == org_id).order_by(ApiKey.id.desc()).limit(limit)
        )
        if before_id is not None:
            query = query.where(ApiKey.id < before_id)
        async with self._sessionmaker() as session:
            return [to_record(api_key) for api_key in await session.scalars(query)]

    async def revoke(self, org_id: UuidV7, key_id: UuidV7, revoked_at: datetime) -> bool:
        """Mark a key of this organization as revoked, unless it already is.

        Args:
            org_id: The organization the key must belong to.
            key_id: The key to revoke.
            revoked_at: When it was revoked (UTC).

        Returns:
            True if a key was revoked; False if none matched or it was already revoked.
        """
        async with self._sessionmaker.begin() as session:
            revoked_id = await session.scalar(
                update(ApiKey)
                .where(
                    ApiKey.org_id == org_id,
                    ApiKey.id == key_id,
                    ApiKey.revoked_at.is_(None),
                )
                .values(revoked_at=revoked_at)
                .returning(ApiKey.id)
            )
        return revoked_id is not None
