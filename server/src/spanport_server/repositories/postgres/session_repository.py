"""Reads and writes signed-in sessions."""

from datetime import datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spanport_server.core.ids import UuidV7, new_id
from spanport_server.models import UserSession


class SessionRepository:
    """user_sessions table access. Raw session ids and CSRF tokens never reach this layer."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Create the repository.

        Args:
            sessionmaker: Opens Postgres sessions.
        """
        self._sessionmaker = sessionmaker

    async def insert(self, user_id: UuidV7, token_hash: str, csrf_hash: str) -> None:
        """Store a new session for a user."""
        async with self._sessionmaker.begin() as session:
            session.add(
                UserSession(
                    id=new_id(), user_id=user_id, token_hash=token_hash, csrf_hash=csrf_hash
                )
            )

    async def touch_active(
        self, token_hash: str, idle_since: datetime, now: datetime
    ) -> tuple[UuidV7, str] | None:
        """Mark a live session as seen now.

        Args:
            token_hash: Hash of the session id from the cookie.
            idle_since: Sessions last seen before this have timed out.
            now: The current time.

        Returns:
            The session's user id and CSRF token hash, or None when the session is unknown,
            revoked or timed out.
        """
        async with self._sessionmaker.begin() as session:
            row = (
                await session.execute(
                    update(UserSession)
                    .where(
                        UserSession.token_hash == token_hash,
                        UserSession.revoked_at.is_(None),
                        UserSession.last_seen_at >= idle_since,
                    )
                    .values(last_seen_at=now)
                    .returning(UserSession.user_id, UserSession.csrf_hash)
                )
            ).first()
        return None if row is None else (row[0], row[1])

    async def revoke(self, token_hash: str, now: datetime) -> UuidV7 | None:
        """Revoke one session (sign out).

        Returns:
            The session's user id, or None when it was unknown or already revoked.
        """
        async with self._sessionmaker.begin() as session:
            return await session.scalar(
                update(UserSession)
                .where(UserSession.token_hash == token_hash, UserSession.revoked_at.is_(None))
                .values(revoked_at=now)
                .returning(UserSession.user_id)
            )

    async def revoke_for_user(self, user_id: UuidV7, now: datetime) -> int:
        """Revoke every live session of a user, e.g. after a password reset.

        Returns:
            How many sessions were revoked.
        """
        async with self._sessionmaker.begin() as session:
            revoked = await session.scalars(
                update(UserSession)
                .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
                .values(revoked_at=now)
                .returning(UserSession.id)
            )
            return len(revoked.all())
